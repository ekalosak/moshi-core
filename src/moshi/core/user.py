"""Manage user profiles."""
from google.cloud import firestore
from loguru import logger
from pydantic import BaseModel

from moshi import GOOGLE_PROJECT

client = firestore.Client(project=GOOGLE_PROJECT)
logger.success("User module loaded.")

class User(BaseModel):
    """Models the user profile."""
    uid: str
    name: str
    lang: str

def create_user(usr: User):
    """Create a new user in the database."""
    dr = client.collection("users").document(usr.uid)
    doc = dr.get()
    if doc.exists:
        raise ValueError(f"User already exists: {usr.uid}")
    dr.set(usr.model_dump(exclude=["uid"]))
    dr.collection("transcripts").document("init").set({"init": True})

def get_user(uid: str):
    """Get a user from the database."""
    dr = client.collection("users").document(uid)
    doc = dr.get()
    if not doc.exists:
        raise ValueError(f"User does not exist: {uid}")
    return User(**doc.to_dict())