import asyncio

import pytest

from moshi import Message, Role
from moshi.utils import comp

@pytest.mark.oai
@pytest.mark.aio
def test_completion():
    """Test completion."""
    msg = Message(content="Penguins are animals.", role=Role.USR)
    loop = asyncio.get_event_loop()
    completion = loop.run_until_complete(comp.from_assistant(msg))
    assert len(completion) == 1
    assert isinstance(completion[0], str)
    print(f"completion: {completion}")