from datetime import datetime

from moshi.core.activities import core, new

import pytest

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