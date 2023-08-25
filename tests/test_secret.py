import asyncio

import pytest

from moshi.utils import secrets

@pytest.mark.oai
@pytest.mark.aio
def test_sec():
    """Test secret retrieval."""
    loop = asyncio.get_event_loop()
    _ = loop.run_until_complete(secrets.get_secret("openai-apikey-0"))