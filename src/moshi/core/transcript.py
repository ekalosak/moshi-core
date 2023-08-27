from datetime import datetime

from google.cloud import firestore
from loguru import logger

from moshi import Message, VersionedModel, __version__ as moshi_version

client = firestore.Client()

def skeleton(activity_id: str, language: str) -> dict:
    transcript_payload = {
        'activity_id': activity_id,
        'language': language,  # NOTE redundant by activity
        'messages': [],
        'created_at': datetime.now(),
        'moshi_version': moshi_version,
    }
    return transcript_payload

def _message_to_payload(msg: Message) -> dict:
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
        logger.trace(f"Converting audio name to int: {fn}")
        return int(fn.split('-')[0])

class Transcript(VersionedModel):
    activity_id: str
    language: str
    messages: list[Message]
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

    def add_msg(self, msg: Message):
        """Add a message to the transcript, saving it in Firestore."""
        with logger.contextualize(tid=self.tid, aid=self.aid):
            logger.trace("Adding message to transcript...")
            self.messages.append(msg)
            self.append_to_doc(msg)
            logger.trace("Message added to transcript.")

    def append_to_doc(self, msg: Message):
        """Save the transcript to Firestore."""
        transcript_col = client.collection("users").document(self.uid).collection("transcripts")
        if self.tid:
            logger.trace("Updating existing doc...")
            doc_ref = transcript_col.document(self.tid)
        else:
            logger.info("Creating new conversation document...")
            doc_ref = transcript_col.document()
            self.transcript_id = doc_ref.id
        with logger.contextualize(tid=self.tid, aid=self.aid):
            logger.trace(f"Saving conversation document...")
            payload = _message_to_payload(msg)
            doc_ref.update({"messages": firestore.ArrayUnion([payload])})
            logger.trace(f"Saved conversation document.")