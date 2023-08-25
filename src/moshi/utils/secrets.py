import asyncio
import functools
import os

from google.cloud import secretmanager
from loguru import logger
import openai

from moshi import GOOGLE_PROJECT

SECRET_TIMEOUT = os.getenv("MOSHISECRETTIMEOUT", 2)
OPENAI_APIKEY_SECRET = os.getenv("OPENAI_APIKEY_SECRET", "openai-apikey-0")
logger.info(f"OPENAI_APIKEY_SECRET={OPENAI_APIKEY_SECRET} SECRET_TIMEOUT={SECRET_TIMEOUT}")

client = secretmanager.SecretManagerServiceAsyncClient()
logger.success("Secrets module loaded.")

functools.lru_cache(maxsize=8)
async def get_secret(
    secret_id: str,
    project_id=GOOGLE_PROJECT,
    version_id: str | None = None,
    decode: str | None = "UTF-8",
) -> str | bytes:
    """Get a secret from the secrets-manager. If version is None, get latest."""
    logger.debug(f"Getting secret: {secret_id}")
    version_id = version_id or "latest"
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    logger.debug(f"Constructed name: {name}")
    response = await asyncio.wait_for(
        client.access_secret_version(request={"name": name}),
        timeout=SECRET_TIMEOUT,
    )
    logger.info(f"Retrieved secret: {response.name}")
    if decode is not None:
        secret = response.payload.data.decode(decode)
    else:
        secret = response.payload.data
    logger.trace(f"Secret length: {len(secret)}")
    logger.trace(f"Secret type: {type(secret)}")
    return secret

async def login_openai():
    if not openai.api_key:
        openai.api_key = await get_secret(OPENAI_APIKEY_SECRET)
        logger.info("Set OpenAI API key")