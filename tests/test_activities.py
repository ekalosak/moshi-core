from datetime import datetime
import importlib
import os

from google.api_core.exceptions import InvalidArgument
from google.cloud import storage
import pytest

from moshi.core.activities import core, new

@pytest.fixture(params=[{"activity_type": "unstructured"}, {"activity_type": "lesson", "name": "introductions", "level": 1}])
def activity(request, db) -> str:
    """Put a dummy activity in the db, return its ID"""
    atp = request.param["activity_type"]
    anm = request.param.get("name", None)
    level = request.param.get("level", 0)
    did = "test-" + (atp if not anm else f"{atp}-{anm}")
    doc_ref = db.collection("activities").document(did)
    doc = doc_ref.get()
    if doc.exists:
        doc_ref.delete()
        print(f"deleted existing activity: {doc.to_dict()}")
    payload = {
        "created_at": datetime.now().astimezone(),
        "config": {
            "level": level,
        },
        "type": atp,
        "translations": {
            "es-MX": {
                "title": "Test",
                "character_prompt": "test",
                "user_prompt": "test",
                "goals": [],
                "vocabulary": [],
            }
        }
    }
    if anm:
        payload["config"].update({"topic": anm})
    doc_ref.set(payload)
    print(f"added activity={did} to db: {payload}")
    request.param["aid"] = did
    return request.param

def test_new(activity, user_fxt, db):
    atp = activity["activity_type"]
    anm = activity.get("name")
    try:
        a = new(atp, user_fxt, name=anm)
    except:
        print("ACTIVITIES IN DB:")
        for doc in db.collection("activities").stream():
            print(doc.id)
            from pprint import pprint
            pprint(doc.to_dict())
        raise
    assert isinstance(a, core.BaseActivity)
    assert a.__class__.__name__.lower() == atp

@pytest.mark.skipif(not os.getenv('STORAGE_EMULATOR_HOST'), reason="requires firebase storage emulator")
def test_respond(activity, user_fxt, usr_audio, store, db, monkeypatch):
    """Test the main functionality of the activities module, i.e. the 'core product'."""
    store: storage.Client
    monkeypatch.setattr('moshi.core.activities.core.db', db)
    monkeypatch.setattr('moshi.utils.audio.store', store)
    print(f"PATCHED ACTIVITY FIRESTORE CLIENT: {core.db.project}")
    print(f"ACTIVITY POST DATA: {activity} {user_fxt}")
    atp = activity["activity_type"]
    anm = activity.get("name")
    a = new(atp, user_fxt, name=anm)
    # TODO 1. upload a sample audio to storage at /audio/{user_id}/{transcript_id}/USR0.wav, USR0.flac
    # 2. call a.respond() with the transcript_id
    print("ACTIVITY CONTENTS:")
    print(a.model_dump())
    from pathlib import Path
    storage_path = f"audio/{user_fxt.uid}/{a.tid}/{usr_audio.with_stem('USR0').name}"
    print(f"UPLOADING {usr_audio} to {storage_path}")
    store.bucket("moshi-3.appspot.com").blob(storage_path).upload_from_filename(usr_audio)
    try:
        resp_sto_path = a.respond(storage_path)
    except InvalidArgument as exc:
        if usr_audio.suffix not in ('.wav', '.flac'):
            pytest.xfail("wav and flac only supported by Google TTS API")
        if "Must use single channel (mono)" in str(exc):
            pytest.xfail("mono only supported")
    print(f"RESPONSE STORED AT: {resp_sto_path}")
    import tempfile
    with tempfile.NamedTemporaryFile() as f:
        print(f"DOWNLOADING RESPONSE TO: {f.name}")
        store.bucket("moshi-3.appspot.com").blob(resp_sto_path).download_to_filename(f.name)