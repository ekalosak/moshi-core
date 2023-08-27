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
            self.save()
            logger.trace("Message added to transcript.")


    def save(self):
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
            print(self.messages.asdict())
            doc_ref.set(self.messages.asdict())
            logger.trace(f"Saved conversation document!")