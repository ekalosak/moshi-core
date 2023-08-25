import asyncio
import os
import textwrap
import tempfile

import openai
from av import AudioFrame
from google.cloud import texttospeech
from google.cloud.texttospeech import Voice
from loguru import logger

from . import audio
from moshi.utils import secrets

GOOGLE_SPEECH_SYNTHESIS_TIMEOUT = int(os.getenv("GOOGLE_SPEECH_SYNTHESIS_TIMEOUT", 5))
logger.info(f"Using speech synth timeout: {GOOGLE_SPEECH_SYNTHESIS_TIMEOUT}")
GOOGLE_VOICE_SELECTION_TIMEOUT = int(os.getenv("GOOGLE_VOICE_SELECTION_TIMEOUT", 5))
logger.info(f"Using language detection timeout: {GOOGLE_VOICE_SELECTION_TIMEOUT}")
OPENAI_TRANSCRIPTION_MODEL = os.getenv("OPENAI_TRANSCRIPTION_MODEL", "whisper-1")
logger.info(f"Using transcription model: {OPENAI_TRANSCRIPTION_MODEL}")

client = texttospeech.TextToSpeechClient()

logger.success("Loaded!")

def gender_match(g1: str, g2: 'SsmlVoiceGender') -> bool:
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
    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(client.list_voices, language_code=langcode),
            timeout=GOOGLE_VOICE_SELECTION_TIMEOUT,
        )
    except Exception as e:
        logger.error(e)
        raise
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


async def _synthesize_speech_bytes(text: str, voice: Voice, rate: int = 24000) -> bytes:
    """Synthesize speech to a bytestring in WAV (PCM_16) format.
    Implemented with texttospeech.googleapis.com;
    """
    synthesis_input = texttospeech.SynthesisInput(text=text)
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16,  # NOTE fixed s16 format
        sample_rate_hertz=rate,
    )
    langcode = voice.language_codes[0]
    logger.debug(f"Extracted language code from voice: {langcode}")
    voice_selector = texttospeech.VoiceSelectionParams(
        name=voice.name,
        language_code=langcode,
        ssml_gender=voice.ssml_gender,
    )
    logger.debug(
        f"Requesting speech synthesis: synthesis_input={synthesis_input}, voice_selector={voice_selector}, audio_config={audio_config}"
    )
    request = dict(
        input=synthesis_input,
        voice=voice_selector,
        audio_config=audio_config,
    )
    response = await asyncio.wait_for(
        asyncio.to_thread(
            client.synthesize_speech,
            request=request,
        ),
        timeout=GOOGLE_SPEECH_SYNTHESIS_TIMEOUT,
    )
    logger.debug(
        f"Got response from texttospeech.synthesize_speech: {textwrap.shorten(str(response.audio_content), 32)}"
    )
    return response.audio_content


async def synthesize(text: str, voice: Voice, rate: int = 24000) -> AudioFrame:
    audio_bytes = await _synthesize_speech_bytes(text, voice, rate)
    assert isinstance(audio_bytes, bytes)
    audio_frame = audio.wav_bytes_to_audio_frame(audio_bytes)
    assert isinstance(audio_frame, AudioFrame)
    return audio_frame


async def transcribe(audio_frame: AudioFrame, language: str = None) -> str:
    await secrets.login_openai()
    _, fp = tempfile.mkstemp(suffix=".wav")
    try:
        audio.write_audio_frame_to_wav(audio_frame, fp)
        with open(fp, "rb") as f:
            transcript = await openai.Audio.atranscribe(
                OPENAI_TRANSCRIPTION_MODEL, f, language=language
            )
    finally:
        os.remove(fp)
    return transcript["text"]
