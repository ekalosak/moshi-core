import os

from google.auth import default
from google.cloud import secretmanager
from loguru import logger
import openai

SECRET_TIMEOUT = os.getenv("MOSHISECRETTIMEOUT", 2)
OPENAI_APIKEY_SECRET = os.getenv("OPENAI_APIKEY_SECRET", "openai-apikey-0")
_, GOOGLE_PROJECT = default()
logger.info(f"OPENAI_APIKEY_SECRET={OPENAI_APIKEY_SECRET} SECRET_TIMEOUT={SECRET_TIMEOUT} GOOGLE_PROJECT={GOOGLE_PROJECT}")

client = secretmanager.SecretManagerServiceClient()

# functools.lru_cache(maxsize=8)
def get_secret(
    secret_id: str,
    project_id=GOOGLE_PROJECT,
    version_id: str | None = None,
    decode: str | None = "UTF-8",
) -> str | bytes:
    """Get a secret from the secrets-manager. If version is None, get latest."""
    version_id = version_id or "latest"
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    with logger.contextualize(secret_id=secret_id, project_id=project_id, version_id=version_id, secret_name=name):
        logger.trace("Retrieving secret...")
        response = client.access_secret_version(request={"name": name}, timeout=SECRET_TIMEOUT)
        if decode is not None:
            secret = response.payload.data.decode(decode)
        else:
            secret = response.payload.data
        logger.trace(f"Retrieved secret: {type(secret)} {len(secret)}")
    return secret

def login_openai():
    if not openai.api_key:
        openai.api_key = get_secret(OPENAI_APIKEY_SECRET)
        logger.info("Set OpenAI API key")

logger.success("Secrets module loaded.")