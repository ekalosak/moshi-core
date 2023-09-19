import os

import google.cloud.firestore as firestore
import pytest

from moshi import Message, Role, User
from moshi.core import transcript

@pytest.fixture
def transcript_fxt(user_fxt, db):
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

def test_skeleton():
    t = transcript.skeleton("test", "es-MX", "en-US")
    print(t)

def test_message_to_payload():
    msg = Message(body="Hello", role=Role.USR)
    payload = transcript.message_to_payload(msg)
    print(payload)
    assert isinstance(payload, dict)

def test_a2int():
    assert transcript.a2int("42-test.wav") == 42

@pytest.mark.skipif(os.getenv("FIRESTORE_EMULATOR_HOST") is None, reason="FIRESTORE_EMULATOR_HOST not set")
@pytest.mark.skipif(transcript.client.project != db.project, reason="Test client project does not match transcript client project")
def test_add_msg(transcript_fxt):
    t = transcript_fxt
    print("TRANSCRIPT CREATED:")
    print(t.model_dump())
    msg1 = Message(body="Hello", role=Role.USR)
    msg2 = Message(body="Hi", role=Role.AST)
    for msg in [msg1, msg2]:
        t.add_msg(msg)
    # check that the messages are in the transcript
    assert len(t.messages) == 2
    doc_ref = db.collection("users").document(t.uid).collection("transcripts").document(t.tid)
    doc = doc_ref.get()
    assert doc.exists
    print("TRANSCRIPT AFTER ROUND TRIP, FROM FB:")
    print(doc.to_dict())
    assert len(doc.get("messages")) == 2
    print("USR0:")
    print(doc.get("messages.USR0"))
    print("AST1:")
    print(doc.get("messages.AST1"))