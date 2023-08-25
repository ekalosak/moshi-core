import asyncio

import pytest

from moshi.utils import audio, speech

@pytest.mark.gcp
@pytest.mark.aio
def test_synthesize():
    msg = "Hello"
    loop = asyncio.get_event_loop()
    voice = loop.run_until_complete(speech.get_voice("en-US"))
    af = loop.run_until_complete(speech.synthesize(msg, voice))
    assert af.rate == 24000
    print(f"Test wav length: {audio.seconds(af)}")