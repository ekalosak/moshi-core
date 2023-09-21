import os
from pathlib import Path

from google.cloud import firestore
from google.cloud import storage
import pytest

from moshi import User

TEST_ROOT = Path(__file__).parent
DATA_DIR = TEST_ROOT / "data"

@pytest.fixture
def data_dir() -> Path:
    return DATA_DIR

AUDIO_FILES = [f for f in DATA_DIR.iterdir() if f.suffix in [".wav", ".m4a", ".flac"]]

@pytest.fixture(params=AUDIO_FILES)
def usr_audio(request) -> Path:
    return request.param

@pytest.fixture
def wavbytes():
    with open('tests/data/hello.wav', 'rb') as f:
        return f.read()

@pytest.fixture
def m4abytes():
    with open('tests/data/hello.m4a', 'rb') as f:
        return f.read()

@pytest.fixture
def db():
    if not os.getenv("FIRESTORE_EMULATOR_HOST"):
        raise ValueError("FIRESTORE_EMULATOR_HOST not set")
    return firestore.Client("demo-test")

@pytest.fixture
def store():
    """Firebase Storage client"""
    if not os.getenv("STORAGE_EMULATOR_HOST"):
        raise ValueError("STORAGE_EMULATOR_HOST not set")
    store = storage.Client("demo-test")
    return store

@pytest.fixture
def user_fxt(db):
    if not os.getenv("FIRESTORE_EMULATOR_HOST"):
        raise ValueError("FIRESTORE_EMULATOR_HOST not set")
    user = User(
        uid="test",
        name="test",
        email="test@dne.dne",
        language="es-MX",
        native_language="en-US",
    )
    # put it in emulator
    writeresult = db.collection("users").document(user.uid).set(user.model_dump())
    print(f"added user={user} to db: {writeresult}")
    return user