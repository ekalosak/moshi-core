import pytest

@pytest.fixture
def wavbytes():
    with open('tests/data/hello.wav', 'rb') as f:
        return f.read()

@pytest.fixture
def m4abytes():
    with open('tests/data/hello.m4a', 'rb') as f:
        return f.read()