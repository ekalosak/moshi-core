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

    async def create_doc(self) -> firestore.DocumentReference:
        """Create a new activity document in Firestore. Usually, this is done when the activity is started and the prompt for the desired language hasn't been initialized yet. If the activity type has already been initialized for the desired language, this will create a new one with a more recent `created_at` tag."""
        activity_payload = self.model_dump()
        prompt = await self.translate_prompt()
        prompt = [msg.model_dump() for msg in prompt]
        activity_payload["prompt"] = prompt
        activity_collection = client.collection("activities")
        activity_doc = activity_collection.document()
        activity_doc.set(activity_payload)
        return activity_doc

    async def get_doc(self) -> firestore.DocumentReference:
        """Get the document for this activity in the desired language. If it doesn't exist, create it."""
        logger.trace("Getting activity doc...")
        activity_collection = client.collection("activities")
        # get the latest activity doc matching the activity type and language
        query = activity_collection.where("type", "==", self.type).where("language", "==", self.language).order_by("created_at", direction=firestore.Query.DESCENDING).limit(1)
        activity_docs = await query.get()
        if activity_docs:
            assert len(activity_docs) == 1, "More than one activity doc found."
            activity_doc = activity_docs[0]
        else:
            logger.info("Creating new activity doc...")
            activity_doc = self.create_doc()
            logger.success("Created new activity doc.")
        logger.trace("Got activity doc.")
        return activity_doc

    async def translate_prompt(self) -> list[Message]:
        """Translate the prompt into the user's target language.
        NOTE: this does not get the base prompt from Firebase, it gets it from the static configuration provided by the concrete BaseActivity class.
        """
        with logger.contextualize(activity_type=self.type, language=self.language):
            logger.trace("Translating prompt...")
            prompt = await lang.translate_messages(self._get_base_prompt(), self.language)
            logger.info(f"Translated prompt: {prompt}")
            logger.trace(f"Translated prompt.")
        return prompt

    async def init_transcript(self):
        """Create the Firestore artifacts for this conversation."""
        logger.trace("Initializing transcript...")
        messages = await asyncio.wait_for(self.get_prompt(), timeout=5)
        logger.trace(f"Translated prompt.")
        self._transcript = transcript.Transcript(
            self.activity,
            language=self.language,
            messages=messages,
        )
        await self.__save()
        logger.trace(f"Transcript initialized.")

    async def init_character(self):
        """Initialize the character for this conversation."""
        logger.debug(f"Creating character...")
        lang = self.profile.lang
        logger.trace("Getting voice")
        voice = await speech.get_voice(lang)
        logger.debug(f"Selected voice: {voice}")
        self._character = character.Character(voice)
        logger.debug(f"Character initialized: {self.__haracter}")

    async def start(self, usr: user.User) -> str:
        """This is a new coversation, so initialize the transcript.
        Returns:
            str: the id of the transcript
        """
        with logger.contextualize(**usr.model_dump()):
            logger.trace("Starting activity...")
            activity_doc = await self.get_doc()
            transcript_doc = await usr.init_transcript(activity_doc.id)
            # create transcript doc skeleton (created_at, language, activity id, empty messages array)

    async def load(self):
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
                Role.SYS,
                "You are the second character, and I am the first character.",
            ),
            Message(
                Role.SYS,
                "Do not break the fourth wall.",
            ),
            Message(
                Role.SYS,
                "If the conversation becomes laborious, try introducing or asking a question about various topics such as the weather, history, sports, etc.",
            )
        ]
        return messages


Activity = Annotated[
    Union[Unstructured, Unstructured], Field(discriminator="type")
]
