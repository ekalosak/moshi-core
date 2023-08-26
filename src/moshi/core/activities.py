"""Create initial prompt for a an unstructured conversation."""
from abc import ABC, abstractmethod
import asyncio
import dataclasses
import datetime
from enum import Enum
from typing import Annotated, Literal, Union

from loguru import logger
from pydantic import BaseModel, Field

from .base import Message, Role, Profile
from .character import Character
from moshi import __version__ as moshi_version
from moshi.utils.storage import client as firestore_client
from moshi.utils import speech, lang

# transcript_col = firestore_client.collection("transcripts")


@dataclasses.dataclass
class Transcript:
    actid: str
    messages: list[Message]
    language: str
    tid: str = None
    timestamp: datetime.datetime = None
    moshi_version: str = moshi_version

    def asdict(self) -> dict:
        return dataclasses.asdict(self)

    def __post_init__(self):
        self.timestamp = self.timestamp or datetime.datetime.now()


class ActivityType(str, Enum):
    UNSTRUCTURED = "unstructured"


class BaseActivity(ABC, BaseModel):
    """An Activity provides a prompt for a conversation and the database wrapper."""

    activity_type: ActivityType
    profile: Profile
    _character: Character = None
    _transcript: Transcript = None

    def __init__(self, activity_type: ActivityType, profile: Profile, tid: str = None):
        logger.trace("Initializing activity...")
        super().__init__(activity_type=activity_type, profile=profile)
        loop = asyncio.get_event_loop()
        if tid:
            logger.trace("Loading existing transcript...")
            loop.run_until_complete(self.__load(tid))
        else:
            logger.trace("Creating new transcript...")
            loop.run_until_complete(self.__init())
        logger.trace("Activity initialized.")



    @abstractmethod
    def _prompt(self) -> list[Message]:
        """Assemble the prompt."""
        ...

    @property
    def messages(self) -> list[Message]:
        return self._transcript.messages

    @property
    def voice(self):
        return self._character.voice

    @property
    def lang(self):
        return self._character.language

    @property
    def tid(self):
        return self._transcript.tid

    async def add_msg(self, msg: Message):
        logger.trace("Adding message to transcript...")
        self._transcript.messages.append(msg)
        await self.__save()
        logger.trace("Added message to transcript.")

    async def _translate_prompt(self) -> list[Message]:
        """Translate the prompt into the user's target language. Timeout handled by caller. Requires a profile to be set."""
        logger.trace("Translating prompt...")
        prompt = self._prompt()
        prompt = await lang.translate_messages(prompt, self.profile.lang)
        logger.trace(f"Translated prompt: {prompt}")
        return prompt

    async def __init_transcript(self):
        """Create the Firestore artifacts for this conversation."""
        logger.trace("Initializing transcript...")
        messages = await asyncio.wait_for(self._translate_prompt(), timeout=5)
        logger.trace(f"Translated prompt: {messages}")
        self.__transcript = Transcript(
            self.activity,
            language=ctx.profile.get().lang,
            messages=messages,
        )
        await self.__save()
        logger.trace(f"Transcript initialized.")

    async def __init_character(self):
        """Initialize the character for this conversation."""
        logger.debug(f"Creating character...")
        lang = self.profile.lang
        logger.trace("Getting voice")
        voice = await speech.get_voice(lang)
        logger.debug(f"Selected voice: {voice}")
        self.__character = Character(voice)
        logger.debug(f"Character initialized: {self.__character}")

    async def __init(self):
        """If this is a new conversation, initialize the transcript and character."""
        await asyncio.gather(self.__init_transcript(), self.__init_character())

    async def __load(self):
        """If this is an existing conversation, load the transcript and character."""
        

    async def __save(self):
        """Save the transcript to Firestore."""
        if self.__cid:
            logger.info("Updating existing doc...")
            doc_ref = transcript_col.document(self.__cid)
        else:
            logger.info("Creating new conversation document...")
            doc_ref = transcript_col.document()
            self.__cid = doc_ref.id
        with logger.contextualize(cid=self.__cid):
            logger.debug(f"Saving conversation document...")
            try:
                await doc_ref.set(self.__transcript.asdict())
                logger.success(f"Saved conversation document!")
            except asyncio.CancelledError:
                logger.debug(f"Cancelled saving conversation document.")


class Unstructured(BaseActivity):
    activity_type: Literal[ActivityType.UNSTRUCTURED] = ActivityType.UNSTRUCTURED

    def _prompt(self) -> list[Message]:
        messages = [
            Message(
                Role.SYS,
                "Use this language to respond.",
            ),
            Message(
                Role.SYS,
                "Do not break the fourth wall.",
            ),
            Message(
                Role.SYS,
                "You are the second character, and I am the first character.",
            ),
        ]
        return messages


Activity = Annotated[
    Union[Unstructured, Unstructured], Field(discriminator="activity_type")
]
