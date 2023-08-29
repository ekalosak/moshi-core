"""Operate the Activity using this module. Create, continue, and enrich the conversation."""
from abc import ABC, abstractmethod
from enum import Enum
import os
from pprint import pformat
from pathlib import Path
from typing import Annotated, Literal, Union
import tempfile

from google.cloud import firestore
from google.cloud.firestore_v1 import FieldFilter
from loguru import logger
from pydantic import Field

from moshi import Message, Role, VersionedModel, user
from moshi.core import character, transcript
from moshi.utils import audio, speech, lang
from moshi.utils.audio import AUDIO_BUCKET
from moshi.utils.log import traced

client = firestore.Client()

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
    _tid: str = None
    _uid: str = None
    _transcript: transcript.Transcript = None
    _prompt: list[Message] = None
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

    @traced
    def create_doc(self):
        """Create a new activity document in Firestore. Usually, this is done when the activity is started and the prompt for the desired language hasn't been initialized yet. If the activity type has already been initialized for the desired language, this will create a new one with a more recent `created_at` tag."""
        activity_payload = self.model_dump()
        if self.language.startswith("en"):
            prompt = self._get_base_prompt()
        else:
            prompt = lang.translate_messages(self._get_base_prompt(), self.language)
        self._prompt = prompt
        prompt = [transcript.message_to_payload(msg) for msg in prompt]
        activity_payload["prompt"] = prompt
        activity_collection = client.collection("activities")
        activity_doc = activity_collection.document()
        self._aid = activity_doc.id
        activity_doc.set(activity_payload)
        logger.success(f"Created new activity doc: {activity_doc.id}")

    @traced
    def init_activity(self):
        """Get the document for this activity in the desired language. If it doesn't exist, create it."""
        with logger.contextualize(activity_type=self.type.value, language=self.language):
            activity_collection = client.collection("activities")
            query = activity_collection.where(filter=FieldFilter("type", "==", self.type.value)).where(filter=FieldFilter("language", "==", self.language)).order_by("created_at", direction=firestore.Query.DESCENDING).limit(1)
            activity_docs = query.get()
            if activity_docs:
                assert len(activity_docs) == 1, "More than one activity doc found."
                activity_doc = activity_docs[0]
                self._aid = activity_doc.id
                self._prompt = [Message(**msg) for msg in activity_doc.get("prompt")]
            else:
                activity_doc = self.create_doc()

    @traced
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
        logger.info(f"Initialized transcript: {self._tid}")

    @traced
    def start(self, usr: user.User):
        """This is a new coversation, so initialize the transcript skeleton.
        The tid and aid are initialized in this function, in place.
        """
        with logger.contextualize(activity_type=self.type.value):
            self.init_activity()
            self.init_transcript(usr.uid)
            logger.info(f"Activity started: {self._aid}")

    @staticmethod
    @traced
    def load(uid: str, tid: str) -> 'BaseActivity':
        """Load an existing activity from the user id and transcript id."""
        with logger.contextualize(tid=tid, uid=uid):
            activity_collection = client.collection("activities")
            usr_ref = client.collection("users").document(uid)
            transcript_doc_ref = usr_ref.collection("transcripts").document(tid)
            transcript_doc = transcript_doc_ref.get()
            if not transcript_doc.exists:
                raise ValueError(f"Transcript does not exist: {tid}")
            logger.debug(f"Got transcript: {transcript_doc.to_dict()}")
            activity_doc_ref = activity_collection.document(transcript_doc.get("activity_id"))
            activity_doc = activity_doc_ref.get()
            if not activity_doc.exists:
                raise ValueError(f"Activity does not exist: {activity_doc.id}")
            activity = Activity(
                type=activity_doc.get("type"),
                language=activity_doc.get("language"),
                created_at=activity_doc.get("created_at"),
                moshi_version=activity_doc.get("moshi_version"),
            )
            activity._aid = activity_doc.id
            activity._tid = tid
            activity._uid = uid
            assert transcript_doc.get("activity_id") == activity_doc.id, "Transcript and activity do not match."
            activity._transcript = transcript.Transcript(
                transcript_id=transcript_doc.id,
                user_id=uid,
                **transcript_doc.to_dict()
            )
            logger.debug(f"Transcript: {activity._transcript}")
            activity._prompt = [Message(**msg) for msg in activity_doc.get("prompt")]
            logger.debug(f"Prompt: {activity._prompt}")
            activity._character = character.Character.from_language(transcript_doc.get("language"))
        logger.info(f"Loaded activity: {activity._aid}")
        return activity

    @traced
    def respond(self, usr_audio_storage_name: str) -> str:
        """Main loop iter. From the user's audio, transcribe it, get the character's response, and synthesize it to audio.
        Returns:
            The storage id for the character's response audio.
        """
        logger.trace(f"Responding to: {usr_audio_storage_name}")
        if not self._aid or not self._tid:
            raise NotCreatedError("Activity not created.")
        usr_txt = speech.transcribe(usr_audio_storage_name, self.language)
        assert isinstance(usr_txt, str)
        usr_msg = Message(role=Role.USR, content=usr_txt, audio={'path': usr_audio_storage_name, 'bucket': AUDIO_BUCKET})
        self._transcript.add_msg(usr_msg)
        messages = self._prompt + self._transcript.messages
        logger.trace(f"Prompt + transcript have n messages: {len(messages)}")
        ast_txt = self._character.complete(messages)
        assert len(ast_txt) == 1, "Character response should be a single message."
        ast_txt = ast_txt[0]
        assert isinstance(ast_txt, str), "Character response should be a string."
        ast_audio_bytes = speech.synthesize(ast_txt, self.voice, to="bytes")
        ast_audio_storage_name = audio.make_ast_audio_name(usr_audio_storage_name)
        _, ast_audio_file = tempfile.mkstemp(suffix=".wav", dir='/tmp')
        try:
            with open(ast_audio_file, "wb") as f:
                f.write(ast_audio_bytes)
            audio.upload(ast_audio_file, ast_audio_storage_name)
        finally:
            logger.trace(f"Removing temporary file: {ast_audio_file}")
            os.remove(ast_audio_file)
        ast_msg = Message(role=Role.AST, content=ast_txt, audio={'path': ast_audio_storage_name, 'bucket': AUDIO_BUCKET})
        self._transcript.add_msg(ast_msg)  # NOTE sequence add_msg so the msgs arrive in order (for async)
        logger.trace(f"Responded to: {usr_audio_storage_name}")
        return ast_audio_storage_name

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

logger.success("Activities module loaded.")
