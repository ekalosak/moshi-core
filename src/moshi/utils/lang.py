"""This module provides language utilities, including:
    - Language detection
    - Language translation
    - String similarity
"""
# TODO use langcodes package to parse / handle language codes

from difflib import SequenceMatcher
import textwrap

import iso639
import isocodes
from google.cloud import translate_v2 as translate
from loguru import logger

from moshi import Message
from moshi.utils.log import traced

client = translate.Client()

def similar(a, b) -> float:
    """Return similarity of two strings.
    Source:
        - https://stackoverflow.com/a/17388505/5298555
    """
    return SequenceMatcher(None, a, b).ratio()

def match(language: str) -> str:
    """Get the closest matching language code ISO-639-1."""
    # There is spotty language coverage across libraries, so we use both
    try:
        lan = iso639.Language.match(language)
        logger.debug(f"Matched {language} to {lan} using iso639.")
        lan = lan.part1
    except iso639.language.LanguageNotFoundError:
        lan = isocodes.languages.get(name=language)['alpha_2']
        if not lan:
            lan = isocodes.languages.get(alpha_3=language)['alpha_2']
        if not lan:
            lan = isocodes.languages.get(alpha_2=language)['alpha_2']
        if not lan:
            raise ValueError(f"Could not find language for {language}")
        logger.debug(f"Matched {language} to {lan} using isocodes.")
    assert len(lan) in {2, 3}, f"Invalid language code: {lan}"
    return lan

@traced
def translate_messages(messages: list[Message], target: str) -> list[Message]:
    """ Translate a list of messages. Timeout handled by caller. """
    with logger.contextualize(tmtarget=target):
        logger.trace(f"Translating {len(messages)} messages...")
        for i, message in enumerate(messages):
            logger.debug(f"Translating: {message}")
            messages[i].body = translate_text(message.body, target=target)
            logger.debug(f"Translated to: {messages[i]}")
        logger.trace(f"Translated {len(messages)} messages.")
    return messages

@traced
def translate_text(text: str, target: str) -> str:
    """Translate text to target language. Timeout handled by caller.
    Args:
        text: The text to translate.
        target: The target language bcp47 code.
    Returns:
        The translated text.
    """
    if '-' in target:
        target = target.split('-')[0]
    assert len(target) in {2, 3}, f"Invalid target language: {target}"
    with logger.contextualize(tttarget=target):
        logger.debug("Translation has no timeout.")
        logger.trace(f"Translating: {textwrap.shorten(text, 64)}")
        result = client.translate(values=text, target_language=target)
        translated_text = result["translatedText"]
        translated_text = translated_text.replace("&#39;", "'")
        logger.trace(f"Translated to: {textwrap.shorten(translated_text, 64)}")
    return translated_text

@traced
def detect_language(text: str) -> str:
    """Detects the text's language. Run setup_client first.
    Source:
        - https://cloud.google.com/translate/docs/basic/detecting-language#translate-detect-language-multiple-python
    """
    logger.trace(f"Detecting language for: {textwrap.shorten(text, 64)}")
    logger.debug("Translation has no timeout.")
    result = client.detect_language(text)
    conf = result["confidence"]
    lang = result["language"]
    logger.debug(f"Confidence: {conf}")
    logger.debug(f"Language: {lang}")
    return lang

logger.success("Language moduel loaded.")