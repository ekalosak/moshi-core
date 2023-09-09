""" Base types. """
import datetime
from enum import Enum

from pydantic import BaseModel

from moshi import __version__ as moshi_version

class VersionedModel(BaseModel):
    created_at: datetime.datetime = datetime.datetime.now()
    moshi_version: str = moshi_version

class Role(str, Enum):
    SYS = "system"
    USR = "user"
    AST = "assistant"

class AudioStorage(BaseModel):
    """Where the audio for a message is stored."""
    path: str
    bucket: str = None

# class Translation(BaseModel):
#     body: str
#     language: str
#     # audio: AudioStorage | None = None

class Message(VersionedModel):
    role: Role
    body: str
    audio: AudioStorage | None = None
    translation: str | None = None

# TODO Model(ABC, str, Enum), ChatModel(Model), CompletionModel(Model)
class ModelType(str, Enum):
    """The two model types used by this app.
    Source:
        - https://platform.openai.com/docs/api-reference/models
    """

    COMP = "completion"
    CHAT = "chat_completion"


class Model(str, Enum):
    """The various models available."""

    GPT35TURBO = "gpt-3.5-turbo"
    GPT35TURBO0301 = "gpt-3.5-turbo-0301"
    TEXTDAVINCI003 = "text-davinci-003"
    TEXTDAVINCI002 = "text-davinci-002"
    TEXTCURIE001 = "text-curie-001"
    TEXTBABBAGE001 = "text-babbage-001"
    TEXTADA001 = "text-ada-001"