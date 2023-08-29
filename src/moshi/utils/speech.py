"""This module provides speech synthesis and transcription utilities.
The main entrypoint is `synthesize` which takes a string and returns an AudioFrame.
"""
import io
import os
from pathlib import Path
from textwrap import shorten

import av
from google.cloud import texttospeech as tts
import iso639
from loguru import logger
import openai

from . import audio
from moshi.utils import secrets
from moshi.utils.log import traced

GOOGLE_SPEECH_SYNTHESIS_TIMEOUT = int(os.getenv("GOOGLE_SPEECH_SYNTHESIS_TIMEOUT", 5))
GOOGLE_VOICE_SELECTION_TIMEOUT = int(os.getenv("GOOGLE_VOICE_SELECTION_TIMEOUT", 5))
OPENAI_TRANSCRIPTION_MODEL = os.getenv("OPENAI_TRANSCRIPTION_MODEL", "whisper-1")
logger.info(f"GOOGLE_SPEECH_SYNTHESIS_TIMEOUT={GOOGLE_SPEECH_SYNTHESIS_TIMEOUT} GOOGLE_VOICE_SELECTION_TIMEOUT={GOOGLE_VOICE_SELECTION_TIMEOUT} OPENAI_TRANSCRIPTION_MODEL={OPENAI_TRANSCRIPTION_MODEL}")

client = tts.TextToSpeechClient()

def gender_match(g1: str, g2: tts.SsmlVoiceGender) -> bool:
    if g1.lower() == "female" and g2 == 2:
        return True
    elif g1.lower() == "male" and g2 == 1:
        return True
    else:
        return False


@traced
def list_voices(lan: str=None) -> list[tts.Voice]:
    """List all voices supported by the API.
    Args:
        - lan: if provided, filter by language code. It must be a BCP 47 language code e.g. "en-US" https://www.rfc-editor.org/rfc/bcp/bcp47.txt
    """
    if lan:
        logger.debug(f"Listing voices for language: {lan}")
        response = client.list_voices(language_code=lan, timeout=GOOGLE_VOICE_SELECTION_TIMEOUT)
    else:
        logger.debug("Listing all voices.")
        response = client.list_voices(timeout=GOOGLE_VOICE_SELECTION_TIMEOUT)
    return response.voices

def get_voice(langcode: str, gender="FEMALE", model="Standard") -> str:
    """Get a valid voice for the language. Just picks the first match.
    Args:
        - langcode: in BPC 47 format e.g. "en-US" https://www.rfc-editor.org/rfc/bcp/bcp47.txt
    Raises:
        - ValueError if no voice found.
    Source:
        - https://cloud.google.com/text-to-speech/pricing for list of valid voice model classes
    """
    logger.debug(f"Getting voice for lang code: {langcode}")
    voices = list_voices(langcode)
    logger.debug(f"Language {langcode} has {len(voices)} supported voices.")
    for voice in voices:
        if model in voice.name and gender_match(gender, voice.ssml_gender):
            logger.debug("Found match")
            return voice
    raise ValueError(
        f"Voice not found for langcode={langcode}, gender={gender}, model={model}"
    )


def _synthesize_bytes(text: str, voice: tts.Voice, rate: int = 24000) -> bytes:
    """Synthesize speech to a bytestring in WAV (PCM_16) format.
    Implemented with tts.googleapis.com;
    """
    logger.debug(f"text={text} voice={voice} rate={rate}")
    synthesis_input = tts.SynthesisInput(text=text)
    audio_config = tts.AudioConfig(
        audio_encoding=tts.AudioEncoding.LINEAR16,  # NOTE fixed s16 format
        sample_rate_hertz=rate,
    )
    langcode = voice.language_codes[0]
    logger.trace(f"Extracted language code from voice: {langcode}")
    voice_selector = tts.VoiceSelectionParams(
        name=voice.name,
        language_code=langcode,
        ssml_gender=voice.ssml_gender,
    )
    with logger.contextualize(voice_selector=voice_selector, audio_config=audio_config):
        logger.trace(f"Synthesizing speech for: {synthesis_input}")
        request = dict(
            input=synthesis_input,
            voice=voice_selector,
            audio_config=audio_config,
        )
        response = client.synthesize_speech(request=request, timeout=GOOGLE_SPEECH_SYNTHESIS_TIMEOUT)
        logger.trace(f"Synthesized speech: {len(response.audio_content)} bytes")
    return response.audio_content

