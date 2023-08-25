import pytest

from moshi import audio

@pytest.mark.asyncio
@pytest.mark.gcp
def test_synthesize(wavbytes):
    assert isinstance(wavbytes, bytes)
    assert len(wavbytes) > 0
    assert wavbytes.startswith(b"RIFF")
    assert wavbytes[20:24] == b"WAVE"
    assert wavbytes[24:28] == b"fmt "
    assert wavbytes[36:40] == b"data"
    assert wavbytes[40:44] == b"\x00\x00\x00\x00"