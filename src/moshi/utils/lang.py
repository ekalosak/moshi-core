# This module provides language utilities, including:
#     - Language detection
#     - Language translation
#     - String similarity

import asyncio
import contextvars
import textwrap
from difflib import SequenceMatcher

from google.cloud import translate_v2 as translate
from loguru import logger

from moshi import Message

logger.trace("Loading lang module...")
client = translate.Client()
logger.trace("Loaded!")


def similar(a, b) -> float:
    """Return similarity of two strings.
    Source:
        - https://stackoverflow.com/a/17388505/5298555
    """
    return SequenceMatcher(None, a, b).ratio()


async def translate_messages(messages: list[Message], target: str) -> list[Message]:
    """ Translate a list of messages. Timeout handled by caller. """
    logger.trace(f"Translating {len(messages)} messages to {target}...")
    tasks = []
    async with asyncio.TaskGroup() as tg:  # NOTE if 1 fails (w/ non-cancel), all fail.
        for message in messages:
            logger.trace(f"Translating message {message} to {target}...")
            task = tg.create_task(translate_text(message.content, target=target))
            tasks.append(task)
    for i, task in enumerate(tasks):
        logger.trace(f"Task {i} is {task}")
        val = await task
        logger.trace(f"Task {i} returned: {val}")
        messages[i].content = val
        logger.trace(f"Translated message {i} to {target}: {messages[i]}")
    logger.trace(f"Translated {len(messages)} messages to {target}.")
    return messages


async def translate_text(text: str, target: str) -> str:
    if '-' in target:
        target = target.split('-')[0]
    assert len(target) in {2, 3}, f"Invalid target language: {target}"
    logger.trace(f"target = {target}")
    logger.trace(f"text = {text}")
    try:
        result = await asyncio.to_thread(client.translate, values=text, target_language=target)
    except Exception as e:
        logger.error(f"Error translating text: {e}")
        raise
    logger.trace(f"result = {result}")
    return result["translatedText"]

async def detect_language(text: str) -> str:
    """Detects the text's language. Run setup_client first.
    Source:
        - https://cloud.google.com/translate/docs/basic/detecting-language#translate-detect-language-multiple-python
    """
    logger.debug(f"Detecting language for: {textwrap.shorten(text, 64)}")
    # NOTE using to_thread rather than TranslationAsyncClient because later has much more complicated syntax
    result = await asyncio.to_thread(
        client.detect_language,
        text,
    )
    conf = result["confidence"]
    lang = result["language"]
    logger.debug(f"Confidence: {conf}")
    logger.info(f"Language: {lang}")
    return lang
