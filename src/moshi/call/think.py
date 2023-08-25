""" This module abstracts specific chatbot implementations for use in the ChitChat app. """
import os
import re
from dataclasses import asdict
from enum import Enum
from pprint import pformat
from typing import NewType

import openai
from loguru import logger

from moshi import Message, Model, ModelType, Role
from moshi.utils import secrets

OPENAI_COMPLETION_MODEL = Model(
    os.getenv("OPENAI_COMPLETION_MODEL", "text-davinci-002")
)
logger.info(f"Using completion model: {OPENAI_COMPLETION_MODEL}")

logger.success("Loaded!")


def _get_type_of_model(model: Model) -> ModelType:
    """Need to know the type of model for endpoint compatibility.
    Source:
        - https://platform.openai.com/docs/models/model-endpoint-compatibility
    """
    if model == Model.GPT35TURBO or model == Model.GPT35TURBO0301:
        return ModelType.CHAT
    else:
        return ModelType.COMP


def _clean_completion(msg: str) -> str:
    """Remove all the formatting the completion model thinks it should give."""
    logger.trace("Cleaning response...")
    # 1. only keep first response, remove its prefix
    pattern = r"(?:\n|^)([0-9]+:)(?:[ \n\t]*)([^\n\t]+)"
    match = re.search(pattern, msg)
    if match:
        first_response = match.group(2)
        logger.trace(f"Regex matched: {first_response}")
        result = first_response
    else:
        logger.trace("Regex did not match.")
        result = msg
    return result


ChatCompletionPayload = NewType("ChatCompletionPayload", list[dict[str, str]])
CompletionPayload = NewType("CompletionPayload", str)


def _chat_completion_payload_from_messages(
    messages: list[Message],
) -> ChatCompletionPayload:
    """Convert a list of messages into a payload for the messages arg of openai.ChatCompletion.acreate()
    Source:
        - https://platform.openai.com/docs/api-reference/chat
    """
    payload = []
    for msg in messages:
        msg_ = {"role": msg.role.value, "content": msg.content}
        payload.append(msg_)
    logger.debug(f"payload:\n{pformat(payload)}")
    return payload


def _completion_payload_from_messages(messages: list[Message]) -> CompletionPayload:
    """Convert a list of message into a payload for the prompt art of openai.Completion.acreate()
    Source:
        - https://platform.openai.com/docs/api-reference/completions/create
    """
    payload = []
    sys_done = False
    for i, msg in enumerate(messages):
        if msg.role == Role.SYS:
            if sys_done:
                logger.warning(
                    f"System message out of place:\n{msg}\n{[msg.role for msg in messages]}"
                )
            msgstr = f"{msg.content}"
        else:
            sys_done = True
            role = "1" if msg.role == Role.USR else "2"
            msgstr = f"{role}: {msg.content}"
        payload.append(msgstr)
    payload = "\n".join(payload) + "\n2:"
    logger.debug(f"payload:\n{pformat(payload)}")
    return payload

async def _chat_completion(
    payload: ChatCompletionPayload, n: int, model: Model, user: str | None = None, **kwargs
) -> list[str]:
    """Get the message"""
    msg_contents = []
    assert _get_type_of_model(model) == ModelType.CHAT
    response = await openai.ChatCompletion.acreate(
        model=model,
        messages=payload,
        n=n,
        user=user,
        **kwargs,
    )
    logger.debug(f"response:\n{pformat(response)}")
    for choice in response.choices:
        if reason := choice["finish_reason"] != "stop":
            logger.warning(f"Got finish_reason: {reason}")
        if n > 1:
            logger.warning(f"n={n}, using only first completion")
        msg_contents.append(choice.message.content)
        break
    return msg_contents


async def _completion(
    payload: CompletionPayload, n: int, model: Model, user: str | None = None, **kwargs
) -> list[str]:
    assert _get_type_of_model(model) == ModelType.COMP
    msg_contents = []
    response = await openai.Completion.acreate(
        model=model,
        prompt=payload,
        n=n,
        user=user,
        **kwargs,
    )
    logger.debug(f"response:\n{pformat(response)}")
    for choice in response.choices:
        if reason := choice["finish_reason"] != "stop":
            logger.warning(f"Got finish_reason: {reason}")
        msg = choice.text.strip()
        if n > 1:
            logger.warning(f"n={n}, using only first completion")
        break
    msg = _clean_completion(msg)
    msg_contents.append(msg)
    return msg_contents


async def completion_from_assistant(
    messages: list[Message],
    n: int = 1,
    model=Model.TEXTDAVINCI002,
    user: str | None = None,
    **kwargs,
) -> list[str]:
    """Get the conversational response from the LLM.
    Args:
        n: how many responses
        kwargs: passed directly to the OpenAI
    Details on args:
        https://platform.openai.com/docs/api-reference/chat/create
    """
    assert n > 0 and isinstance(n, int)
    if n > 1:
        logger.warning(f"Generating many responses at once can be costly: n={n}")
    await secrets.login_openai()
    msg_contents = []
    if _get_type_of_model(model) == ModelType.CHAT:
        payload = _chat_completion_payload_from_messages(messages)
        msg_contents = await _chat_completion(payload, n, model, user, **kwargs)
    elif _get_type_of_model(model) == ModelType.COMP:
        payload = _completion_payload_from_messages(messages)
        msg_contents = await _completion(payload, n, model, user, **kwargs)
    else:
        raise TypeError(f"Model not supported: {model}")
    assert isinstance(msg_contents, list)
    assert all(isinstance(mc, str) for mc in msg_contents)
    return msg_contents
