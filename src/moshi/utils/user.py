# Filter users by the table authorized_users in Firestore.
import contextvars

from google.cloud import firestore
from loguru import logger

from moshi.core.gcloud import GOOGLE_PROJECT

gdbclient = contextvars.ContextVar("gdbclient")

logger.success("Loaded!")


def _setup_client():
    """Set the gdbclient ContextVar."""
    try:
        gdbclient.get()
        logger.debug("Firestore client already exists.")
    except LookupError:
        logger.debug("Creating Firestore client...")
        client = firestore.AsyncClient(project=GOOGLE_PROJECT)
        gdbclient.set(client)
        logger.info("Firestore client initialized.")


def _get_client() -> "Client":
    """Get the translation client."""
    _setup_client()
    return gdbclient.get()
