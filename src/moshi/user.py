"""Manage user profiles."""
from datetime import datetime

from google.cloud import firestore, exceptions
from loguru import logger

from moshi import VersionedModel, ParseError
from moshi.utils.storage import firestore_client as client

class User(VersionedModel):
    """Models the user profile."""
    uid: str
    name: str
    language: str
    native_language: str

async def create_doc(usr: User):
    """Create a new user in Firestore."""
    logger.trace(f"Creating user...")
    doc_ref = client.collection("users").document(usr.uid)
    try:
        await doc_ref.create(usr.model_dump(exclude=["uid"]))
    except exceptions.Conflict:
        logger.trace(f"User already exists.")
        raise ValueError(f"User already exists: {usr.uid}")
    logger.trace(f"User created.")

async def get_user(uid: str) -> User:
    """Get a user from Firestore."""
    logger.trace(f"Getting user...")
    doc_ref = client.collection("users").document(uid)
    doc_snap = await doc_ref.get()
    if not doc_snap.exists:
        raise ValueError(f"User does not exist: {uid}")
    logger.trace(f"User found: {doc_snap.to_dict()['name']}")
    try:
        usr = User(uid=uid, **doc_snap.to_dict())
    except Exception as e:
        raise ParseError("Error parsing user") from e
    return usr

logger.success("User module loaded.")
