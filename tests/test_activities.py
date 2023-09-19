from moshi import User
from moshi.core.activities import core, new

import pytest

# def activity(user_fxt, db):
#     doc_ref = db.collection("activities").document("test")
#     doc = doc_ref.get()
#     if doc.exists:
#         doc_ref.delete()
#         print(f"deleted existing transcript: {doc.to_dict()}")
#     writeresult = doc_ref.set(t.model_dump())
#     print(f"added transcript={t} to db: {writeresult}")
#     return t

# @pytest.mark.parametrize("activity_type, name", [("unstructured", None), ("lesson", "introdcutions")])
@pytest.mark.parametrize("activity_type, name", [("unstructured", None)])
def test_new(activity_type, name, user_fxt, db):
    a = new(activity_type, user_fxt, name=name)
    assert isinstance(a, core.BaseActivity)
    assert a.__class__.__name__.lower() == activity_type
    # get the activity from the db
    doc = db.collection("activities").document(a.aid).get()