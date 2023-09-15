"""Operate the Activity using this module. Create, continue, and enrich the conversation.
The Activity is the main object in the system. It is the context for the user's conversation."""
from abc import ABC, abstractmethod
import os
from pathlib import Path
import tempfile
from textwrap import shorten
import random

from google.cloud import firestore
from google.cloud.firestore_v1 import FieldFilter
from loguru import logger

from moshi import Message, Role, VersionedModel, user, GCLOUD_PROJECT
from moshi.core import character, transcript
from moshi.utils import audio, speech
from moshi.utils.audio import AUDIO_BUCKET
from moshi.utils.log import traced

db = firestore.Client(project=GCLOUD_PROJECT)

@traced
def sample_activity_id(activity_type: str, level: int, latest=True):
    """Get a random activity id for the given type and <= level.
    If latest==True, get the latest matching lesson id.
    Otherwise, get a random matching lesson id.
    """
    activity_col = db.collection('activities')
    query = activity_col.where(filter=FieldFilter('type', '==', activity_type)).where(filter=FieldFilter('config.level', '<=', level)).order_by('config.level', direction=firestore.Query.DESCENDING).limit(10)
    docs = list(query.stream())
    for doc in docs:
        logger.debug(f"Found activity: {doc.id}")
    if not docs:
        raise ValueError(f"No activities found for type: {activity_type} and level: {level}")
    if latest:
        doc = sorted(docs, key=lambda d: d.get('created_at'), reverse=True)[0]
        logger.debug(f"Latest activity: {doc.get('created_at')} {doc.id}")
    else:
        doc = random.choice(docs)
        logger.debug(f"Random activity: {doc.get('created_at')} {doc.id}")
    return doc.id

