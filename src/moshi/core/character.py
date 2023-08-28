import dataclasses

from google.cloud import texttospeech
import iso639
from loguru import logger

from moshi import Message
from moshi.utils import speech, comp

def _name_from_language(language: iso639.Language) -> str:
    match language.part1:
        case "en":
            return "Courtney"
        case "es":
            return "Carmen"
        case "fr":
            return "Céline"
        case "de":
            return "Carolin"
        case "it":
            return "Chiara"
        case "ja":
            return "千尋"
        case "ko":
            return "채원"
        case "zh":
            return "小梅"
        case _:
            return "Moshi"


@dataclasses.dataclass
class Character:
    voice: texttospeech.Voice
    name: str | None = None
    description: str | None = None
    age: int | None = None

    def __post_init__(self):
        self.name = self.name or _name_from_language(self.language)

    @property
    def language(self) -> iso639.Language:
        lan = iso639.Language.match(self.voice.language_codes[0].split('-')[0])
        if not lan:
            raise ValueError(f"Could not find language for {self.voice.language_codes[0]}")
        return lan

    @property
    def country(self) -> str:
        logger.debug(f"language_codes={self.voice.language_codes}")
        return self.voice.language_codes[0].split("-")[1].upper()

    @property
    def gender(self) -> str:
        return self.voice.ssml_gender.name

    def complete(self, prompt: list[Message]) -> Message:
        """Complete the prompt with the character's voice."""
        return comp.from_assistant(prompt)

    def asdict(self) -> dict:
        return dataclasses.asdict(self)

    @staticmethod
    def from_language(language: str) -> 'Character':
        logger.debug(f"language={language}; should have country code")
        with logger.contextualize(language=language):
            logger.trace("Creating character...")
            voice = speech.get_voice(language)
            character = Character(voice)
            logger.debug(f"Character created: {character}")
        return character


def get():
    """Get the character for this scenario."""
    return {
        'name': 'Francis',
        'voice': {
            'en': 'en-US-Wavenet-A',
            'fr': 'fr-FR-Wavenet-A',
        },
        'gender': 2,
        'age': 20,
        'description': 'This character is a student.',
    }
