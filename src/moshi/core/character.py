import dataclasses

from google.cloud import texttospeech


def _name_from_language(language: str) -> str:
    match language:
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
    name: str = None

    @property
    def language(self) -> str:
        return self.voice.language_codes[0].split("-")[0]

    def asdict(self) -> dict:
        return dataclasses.asdict(self)

    def __post_init__(self):
        self.name = self.name or _name_from_language(self.language)
