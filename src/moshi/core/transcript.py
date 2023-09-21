from datetime import datetime

from google.cloud import firestore
from loguru import logger

from moshi import Message, VersionedModel, __version__ as moshi_version, GCLOUD_PROJECT
from moshi.utils.log import traced

client = firestore.Client(project=GCLOUD_PROJECT)

def skeleton(activity_id: str, language: str, native_language: str) -> dict:
    """Create a new transcript payload, languages are BCP-47 codes."""
    transcript_payload = {
        'activity_id': activity_id,
        'language': language,  # NOTE redundant by activity but useful for querying upon finalization etc.
        'native_language': native_language,
        'created_at': datetime.now(),
        'moshi_version': moshi_version,
    }
    return transcript_payload

def message_to_payload(msg: Message) -> dict:
    """Convert a list of messages to a list of dicts."""
    msg = msg.model_dump()
    if 'moshi_version' in msg:
        msg.pop('moshi_version')  # redundant, in transcript doc
    msg['role'] = msg['role'].value
    return msg

def a2int(audio_name: str) -> int:
    """Convert an audio name to an integer."""
    with logger.contextualize(audio_name=audio_name):
        fn = audio_name.split('/')[-1]
        return int(fn.split('-')[0])

class Transcript(VersionedModel):
    activity_id: str
    language: str
    messages: dict[str, Message] = {}
    transcript_id: str = None
    user_id: str = None

    @property
    def aid(self):
        return self.activity_id

    @property
    def tid(self):
        return self.transcript_id

    @property
    def uid(self):
        return self.user_id

    @traced
    def add_msg(self, msg: Message):
        """Add a message to the transcript, saving it in Firestore."""
        with logger.contextualize(tid=self.tid, aid=self.aid):
            key = f"{msg.role.name}{len(self.messages)}"
            self.messages[key] = msg
            self._append_to_doc(key)

    @traced
    def _append_to_doc(self, key: str):
        """Save the transcript to Firestore."""
        msg = self.messages[key]
        transcript_col = client.collection("users").document(self.uid).collection("transcripts")
        if self.tid:
            logger.debug("Updating existing doc.")
            doc_ref = transcript_col.document(self.tid)
        else:
            logger.info("Creating new conversation document.")
            doc_ref = transcript_col.document(self.transcript_id or None)
            self.transcript_id = self.transcript_id or doc_ref.id
        with logger.contextualize(tid=self.tid, aid=self.aid):
            logger.trace(f"[START] Saving conversation document.")
            payload = message_to_payload(msg)
            logger.debug(f"payload={payload}")
            # messages is {"AST0": {Message}, "USR1": {Message}, ...}
            # or with any all caps AST, USR, SYS, etc.
            key = f"{msg.role.name}{len(self.messages) - 1}"
            doc_ref.update({f"messages.{key}": payload})
            logger.trace(f"[END] Saving conversation document.")