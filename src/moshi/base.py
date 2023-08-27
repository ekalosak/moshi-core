""" Base types. """
import datetime
from enum import Enum

from pydantic import BaseModel

from moshi import __version__ as moshi_version

class VersionedModel(BaseModel):
    created_at: datetime.datetime = datetime.datetime.now()
    moshi_version: str = moshi_version

    # def __post_init__(self):
    #     # TODO can these be moved to the dataclass-like init above?
    #     self.moshi_version = self.moshi_version or moshi_version
    #     self.created_at = self.created_at or datetime.datetime.now()

class Role(str, Enum):
    SYS = "sys"
    USR = "usr"
    AST = "ast"


class Message(VersionedModel):
    role: Role
    content: str
    translation: str = None
    sid: str = None  # NOTE storage id for audio

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