class BaseActivity(ABC, VersionedModel):
    """An Activity provides access to the content required for a user session.
    Typically create an instance with start() or load().
    Related artifacts:
    - transcript doc
        - get
        - create
    - activity doc
        - get
        - ensure translation
    """

    user: user.User

    _activity_id: str = None
    _character: character.Character = None
    _transcript: transcript.Transcript = None
    _translations: dict[str, dict] = None

    @traced
    @abstractmethod
    def _translate_activity(self):
        """Translate the activity into the user's language.
        Subclasses must initialize the _translations attribute and set the translations in the activity doc:
        self.doc.set({"translations": self._translations})
        """
        pass

    @property
    @traced
    @abstractmethod
    def prompt(self) -> list[Message]:
        """Get the prompt for this activity."""
        pass

    @property
    def doc(self) -> firestore.DocumentReference:
        return db.collection("activities").document(self._activity_id)

    @property
    def messages(self) -> list[Message] | None:
        try:
            return self._transcript.messages
        except AttributeError:
            return None

    @property
    def language(self) -> str:
        return self.user.language

    @property
    def voice(self) -> str | None:
        try:
            return self._character.voice
        except AttributeError:
            return None

    @property
    def aid(self) -> str | None:
        return self._activity_id

    @property
    def tid(self) -> str | None:
        """Get the transcript id."""
        try:
            return self._transcript.transcript_id
        except AttributeError as e:
            logger.error(e)
            return None

    @property
    def uid(self) -> str:
        return self.user.uid

    @traced
    def _load_activity_content(self):
        doc = self.doc.get()
        trans = doc.to_dict()["translations"]
        logger.debug(f"trans={trans}")
        self._translations = trans

    @traced
    def _ensure_translation(self) -> bool:
        """Ensure that the activity has a translation for the given language.
        _init_activity_content() must be called first.
        Args:
            language: The language code, bcp47.
        """
        with logger.contextualize(language=self.user.language):
            if self.user.language in self._translations:
                logger.debug("Translation already exists.")
                return False
            logger.info("Translating activity.")
            self._translate_activity()
            logger.success(f"Translated activity in Firestore for {self.__class__.__name__}.")

    @traced
    def _load_transcript(self, transcript_id: str):
        """Retrieve an existing transcript doc from Firestore.
        Side effects:
            - sets the _transcript attribute
        Raises:
            google.cloud.exceptions.NotFound: If the transcript does not exist.
        """
        with logger.contextualize(transcript_id=transcript_id):
            logger.debug(f"Getting transcript doc for user: {self.user.uid}")
            doc = db.collection("users").document(self.user.uid).collection("transcripts").document(transcript_id).get()
            self._transcript = transcript.Transcript(**doc.to_dict(), transcript_id=doc.id, user_id=self.user.uid)
            self._activity_id = self._transcript.aid
            logger.debug(f"Loaded transcript: {shorten(str(self._transcript), 96)}")

    @traced
    def _init_transcript(self):
        """Create a skeleton transcript document in Firestore for the user.
        Side effects:
            - sets the _transcript attribute
        Raises:
            google.cloud.exceptions.NotFound: If the user does not exist.
        """
        logger.debug(f"Getting transcript doc for user: {self.user.uid}")
        doc = db.collection("users").document(self.user.uid).collection("transcripts").document()
        tdict = transcript.skeleton(self.aid, self.user.language, self.user.native_language)
        doc.set(tdict)
        with logger.contextualize(transcript_id=doc.id):
            logger.info(f"Initialized transcript.")
            self._transcript = transcript.Transcript(**tdict, transcript_id=doc.id) 
            logger.debug(f"_transcript={self._transcript}")

    @traced
    def _load_character(self):
        """Initialize the character for this activity."""
        if self._character:
            logger.warning(f"Character already loaded: {self._character}")
        self._character = character.Character.from_language(self.user.language)

    @traced
    def start(self, activity_id: str):
        """Start a new activity for the user.
        - initialize the transcript doc
        - create the translation in the activity doc if necessary
        - return the activity
        """
        self._activity_id = activity_id
        self._load_character()
        self._load_activity_content()
        self._ensure_translation()
        self._init_transcript()

    @traced
    def load(self, transcript_id: str):
        """Load an existing activity for the user.
        - load the transcript
        - load the activity content
        - return the activity
        """
        self._load_character()
        self._load_transcript(transcript_id)
        self._load_activity_content()
        if self._ensure_translation():
            logger.warning(f"Created new translation for ongoing activity: {self._aid}")

    @traced
    def respond(self, usr_audio_storage_name: str) -> str:
        """Main loop iter. From the user's audio, transcribe it, get the character's response, and synthesize it to audio.
        Returns:
            The storage id for the character's response audio.
        """
        logger.trace(f"Responding to: {usr_audio_storage_name}")
        usr_audio_gsid = f"gs://{AUDIO_BUCKET}/{usr_audio_storage_name}"
        try:
            usr_txt = speech.transcribe(usr_audio_gsid, self.language)
        except Exception as e:  # TODO make this specific
            logger.error(f"Audio not found: {e}")
            # TODO ensure this is disabled in production
            # if ENV != "dev":
            #     raise
            logger.warning("Trying local storage emulator.")
            suf = Path(usr_audio_storage_name).suffix
            tmp = None
            try:
                tmp = audio.download(usr_audio_storage_name)
                with open(tmp, "rb") as f:
                    usr_audio_bytes = f.read()
                usr_txt = speech.transcribe(usr_audio_bytes, self.language)
            finally:
                if tmp:
                    os.remove(tmp)
        assert isinstance(usr_txt, str)
        usr_msg = Message(role=Role.USR, body=usr_txt, audio={'path': usr_audio_storage_name, 'bucket': AUDIO_BUCKET})
        logger.debug(f"Adding usr_msg to transcript ({self._transcript})")
        self._transcript.add_msg(usr_msg)
        messages = self.prompt + self._transcript.messages
        logger.trace(f"Prompt + transcript have n messages: {len(messages)}")
        ast_txt = self._character.complete(messages)
        assert len(ast_txt) == 1, "Character response should be a single message."
        ast_txt = ast_txt[0]
        assert isinstance(ast_txt, str), "Character response should be a string."
        ast_audio_bytes = speech.synthesize(ast_txt, self.voice, to="bytes")
        ast_audio_storage_name = audio.make_ast_audio_name(usr_audio_storage_name)
        _, ast_audio_file = tempfile.mkstemp(suffix=".wav", dir='/tmp')
        try:
            with open(ast_audio_file, "wb") as f:
                f.write(ast_audio_bytes)
            audio.upload(ast_audio_file, ast_audio_storage_name)
        finally:
            logger.trace(f"Removing temporary file: {ast_audio_file}")
            os.remove(ast_audio_file)
        ast_msg = Message(role=Role.AST, body=ast_txt, audio={'path': ast_audio_storage_name, 'bucket': AUDIO_BUCKET})
        self._transcript.add_msg(ast_msg)  # NOTE sequence add_msg so the msgs arrive in order (for async)
        logger.trace(f"Responded to: {usr_audio_storage_name}")
        return ast_audio_storage_name