"""Manage user profiles."""
from google.cloud import firestore, exceptions
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
    """Create a new user in Firestore."""
    logger.trace(f"Creating user...")
    dr = client.collection("users").document(usr.uid)
    doc = dr.get()
    try:
        dr.create(usr.model_dump(exclude=["uid"]))
    except exceptions.Conflict:
        logger.trace(f"User already exists.")
        raise ValueError(f"User already exists: {usr.uid}")
    logger.trace(f"User created.")

def get_user(uid: str) -> User:
    """Get a user from Firestore."""
    logger.trace(f"Getting user...")
    dr = client.collection("users").document(uid)
    doc = dr.get()
    if not doc.exists:
        raise ValueError(f"User does not exist: {uid}")
    logger.trace(f"User found.")
    try:
        usr = User(uid=uid, **doc.to_dict())
    except Exception as e:
        logger.error(f"Error parsing user: {e}")
        logger.error(f"type: {type(e)}")
        raise e
    return usr