"""Operate the Activity using this module. Create, continue, and enrich the conversation."""
from abc import ABC, abstractmethod
import asyncio
import datetime
from enum import Enum
from typing import Annotated, Literal, Union
from pathlib import Path

from google.cloud import firestore
from loguru import logger
from pydantic import Field

from moshi import Message, Role, VersionedModel, GOOGLE_PROJECT, user
from moshi.core import character, transcript
from moshi.utils import speech, lang

client = firestore.Client(project=GOOGLE_PROJECT)
aclient = firestore.AsyncClient(project=GOOGLE_PROJECT)

logger.success("Activities module loaded.")

class NotCreatedError(Exception):
    """Raised when an activity is not created before it is loaded."""
    pass

class ActivityType(str, Enum):
    UNSTRUCTURED = "unstructured"  # talk about anything, user-driven.
    TOPICAL = "topical"  # talk about a specific topic e.g. sports, politics, etc.
    SCENARIO = "scenario"  # play out a scenario e.g. a job interview, ordering coffee, etc.

class BaseActivity(ABC, VersionedModel):
    """An Activity provides a prompt for a conversation and the database wrapper."""

    type: ActivityType
    language: str
    _aid: str = None
    _tid: str = None  # NOTE: redundant with _transcript
    _transcript: transcript.Transcript = None
    _character: character.Character = None

    @abstractmethod
    def _get_base_prompt(self) -> list[Message]:
        """Get the base prompt for this activity."""
        ...

    @property
    def messages(self) -> list[Message]:
        return self._transcript.messages

    @property
    def voice(self):
        return self._character.voice

    @property
    def tid(self):
        try:
            return self._transcript.tid
        except AttributeError:
            return self._tid

    @property
    def aid(self):
        return self._aid

    async def create_doc(self) -> firestore.DocumentReference:
        """Create a new activity document in Firestore. Usually, this is done when the activity is started and the prompt for the desired language hasn't been initialized yet. If the activity type has already been initialized for the desired language, this will create a new one with a more recent `created_at` tag."""
        activity_payload = self.model_dump()
        if self.language.startswith("en"):
            prompt = self._get_base_prompt()
        else:
            prompt = self.translate_prompt()
        prompt = [msg.model_dump() for msg in prompt]
        activity_payload["prompt"] = prompt
        activity_collection = aclient.collection("activities")
        activity_doc = activity_collection.document()
        await activity_doc.set(activity_payload)
        return activity_doc

    def init_activity(self):
        """Get the document for this activity in the desired language. If it doesn't exist, create it."""
        logger.trace("Getting activity doc...")
        activity_collection = client.collection("activities")
        # get the latest activity doc matching the activity type and language
        query = activity_collection.where("type", "==", self.type).where("language", "==", self.language).order_by("created_at", direction=firestore.Query.DESCENDING).limit(1)
        activity_docs = query.get()
        if activity_docs:
            assert len(activity_docs) == 1, "More than one activity doc found."
            activity_doc = activity_docs[0]
        else:
            logger.info("Creating new activity doc...")
            activity_doc = self.create_doc()
            logger.success("Created new activity doc.")
        logger.trace("Got activity doc.")
        self._aid = activity_doc.id

    def translate_prompt(self) -> list[Message]:
        """Translate the prompt into the user's target language.
        NOTE: this does not get the base prompt from Firebase, it gets it from the static configuration provided by the concrete BaseActivity class.
        """
        with logger.contextualize(activity_type=self.type.value, language=self.language):
            logger.trace("Translating prompt...")
            prompt = asyncio.run(lang.translate_messages(self._get_base_prompt(), self.language))
            logger.info(f"Translated prompt: {prompt}")
            logger.trace(f"Translated prompt.")
        return prompt

    def init_character(self):
        """Initialize the character for this conversation."""
        logger.debug(f"Creating character...")
        lang = self.profile.lang
        logger.trace("Getting voice")
        voice = asyncio.run(speech.get_voice(lang))
        logger.debug(f"Selected voice: {voice}")
        self._character = character.Character(voice)
        logger.debug(f"Character initialized: {self.__haracter}")

    def init_transcript(self, uid: str):
        """Create a skeleton transcript document in Firestore for the user.
        Raises:
            ValueError: If the user does not exist.
        """
        usr_doc_ref = client.collection("users").document(uid)
        usr_doc = usr_doc_ref.get()
        if not usr_doc.exists:
            raise ValueError(f"User does not exist: {uid}")
        transcript_doc_ref = usr_doc_ref.collection("transcripts").document()
        transcript_doc_ref.set(transcript.skeleton(self._aid, self.language))
        self._tid = transcript_doc_ref.id

    def start(self, usr: user.User):
        """This is a new coversation, so initialize the transcript skeleton.
        The tid and aid are initialized in this function, in place.
        """
        with logger.contextualize(activity_type=self.type.value):
            logger.trace("Starting activity...")
            self.init_activity()
            logger.trace(f"Initializing transcript...")
            self.init_transcript(usr.uid)
            logger.trace(f"Transcript initialized: {self._tid}")
            logger.trace(f"Activity started: {self._aid}")
        

    def load(self):
        """If this is an existing conversation, load the transcript and other activity attributes.
        Raises:
            NotCreatedError: If the activity has not been created yet.
        """
        if self._transcript:
            logger.debug("Already loaded")
            return
        raise NotImplementedError

    async def respond(self, usr_sid: str) -> str:
        """Main loop iter. From the user's audio, transcribe it, get the character's response, and synthesize it to audio.
        Args:
            usr_sid: the storage id for the user's audio.
        Returns:
            The storage id for the character's response audio.
        """
        logger.trace(f"Responding to: {usr_sid}")
        self.load()
        usr_txt = await speech.transcribe(usr_sid, self.language)
        usr_msg = Message(role=Role.USR, content=usr_txt)
        await self._transcript.add_msg(usr_msg)
        ast_txt = self._character.complete(self._transcript)
        ast_msg = Message(role=Role.AST, content=ast_txt)
        await self._transcript.add_msg(ast_msg)  # NOTE sequence add_msg so the msgs arrive in order
        ast_sid = await speech.synthesize(ast_txt, self.voice, to="storage")
        logger.trace(f"Responded to: {usr_sid}")
        return ast_sid

class Unstructured(BaseActivity):
    type: Literal[ActivityType.UNSTRUCTURED] = ActivityType.UNSTRUCTURED

    def _get_base_prompt(self) -> list[Message]:
        messages = [
            Message(
                role=Role.SYS,
                content="If the conversation becomes laborious, try introducing or asking a question about various topics such as the weather, history, sports, etc.",
            )
        ]
        return messages


Activity = Annotated[
    Union[Unstructured, Unstructured], Field(discriminator="type")
]
