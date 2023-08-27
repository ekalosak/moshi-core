import asyncio
from datetime import datetime

from loguru import logger

from moshi import Message, VersionedModel, __version__ as moshi_version

def skeleton(activity_id: str, language: str) -> dict:
    transcript_payload = {
        'aid': activity_id,
        'language': language,  # NOTE redundant by activity
        'messages': [],
        'created_at': datetime.now(),
        'moshi_version': moshi_version,
    }
    return transcript_payload

class Transcript(VersionedModel):
    aid: str
    language: str
    messages: list[Message]
    tid: str = None

    async def add_msg(self, msg: Message):
        """Add a message to the transcript, saving it in Firestore."""
        with logger.contextualize(tid=self.tid, aid=self.aid):
            logger.trace("Adding message to transcript...")
            self.messages.append(msg)
            await self.__save()
            logger.trace("Message added to transcript.")

    async def __save(self):
        """Save the transcript to Firestore."""
        if self.tid:
            logger.info("Updating existing doc...")
            doc_ref = transcript_col.document(self.__cid)
        else:
            logger.info("Creating new conversation document...")
            doc_ref = transcript_col.document()
            self.__cid = doc_ref.id
        with logger.contextualize(cid=self.__cid):
            logger.debug(f"Saving conversation document...")
            try:
                await doc_ref.set(self.__transcript.asdict())
                logger.success(f"Saved conversation document!")
            except asyncio.CancelledError:
                logger.debug(f"Cancelled saving conversation document.")