def _synthesize_af(text: str, voice: tts.Voice, rate: int = 24000) -> av.AudioFrame:
    audio_bytes = _synthesize_bytes(text, voice, rate)
    audio_frame = audio.wav2af(audio_bytes)
    return audio_frame

@traced
def synthesize(text: str, voice: tts.Voice, rate: int = 24000, to="audio_frame") -> av.AudioFrame | bytes:
    """Synthesize speech to an AudioFrame or Storage.
    Returns:
        - AudioFrame: if to == "audio_frame"
        - bytes: raw WAV format audio if to == "bytes"
    Raises:
        - ValueError if to is invalid.
    """
    with logger.contextualize(text=text, voice=voice, rate=rate, to=to):
        logger.trace("[START] Synthesizing speech.")
        if to == "audio_frame":
            result = _synthesize_af(text, voice, rate)
        elif to == "bytes":
            result = _synthesize_bytes(text, voice, rate)
        else:
            raise ValueError(f"Invalid value for 'to': {to}")
        logger.trace(f"synthesized speech: {type(result)}")
        assert isinstance(result, (av.AudioFrame, bytes, str))
        logger.trace("[END] Synthesizing speech.")
    return result

def _transcribe_audio_buffer(buf: io.BytesIO, language: str = None) -> str:
    logger.debug("Transcription has no timeout.")
    buf.name = 'dummy'
    transcript = openai.Audio.transcribe(
        OPENAI_TRANSCRIPTION_MODEL, buf, language=language
    )
    logger.debug(f"Transcript: {transcript}")
    return transcript["text"]

def _transcribe_audio_file(fp: Path | str, language: str = None) -> str:
    logger.trace(f"[START] Transcribing: {fp}")
    logger.debug("Transcription has no timeout.")
    with open(fp, "rb") as f:
        transcript = openai.Audio.transcribe(
            OPENAI_TRANSCRIPTION_MODEL, f, language=language
        )
    text = transcript['text']
    transcript.pop('text')
    with logger.contextualize(transcript=transcript.to_dict()):
        logger.log("TRANSCRIPT", shorten(text, 96))
    logger.trace(f"[END] Transcribing: {fp}")
    return text


def _transcribe_audio_frame(audio_frame: av.AudioFrame, language: str = None) -> str:
    buf = audio.af2wav(audio_frame)
    return _transcribe_audio_buffer(buf, language)

def _parse_to_iso639_1(language: str) -> str:
    iso = language.split("-")[0] if '-' in language else language
    lan = iso639.Language.match(iso)
    if lan is None:
        raise ValueError(f"Could not parse language: {language}")
    return lan.part1

@traced
def transcribe(aud: av.AudioFrame | str, language: str = None) -> str:
    """Transcribe audio to text. OpenAI requires ISO-639-1 ('en', 'es', 'fr', etc.).
    Args:
        - audio: either an AudioFrame or a storage id.
        - language: if provided, transcribe to that language; else, autodetect
    """
    logger.trace("[START] Transcribing audio.")
    if not language:
        logger.warning("Using language auto-detection; accuracy will be degraded.")
    secrets.login_openai()
    language = _parse_to_iso639_1(language)
    if isinstance(aud, av.AudioFrame):
        result = _transcribe_audio_frame(aud, language)
    elif isinstance(aud, str):
        with logger.contextualize(aud=aud):
            logger.trace("Retrieving audio from storage...")
            fn = audio.download(aud)
            with logger.contextualize(fn=fn):
                try:
                    logger.trace("Audio retrieved from storage.")
                    fp = Path(fn)
                    transcription = _transcribe_audio_file(fp, language)
                finally:
                    logger.trace("Removing temporary file.")
                    os.remove(fn)
        result = transcription.strip()
    else:
        raise ValueError(f"Invalid type for audio: {type(aud)}")
    logger.trace("[END] Transcribing audio.")
    return result

logger.success("Speech module loaded.")