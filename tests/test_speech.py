import pytest

from moshi import speech

@pytest.mark.asyncio
@pytest.mark.gcp
def test_synthesize():
    msg = "Hello world"
    voice = speech.get_voice("en-US")
    audio_bytes = speech.synthesize_speech_bytes(msg, voice)
    assert isinstance(audio_bytes, bytes)
    assert len(audio_bytes) > 0
    assert audio_bytes.startswith(b"RIFF")
    assert audio_bytes[20:24] == b"WAVE"
    assert audio_bytes[24:28] == b"fmt "
    assert audio_bytes[36:40] == b"data"
    assert audio_bytes[40:44] == b"\x00\x00\x00\x00"