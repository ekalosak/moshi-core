import asyncio

import pytest

from moshi import Message, Role
from moshi.utils import comp

@pytest.mark.oai
@pytest.mark.aio
def test_completion():
    """Test completion."""
    msg = Message(content="Hello, world!", role=Role.USR)
    completion = asyncio.run(comp.from_assistant(msg))
    assert len(completion) == 1
    assert isinstance(completion[0], str)
    print(f"completion: {completion}")