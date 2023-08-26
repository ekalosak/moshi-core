"""Manage user profiles."""
from google.cloud import firestore, exceptions
from loguru import logger

from moshi import GOOGLE_PROJECT, VersionedModel

client = firestore.Client(project=GOOGLE_PROJECT)
logger.success("User module loaded.")

class User(VersionedModel):
    """Models the user profile."""
    uid: str
    name: str
    language: str

    def init_transcript(self, activity_id: str) -> firestore.DocumentReference:
        """Create a skeleton transcript document in Firestore."""
        usr_doc_ref = client.collection("users").document(self.uid)
        # check that the user exists
        usr_doc = usr_doc_ref.get()
        if not usr_doc.exists:
            raise ValueError(f"User does not exist: {self.uid}")
        # create the transcript
        transcript_doc_ref = usr_doc_ref.collection("transcripts").document()
        transcript_payload = {
            'aid': activity_id,
        }


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
    doc_ref = client.collection("users").document(uid)
    doc_snap = doc_ref.get()
    if not doc_snap.exists:
        raise ValueError(f"User does not exist: {uid}")
    logger.trace(f"User found.")
    try:
        usr = User(uid=uid, **doc_snap.to_dict())
    except Exception as e:
        logger.error(f"Error parsing user: {e}")
        logger.error(f"type: {type(e)}")
        raise e
    return usr