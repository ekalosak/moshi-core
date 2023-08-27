import asyncio

from google.cloud import firestore
from loguru import logger

try:
    firestore_client = firestore.AsyncClient()
except RuntimeError as e:
    logger.debug(f"RuntimeError: {e}")
    logger.warning("Couldn't initialize async client. Only expect this if your entrypoint is not asyncio.run().")
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    firestore_client = firestore.AsyncClient()
