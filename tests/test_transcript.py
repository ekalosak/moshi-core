import os

import google.cloud.firestore as firestore
import pytest

from moshi import Message, Role, User
from moshi.core import transcript

db = firestore.Client(project=os.getenv("GCLOUD_PROJECT", "demo-test"))

@pytest.fixture
def user_fxt():
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


@pytest.fixture
def transcript_fxt(user_fxt):
    if not os.getenv("FIRESTORE_EMULATOR_HOST"):
        raise ValueError("FIRESTORE_EMULATOR_HOST not set")
    t = transcript.Transcript(
        activity_id="test",
        language="es-MX",
        native_language="en-US",
        user_id=user_fxt.uid,
        transcript_id="test",
    )
    doc_ref = db.collection("users").document(user_fxt.uid).collection("transcripts").document(t.tid)
    doc = doc_ref.get()
    if doc.exists:
        doc_ref.delete()
        print(f"deleted existing transcript: {doc.to_dict()}")
    writeresult = doc_ref.set(t.model_dump())
    print(f"added transcript={t} to db: {writeresult}")
    return t

@pytest.mark.skipif(os.getenv("FIRESTORE_EMULATOR_HOST") is None, reason="FIRESTORE_EMULATOR_HOST not set")
@pytest.mark.skipif(transcript.client.project != db.project, reason="Test client project does not match transcript client project")
def test_messages(transcript_fxt):
    t = transcript_fxt
    print("TRANSCRIPT")
    print(t.model_dump())
    msg1 = Message(body="Hello", role=Role.USR)
    msg2 = Message(body="Hi", role=Role.AST)
    for msg in [msg1, msg2]:
        print("ADD MSG")
        t.add_msg(msg)