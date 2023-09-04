"""This module creates completions from the OpenAI API.
The main function is `from_assistant()`.
"""
import os
from pprint import pformat
import re
from typing import NewType

import openai
from loguru import logger

from moshi import Message, Model, ModelType, Role
from moshi.utils import secrets

STOP_TOKENS = os.getenv("OPENAI_STOP_TOKENS", ["\n", "1:", "2:"])
OPENAI_COMPLETION_MODEL = Model(
    os.getenv("OPENAI_COMPLETION_MODEL", "text-davinci-002")
)
logger.info(f"OPENAI_COMPLETION_MODEL={OPENAI_COMPLETION_MODEL} STOP_TOKENS={STOP_TOKENS}")

ChatCompletionPayload = NewType("ChatCompletionPayload", list[dict[str, str]])
CompletionPayload = NewType("CompletionPayload", str)

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


def _chat_completion_payload_from_messages(
    messages: list[Message],
) -> ChatCompletionPayload:
    """Convert a list of messages into a payload for the messages arg of openai.ChatCompletion.create()
    Source:
        - https://platform.openai.com/docs/api-reference/chat
    """
    payload = []
    for msg in messages:
        msg_ = {"role": msg.role.value, "content": msg.body}
        payload.append(msg_)
    logger.debug(f"payload:\n{pformat(payload)}")
    return payload


def _completion_payload_from_messages(messages: list[Message]) -> CompletionPayload:
    """Convert a list of message into a payload for the prompt art of openai.Completion.create()
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
            msgstr = f"{msg.body}"
        else:
            sys_done = True
            role = "1" if msg.role == Role.USR else "2"
            msgstr = f"{role}: {msg.body}"
        payload.append(msgstr)
    payload = "\n".join(payload) + "\n2:"
    logger.debug(f"payload:\n{pformat(payload)}")
    return payload

def _chat_completion(
    payload: ChatCompletionPayload, n: int, model: Model, **kwargs
) -> list[str]:
    """Get the message"""
    msg_contents = []
    assert _get_type_of_model(model) == ModelType.CHAT
    response = openai.ChatCompletion.create(
        model=model,
        messages=payload,
        n=n,
        **kwargs,
    )
    logger.debug(f"response:\n{pformat(response)}")
    for choice in response.choices:
        if reason := choice["finish_reason"] != "stop":
            logger.warning(f"Got finish_reason: {reason}")
        if n > 1:
            logger.warning(f"n={n}, using only first completion")
        msg_contents.append(choice.message.content)  # choice is from the API
        break
    return msg_contents


def _completion(
    payload: CompletionPayload, n: int, model: Model, **kwargs
) -> list[str]:
    assert _get_type_of_model(model) == ModelType.COMP
    msg_contents = []
    response = openai.Completion.create(
        model=model,
        prompt=payload,
        n=n,
        stop=STOP_TOKENS,
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


def from_assistant(
    messages: Message | list[Message],
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
    with logger.contextualize(nmsg=len(messages), n=n, model=model, user=user, **kwargs):
        if isinstance(messages, Message):
            messages = [messages]
        assert n > 0 and isinstance(n, int)
        if n > 1:
            logger.warning(f"Generating many responses at once can be costly: n={n}")
        secrets.login_openai()
        msg_contents = []
        if user:
            kwargs["user"] = user
        logger.trace("Getting LLM response...")
        if _get_type_of_model(model) == ModelType.CHAT:
            payload = _chat_completion_payload_from_messages(messages)
            msg_contents = _chat_completion(payload, n, model, **kwargs)
        elif _get_type_of_model(model) == ModelType.COMP:
            payload = _completion_payload_from_messages(messages)
            msg_contents = _completion(payload, n, model, **kwargs)
        else:
            raise TypeError(f"Model not supported: {model}")
        logger.trace("LLM response received.")
        assert isinstance(msg_contents, list)
        assert all(isinstance(mc, str) for mc in msg_contents)
        return msg_contents

logger.success("Completion module loaded.")
