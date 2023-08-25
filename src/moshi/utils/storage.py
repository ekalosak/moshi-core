from google.cloud import firestore
from loguru import logger

from moshi import GOOGLE_PROJECT
from moshi.core.base import Profile

client = firestore.AsyncClient(project=GOOGLE_PROJECT)
profiles = client.collection("profiles")

logger.success("Storage module loaded.")

async def get_profile(uid: str) -> Profile:
    """Get the user profile."""
    doc_ref = profiles.document(uid)
    doc = await doc_ref.get()
    if not doc.exists:
        raise ValueError(f"User profile not found: {uid}")
    profile = Profile(**doc.to_dict(), uid=uid)
    logger.trace(f"profile={profile}")
    return profile
