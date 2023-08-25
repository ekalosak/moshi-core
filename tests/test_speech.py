import pytest

from moshi.utils import audio, speech

@pytest.mark.gcp
@pytest.mark.asyncio
async def test_synthesize():
    msg = "Hello"
    voice = await speech.get_voice("en-US")
    af = await speech.synthesize(msg, voice)
    assert af.rate == 24000
    print(f"Test wav length: {audio.seconds(af)}")