"""Create initial prompt for a an unstructured conversation."""
from abc import ABC, abstractmethod
import asyncio
import datetime
from enum import Enum
from typing import Annotated, Literal, Union

from google.cloud import firestore
from loguru import logger
from pydantic import Field

from moshi import Message, Role, VersionedModel, GOOGLE_PROJECT
from moshi.core import user, character, transcript
from moshi.utils import speech, lang

client = firestore.Client(project=GOOGLE_PROJECT)

logger.success("Activities module loaded.")

class ActivityType(str, Enum):
    UNSTRUCTURED = "unstructured"  # talk about anything, user-driven.
    TOPICAL = "topical"  # talk about a specific topic e.g. sports, politics, etc.
    SCENARIO = "scenario"  # play out a scenario e.g. a job interview, ordering coffee, etc.

class BaseActivity(ABC, VersionedModel):
    """An Activity provides a prompt for a conversation and the database wrapper."""

    type: ActivityType
    language: str
    _aid: str = None
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
        return self._transcript.tid

    @property
    def aid(self):
        return self._aid

    def create_doc(self) -> firestore.DocumentReference:
        """Create a new activity document in Firestore. Usually, this is done when the activity is started and the prompt for the desired language hasn't been initialized yet. If the activity type has already been initialized for the desired language, this will create a new one with a more recent `created_at` tag."""
        activity_payload = self.model_dump()
        if self.language.startswith("en"):
            prompt = self._get_base_prompt()
        else:
            prompt = self.translate_prompt()
        prompt = [msg.model_dump() for msg in prompt]
        activity_payload["prompt"] = prompt
        activity_collection = client.collection("activities")
        activity_doc = activity_collection.document()
        activity_doc.set(activity_payload)
        return activity_doc

    def get_doc(self) -> firestore.DocumentReference:
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
        return activity_doc

    def translate_prompt(self) -> list[Message]:
        """Translate the prompt into the user's target language.
        NOTE: this does not get the base prompt from Firebase, it gets it from the static configuration provided by the concrete BaseActivity class.
        """
        with logger.contextualize(activity_type=self.type, language=self.language):
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

    def init_transcript(self, uid: str) -> firestore.DocumentReference:
        """Create a skeleton transcript document in Firestore for the user.
        Raises:
            ValueError: If the user does not exist.
        """
        usr_doc_ref = client.collection("users").document(uid)
        usr_doc = usr_doc_ref.get()
        if not usr_doc.exists:
            raise ValueError(f"User does not exist: {uid}")
        transcript_doc_ref = usr_doc_ref.collection("transcripts").document()
        transcript_payload = transcript.skeleton(self._aid, self.language)
        transcript_doc_ref.set(transcript_payload)

    def start(self, usr: user.User) -> str:
        """This is a new coversation, so initialize the transcript skeleton.
        Returns:
            str: the id of the transcript
        """
        with logger.contextualize(**usr.model_dump(exclude=["email"]), activity_type=self.type):
            logger.trace("Starting activity...")
            activity_doc = self.get_doc()
            self._aid = activity_doc.id
            tid = self.init_transcript(usr.uid)
            logger.debug(f"Initialized transcript: {tid}")
            logger.trace("Started activity.")
        return tid
        

    def load(self):
        """If this is an existing conversation, load the transcript."""
        ...
        


class Unstructured(BaseActivity):
    type: Literal[ActivityType.UNSTRUCTURED] = ActivityType.UNSTRUCTURED

    def _get_base_prompt(self) -> list[Message]:
        messages = [
            # Message(
            #     Role.SYS,
            #     "Use this language to respond.",
            # ),
            Message(
                role=Role.SYS,
                content="You are the second character, and I am the first character.",
            ),
            Message(
                role=Role.SYS,
                content="Do not break the fourth wall.",
            ),
            Message(
                role=Role.SYS,
                content="If the conversation becomes laborious, try introducing or asking a question about various topics such as the weather, history, sports, etc.",
            )
        ]
        return messages


Activity = Annotated[
    Union[Unstructured, Unstructured], Field(discriminator="type")
]
