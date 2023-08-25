"""This module provides speech synthesis and transcription utilities.
The main entrypoint is `synthesize` which takes a string and returns an AudioFrame.
"""
import asyncio
import io
import os

import av
import openai
from google.cloud import texttospeech as tts
from loguru import logger

from . import audio
from moshi.utils import secrets

GOOGLE_SPEECH_SYNTHESIS_TIMEOUT = int(os.getenv("GOOGLE_SPEECH_SYNTHESIS_TIMEOUT", 5))
GOOGLE_VOICE_SELECTION_TIMEOUT = int(os.getenv("GOOGLE_VOICE_SELECTION_TIMEOUT", 5))
OPENAI_TRANSCRIPTION_MODEL = os.getenv("OPENAI_TRANSCRIPTION_MODEL", "whisper-1")
logger.info(f"GOOGLE_SPEECH_SYNTHESIS_TIMEOUT={GOOGLE_SPEECH_SYNTHESIS_TIMEOUT} GOOGLE_VOICE_SELECTION_TIMEOUT={GOOGLE_VOICE_SELECTION_TIMEOUT} OPENAI_TRANSCRIPTION_MODEL={OPENAI_TRANSCRIPTION_MODEL}")

# client = tts.TextToSpeechAsyncClient()  # NOTE for some reason the async client closes the event loop in testing, so we use the sync client.
client = tts.TextToSpeechClient()

logger.success("Speech module loaded.")

def gender_match(g1: str, g2: tts.SsmlVoiceGender) -> bool:
    if g1.lower() == "female" and g2 == 2:
        return True
    elif g1.lower() == "male" and g2 == 1:
        return True
    else:
        return False


async def get_voice(langcode: str, gender="FEMALE", model="Standard") -> str:
    """Get a valid voice for the language. Just picks the first match.
    Args:
        - langcode: e.g. "en-US"
    Raises:
        - ValueError if no voice found.
        - asyncio.TimeoutError if timeout exceeded.
    Source:
        - https://cloud.google.com/text-to-speech/pricing for list of valid voice model classes
    """
    logger.trace(f"Getting voice for lang code: {langcode}")
    response = await asyncio.wait_for(
        asyncio.to_thread(client.list_voices, language_code=langcode),
        timeout=GOOGLE_VOICE_SELECTION_TIMEOUT,
    )
    voices = response.voices
    logger.trace(f"Language {langcode} has {len(voices)} supported voices.")
    for voice in voices:
        logger.trace(f"Checking voice: {voice}")
        if model in voice.name and gender_match(gender, voice.ssml_gender):
            logger.trace("Found match")
            return voice
    raise ValueError(
        f"Voice not found for langcode={langcode}, gender={gender}, model={model}"
    )


async def _synthesize_speech_bytes(text: str, voice: tts.Voice, rate: int = 24000) -> bytes:
    """Synthesize speech to a bytestring in WAV (PCM_16) format.
    Implemented with tts.googleapis.com;
    """
    synthesis_input = tts.SynthesisInput(text=text)
    audio_config = tts.AudioConfig(
        audio_encoding=tts.AudioEncoding.LINEAR16,  # NOTE fixed s16 format
        sample_rate_hertz=rate,
    )
    langcode = voice.language_codes[0]
    logger.debug(f"Extracted language code from voice: {langcode}")
    voice_selector = tts.VoiceSelectionParams(
        name=voice.name,
        language_code=langcode,
        ssml_gender=voice.ssml_gender,
    )
    with logger.contextualize(voice_selector=voice_selector, audio_config=audio_config):
        logger.debug(f"Synthesizing speech for: {synthesis_input}")
    request = dict(
        input=synthesis_input,
        voice=voice_selector,
        audio_config=audio_config,
    )
    response = await asyncio.wait_for(
        asyncio.to_thread(client.synthesize_speech, request=request),
        timeout=GOOGLE_SPEECH_SYNTHESIS_TIMEOUT,
    )
    return response.audio_content


async def synthesize(text: str, voice: tts.Voice, rate: int = 24000) -> av.AudioFrame:
    audio_bytes = await _synthesize_speech_bytes(text, voice, rate)
    audio_frame = audio.wav2af(audio_bytes)
    return audio_frame


async def transcribe(audio_frame: av.AudioFrame, language: str = None) -> str:
    await secrets.login_openai()
    # _, fp = tempfile.mkstemp(suffix=".wav")
    # try:
    #     audio.write_audio_frame_to_wav(audio_frame, fp)
    #     with open(fp, "rb") as f:
    #         transcript = await openai.Audio.atranscribe(
    #             OPENAI_TRANSCRIPTION_MODEL, f, language=language
    #         )
    # finally:
    #     os.remove(fp)
    # return transcript["text"]
    buf = audio.af2wav(audio_frame)
    transcript = await openai.Audio.atranscribe(
        OPENAI_TRANSCRIPTION_MODEL, buf, language=language
    )
    logger.debug(f"Transcript: {transcript}")
    return transcript["text"]