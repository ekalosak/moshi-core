"""Manage user profiles."""
from datetime import datetime

from google.cloud import firestore, exceptions
from loguru import logger

from moshi import GOOGLE_PROJECT, VersionedModel
from moshi.core import transcript

client = firestore.Client(project=GOOGLE_PROJECT)
logger.success("User module loaded.")

class User(VersionedModel):
    """Models the user profile."""
    uid: str
    name: str
    language: str
    native_language: str

def create_doc(usr: User):
    """Create a new user in Firestore."""
    logger.trace(f"Creating user...")
    doc_ref = client.collection("users").document(usr.uid)
    try:
        doc_ref.create(usr.model_dump(exclude=["uid"]))
    except exceptions.Conflict:
        logger.trace(f"User already exists.")
        raise ValueError(f"User already exists: {usr.uid}")
    logger.trace(f"User created.")

def get_user(uid: str) -> User:
    """Get a user from Firestore."""
    logger.trace(f"Getting user...")
    doc_ref = client.collection("users").document(uid)
    doc_snap = doc_ref.get()
    if not doc_snap.exists:
        raise ValueError(f"User does not exist: {uid}")
    logger.trace(f"User found: {doc_snap.to_dict()['name']}")
    try:
        usr = User(uid=uid, **doc_snap.to_dict())
    except Exception as e:
        logger.error(f"Error parsing user: {e}")
        logger.error(f"type: {type(e)}")
        raise e
    return usr