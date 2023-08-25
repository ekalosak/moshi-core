from google.cloud import firestore
from loguru import logger

from moshi import GOOGLE_PROJECT
from moshi.core.base import Profile

logger.debug("Creating Firestore client...")
firestore_client = firestore.AsyncClient(project=GOOGLE_PROJECT)
logger.info(f"Firestore client initialized.")


async def get_profile(uid: str) -> Profile:
    """Get the user profile."""
    collection_ref = firestore_client.collection("profiles")
    doc_ref = collection_ref.document(uid)
    doc = await doc_ref.get()
    if not doc.exists:
        raise ValueError(f"User profile not found: {uid}")
    profile = Profile(**doc.to_dict(), uid=uid)
    logger.trace(f"User profile: {profile}")
    return profile
