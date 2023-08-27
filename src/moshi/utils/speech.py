"""This module provides speech synthesis and transcription utilities.
The main entrypoint is `synthesize` which takes a string and returns an AudioFrame.
"""
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

client = tts.TextToSpeechClient()

logger.success("Speech module loaded.")

def gender_match(g1: str, g2: tts.SsmlVoiceGender) -> bool:
    if g1.lower() == "female" and g2 == 2:
        return True
    elif g1.lower() == "male" and g2 == 1:
        return True
    else:
        return False


def list_voices() -> list[tts.Voice]:
    """List all voices supported by the API."""
    response = client.list_voices(timeout=GOOGLE_VOICE_SELECTION_TIMEOUT)
    return response.voices

def get_voice(langcode: str, gender="FEMALE", model="Standard") -> str:
    """Get a valid voice for the language. Just picks the first match.
    Args:
        - langcode: e.g. "en-US"
    Raises:
        - ValueError if no voice found.
    Source:
        - https://cloud.google.com/text-to-speech/pricing for list of valid voice model classes
    """
    logger.trace(f"Getting voice for lang code: {langcode}")
    response = client.list_voices(language_code=langcode, timeout=GOOGLE_VOICE_SELECTION_TIMEOUT)
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


def _synthesize_bytes(text: str, voice: tts.Voice, rate: int = 24000) -> bytes:
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
    response = client.synthesize_speech(request=request, timeout=GOOGLE_SPEECH_SYNTHESIS_TIMEOUT)
    return response.audio_content


def _synthesize_af(text: str, voice: tts.Voice, rate: int = 24000) -> av.AudioFrame:
    audio_bytes = _synthesize_bytes(text, voice, rate)
    audio_frame = audio.wav2af(audio_bytes)
    return audio_frame

def synthesize(text: str, voice: tts.Voice, rate: int = 24000, to="audio_frame") -> av.AudioFrame | bytes | str:
    """Synthesize speech to an AudioFrame or Storage.
    Returns:
        - AudioFrame if to == "audio_frame"
        - Storage id if to == "storage"
        - bytes if to == "bytes"
    Raises:
        - ValueError if to is invalid.
    """
    if to == "audio_frame":
        return _synthesize_af(text, voice, rate)
    elif to == "storage":
        audio_bytes = _synthesize_bytes(text, voice, rate)
        return audio.upload_audio(audio_bytes)
    elif to == "bytes":
        return _synthesize_bytes(text, voice, rate)
    else:
        raise ValueError(f"Invalid value for 'to': {to}")

def _transcribe_audio_buffer(buf: io.BytesIO, language: str = None) -> str:
    logger.warning("Transcription has no timeout.")
    transcript = openai.Audio.transcribe(
        OPENAI_TRANSCRIPTION_MODEL, buf, language=language
    )
    logger.debug(f"Transcript: {transcript}")
    return transcript["text"]

def _transcribe_af(audio_frame: av.AudioFrame, language: str = None) -> str:
    buf = audio.af2wav(audio_frame)
    return _transcribe_audio_buffer(buf, language)

def transcribe(aud: av.AudioFrame | str, language: str = None) -> str:
    """Transcribe audio to text.
    Args:
        - audio: either an AudioFrame or a storage id.
    """
    secrets.login_openai()
    if isinstance(aud, av.AudioFrame):
        return _transcribe_af(aud, language)
    elif isinstance(aud, str):
        with logger.contextualize(aud=aud):
            logger.trace(f"Getting audio from storage...")
            buf = audio.download(aud)
            logger.trace(f"Audio retrieved from storage")
        return _transcribe_audio_buffer(buf, language)