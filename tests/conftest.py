import os

from google.cloud import firestore
import pytest

from moshi import User

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
    return firestore.Client(project=os.getenv("GCLOUD_PROJECT", "demo-test"))

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