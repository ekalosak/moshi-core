import os

from google.cloud import texttospeech as tts
import pytest

from moshi.utils import audio, speech

@pytest.mark.gcp
def test_synthesize():
    msg = "Hello"
    voice = speech.get_voice("en-US")
    af = speech.synthesize(msg, voice)
    assert af.rate == 24000
    print(f"Test wav length: {audio.seconds(af)}")

@pytest.mark.fs
@pytest.mark.parametrize("bcp47", ["es-MX", "zh-Hans-CN", "en-US", "yue-Hant-HK", "ar-AE"])
def test_list_voices(bcp47):
    if not os.environ.get("FIRESTORE_EMULATOR_HOST"):
        pytest.skip("Skipping test because emulator not running; set the FIRESTORE_EMULATOR_HOST environment variable to run this test.")
    voices = speech.list_voices(bcp47)
    assert len(voices) > 0
    assert all(isinstance(v, tts.Voice) for v in voices)

@pytest.mark.fs
@pytest.mark.parametrize("bcp47", ["es-MX", "zh-Hans-CN", "en-US", "yue-Hant-HK", "ar-AE"])
@pytest.mark.parametrize("ssml", ["MALE", "FEMALE"])
def test_get_voice(bcp47, ssml):
    if not os.environ.get("FIRESTORE_EMULATOR_HOST"):
        pytest.skip("Skipping test because emulator not running; set the FIRESTORE_EMULATOR_HOST environment variable to run this test.")
    voice = speech.get_voice(bcp47)
    assert isinstance(voice, tts.Voice)
    if bcp47.startswith("zh"):
        assert voice.name.startswith('cmn-CN'), "Language mismatch"
    else:
        assert voice.name.startswith(bcp47.split('-')[0]), "Language mismatch"