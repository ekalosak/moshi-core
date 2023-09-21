"""This module provides speech synthesis and transcription utilities.
"""
import os
import random
from textwrap import shorten

import av
from google.cloud import speech as stt
from google.cloud import texttospeech as tts
from firebase_admin.firestore import firestore
from loguru import logger

from moshi import GCLOUD_PROJECT
from moshi.utils import audio
from moshi.utils.log import traced

GOOGLE_SPEECH_SYNTHESIS_TIMEOUT = int(os.getenv("GOOGLE_SPEECH_SYNTHESIS_TIMEOUT", 5))
GOOGLE_VOICE_SELECTION_TIMEOUT = int(os.getenv("GOOGLE_VOICE_SELECTION_TIMEOUT", 5))
logger.info(f"GOOGLE_SPEECH_SYNTHESIS_TIMEOUT={GOOGLE_SPEECH_SYNTHESIS_TIMEOUT} GOOGLE_VOICE_SELECTION_TIMEOUT={GOOGLE_VOICE_SELECTION_TIMEOUT}")

logger.trace('[START] Loading clients...')
sclient = stt.SpeechClient()
client = tts.TextToSpeechClient()
db = firestore.Client(project=GCLOUD_PROJECT)
logger.trace('[END] Loading clients...')

class TranscriptionError(Exception):
    """Raised when transcription fails."""
    pass

def gender_match(g1: str, g2: tts.SsmlVoiceGender) -> bool:
    if g1.lower() not in ("male", "female"):
        raise ValueError(f"SSML Gender not yet supported: {g1}")
    if g1.lower() == "female" and g2 == 2:
        return True
    elif g1.lower() == "male" and g2 == 1:
        return True
    else:
        return False


@traced
def list_voices(bcp47: str) -> list[tts.Voice]:
    """List all voices supported by ChatMoshi. Retrieve them from the Firebase document /config/voices.
    If that doc doesn't exist, then list all voices from Google Cloud Text-to-Speech.
    Args:
        - lan: if provided, filter by language code. It must be a BCP 47 language code e.g. "en-US" https://www.rfc-editor.org/rfc/bcp/bcp47.txt
    """
    logger.debug(f"Listing voices for language: {bcp47}")
    try:
        doc = db.collection("config").document("voices").get()
        assert doc.exists, "Voices document doesn't exist."
        _voices = doc.to_dict()[bcp47]
        voices = [tts.Voice(
            name=name,
            ssml_gender=model['ssml_gender'],
            natural_sample_rate_hertz=24000,
            language_codes=[bcp47],
        ) for name, model in _voices.items()]
    except (IndexError, AssertionError) as exc:
        logger.error(f"Failed to get voices from Firebase: {exc}")
        response = client.list_voices(language_code=bcp47, timeout=GOOGLE_VOICE_SELECTION_TIMEOUT)
        voices = response.voices
    return voices

def get_voice(bcp47: str, gender="FEMALE", model="Standard", random_choice=False) -> str:
    """Get a valid voice for the language. Just picks the first match.
    Args:
        - bcp47: Language code in BPC 47 format e.g. "en-US" https://www.rfc-editor.org/rfc/bcp/bcp47.txt
        - gender: SSML Gender
        - model: Voice model class (e.g. "Standard", "WaveNet")
        - random_choice: if True, pick a random voice from the list of matches. If False, pick the first match.
    Raises:
        - ValueError if no voice found.
    Source:
        - https://cloud.google.com/text-to-speech/pricing for list of valid voice model classes
    """
    logger.debug(f"Getting voice for: {bcp47}")
    voices = list_voices(bcp47)
    logger.debug(f"Language {bcp47} has {len(voices)} supported voices.")
    model_matches = []
    for voice in voices:
        if model.lower() in voice.name.lower():
            model_matches.append(voice)
    if len(model_matches) == 0:
        logger.warning(f"No voice found for model={model}, using any model.")
        model_matches = voices
    gender_matches = []
    for voice in model_matches:
        if gender_match(gender, voice.ssml_gender):
            gender_matches.append(voice)
    if len(gender_matches) == 0:
        logger.warning(f"No voice found for gender={gender}, using any model.")
        gender_matches = model_matches
    voices = gender_matches
    if len(voices) > 0:
        voice = random.choice(voices)
        logger.debug(f"Found voice: ({voice.name} {voice.ssml_gender})")
        return voice
    raise ValueError(f"Voice not found for {bcp47}, gender={gender}, model={model}")


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
        if to == "audio_frame":
            result = _synthesize_af(text, voice, rate)
        elif to == "bytes":
            result = _synthesize_bytes(text, voice, rate)
        else:
            raise ValueError(f"Invalid value for 'to': {to}")
        logger.trace(f"synthesized speech: {type(result)}")
        assert isinstance(result, (av.AudioFrame, bytes, str))
    return result

@traced
def transcribe(aud: str | bytes, bcp47: str) -> str:
    """Transcribe audio to text using Google Cloud Speech-to-Text.
    Args:
        - aud: audio GCP Storage path  e.g. "gs://moshi-audio/activities/1/1/1.wav"
        - bcp47: BCP 47 language code e.g. "en-US" https://www.rfc-editor.org/rfc/bcp/bcp47.txt
    Notes:
        - https://cloud.google.com/speech-to-text/docs/error-messages
            - "Invalid recognition 'config': bad encoding"
        - https://cloud.google.com/speech-to-text/docs/troubleshooting#returns_an_empty_response
            - Usually it's the emulator's mic being disabled...
    """
    with logger.contextualize(aud=aud if isinstance(aud, str) else 'bytes ommitted', bcp47=bcp47):
        if isinstance(aud, str):
            config = stt.RecognitionConfig(language_code=bcp47)
            audio = stt.RecognitionAudio(uri=aud)
        elif isinstance(aud, bytes):
            config = stt.RecognitionConfig(
                # NOTE wav and flac get encoding and sample rate from the file headers.
                # encoding=stt.RecognitionConfig.AudioEncoding.LINEAR16,
                # sample_rate_hertz=16000,
                language_code=bcp47,
            )
            audio = stt.RecognitionAudio(content=aud)
        else:
            raise TypeError(f"Invalid type for 'aud': {type(aud)}")
        logger.debug(f"RecognitionConfig: type(aud)={type(aud)} config={config}")
        logger.debug(f"RecognitionAudio: {audio if isinstance(aud, str) else 'bytes: ommitted'}")
        response = sclient.recognize(config=config, audio=audio)
        logger.debug(f"response={response}")
        try:
            text = response.results[0].alternatives[0].transcript
            conf = response.results[0].alternatives[0].confidence
        except IndexError as exc:
            logger.debug(exc)
            logger.error("No transcription found. Usually this means silent audio, but it could be corrupted audio.")
            text = "👂❌ We couldn't hear you. Please ensure your microphone is enabled, and try holding the button down for 1/2 sec before you speak."
            conf = 1.0
        with logger.contextualize(confidence=conf):
            logger.log("TRANSCRIPT", shorten(text, 96))
        return text

logger.success("Speech module loaded.")