"""This module implements the core WebRTCChatter class for use in the WebRTC server."""
import asyncio
import itertools
import textwrap

import aiortc
from aiortc import RTCDataChannel
from aiortc.mediastreams import MediaStreamError
from av import AudioFrame
from loguru import logger

from moshi import (
    Message,
    Role,
    UserResetError,
    utils,
)
from moshi.core import activities
from moshi.utils import ctx
from . import (
    detector,
    responder,
    think,
)

MAX_RESPONSE_TOKENS = 64
MAX_LOOPS = 30
STOP_TOKENS = ["1:"]  # USER is 1, ASSISTANT is 2
UTT_START_MAX_COUNT = 2
assert MAX_LOOPS >= 0

logger.success("Loaded!")


class WebRTCAdapter:
    """This adapter connects WebRTC audio and signalling to the activity."""

    def __init__(self, activity_type: activities.ActivityType):
        self.__dc = None
        self.__dc_connected = asyncio.Event()
        self.__task = None
        self.__utt_start_count = 0
        self.act = activities.Activity(activity_type=activity_type)
        self.detector = (
            detector.UtteranceDetector()
        )  # get_utterance: track -> AudioFrame
        self.responder = (
            responder.ResponsePlayer()
        )  # play_response: AudioFrame -> track

    def __send(self, msg: str):
        """Send msg over dc with best effort."""
        # NOTE RTCDataChannel.send() does aio via ensure_future.
        # source: https://github.com/aiortc/aiortc/blob/main/src/aiortc/rtcsctptransport.py#L1796
        logger.trace("sending: " + msg)
        if not self.__dc:
            logger.warning(
                f"tried to send before dc connected, discarding message: {msg}"
            )
            return
        self.__dc.send(msg)

    def _send_status(self, status: str):
        self.__send(f"status {status}")

    def _send_info(self, var: str, val: str):
        assert " " not in var, "var cannot contain spaces"
        self.__send(f"info {var} {val}")

    def _send_error(self, err: str):
        logger.error("Sending error to user: " + err)
        self.__send("error " + err)

    def _send_transcript(self, msg: Message):
        if msg.role == Role.SYS:
            raise ValueError(
                f"{msg.role} not supported user-facing transcript Role, must be USR or AST"
            )
        self.__send("transcript " + f"{msg.role.value} {msg.content}")

    async def _speak_to_user(self, text: str):
        """Speak to the user over audio channel.
        Use the user's configured language, and provide some variety in phrasing.
        """
        logger.warning("TODO")
        await asyncio.sleep(0)

    async def start(self):
        if self.__task:
            logger.debug("Already started, no-op.")
            return
        self.__task = asyncio.create_task(self.__run(), name="Main chat task")
        logger.debug("Awaiting component startup...")
        results = await asyncio.gather(
            self.act.start(), self.wait_dc_connected(), return_exceptions=True
        )
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Task {i} raised exception: {result}")
                raise result

        logger.success("WebRTC Adapter started")
        self._send_status("start")
        self._send_info("tid", self.act.cid)

    async def stop(self):
        if self.__task == None:
            logger.warning("Already stopped, no-op.")
        try:
            self._send_status("stop")
        except aiortc.exceptions.InvalidStateError as e:
            logger.debug("dc already closed, no-op.")
        self.__task.cancel(f"{self.__class__.__name__}.stop() called")
        results = await asyncio.gather(
            self.act.stop(), self.__task, return_exceptions=True
        )
        self.__task = None
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Task {i} raised exception: {result}")
        logger.info("Stopped")

    async def wait_dc_connected(self):
        logger.trace("pc connected, awaiting dc...")
        await asyncio.wait_for(self.__dc_connected.wait(), timeout=2)
        logger.trace("dc connected.")

    def add_dc(self, dc: RTCDataChannel):
        if self.__dc is not None:
            raise ValueError("DataChannel already set")
        self.__dc = dc
        self.__dc_connected.set()
        logger.success(f"dc connected: {dc.label}:{dc.id}")

    @property
    def voice(self) -> object:
        return self.act.voice

    @property
    def language(self) -> str:
        return self.act.lang

    @property
    def user_utterance(self) -> str:
        """The latest user utterance."""
        return self.__latest_msg(Role.USR).content

    @property
    def assistant_utterance(self) -> str:
        """The latest assistant utterance."""
        return self.__latest_msg(Role.AST).content

    @property
    def messages(self) -> list[Message]:
        return self.act.messages

    def __latest_msg(self, role: Role) -> Message:
        for msg in self.messages[::-1]:
            if msg.role == role:
                return msg
        raise ValueError(f"No {role.value} utterances in messages")

    async def __run(self):
        """Run the main program loop."""
        utils.log.splash("moshi")
        await self.__dc_connected.wait()
        self._send_status("hello")
        for i in itertools.count():
            if i == MAX_LOOPS and MAX_LOOPS != 0:
                msg = f"Reached MAX_LOOPS={MAX_LOOPS}, i={i}"
                logger.info(msg)
                self._send_status("maxlen", msg)
                break
            logger.debug(f"Starting loop {i}")
            with logger.contextualize(i=i):
                self._send_status("loopstart")
            try:
                await self.__main()
            except UserResetError as e:
                self._send_error(str(e))
                self._send_status("bye")
                break
            except MediaStreamError:
                logger.info("User hung up (disconnect).")
                break
            except asyncio.CancelledError as e:
                logger.info("Cancelled.")
                break
            except aiortc.exceptions.InvalidStateError as e:
                logger.info("DataChannel closed.")
                break
            except Exception as e:
                import traceback

                logger.error(f"Caught unexpected exception: {type(e)} {e}")
                logger.error(traceback.format_exc())
                self._send_error("internal")
                break
        utils.log.splash("bye")

    async def __main(self):
        """Run one loop of the main program.
        Raises:
            - UserResetError when chatter entered into a state that requires reset by user.
            - MediaStreamError when connection error or user hangup (disconnect).
        """
        self._send_status("listening")
        try:
            # Raises: MediaStreamError, TimeoutError, UtteranceTooLongError, UtteranceNotStartedError
            usr_audio: AudioFrame = await self.detector.get_utterance()
        except detector.UtteranceTooLongError as e:
            logger.debug("User utterance too long, prompting user to try again.")
            await self._send_error("utttoolong")
            return
        except detector.UtteranceNotStartedError as e:
            logger.trace(f"User didn't start speaking {self.__utt_start_count} times.")
            if self.__utt_start_count == UTT_START_MAX_COUNT:
                logger.trace("User considered inavtive, raising UserResetError.")
                raise UserResetError("usrNotSpeaking") from e
            logger.trace("Prompting user to try again.")
            await self._speak_to_user("Are you still there?")
            self.__utt_start_count += 1
            return

        self.__utt_start_count = 0
        self._send_status("transcribing")
        usr_text: str = await self.__transcribe_audio(
            usr_audio
        )  # TODO handle network errors
        usr_msg = self.__add_message(usr_text, Role.USR)
        self._send_transcript(usr_msg)
        self._send_status("thinking")
        ast_text: str = await self.__get_response()
        if ast_text:
            ast_msg = self.__add_message(ast_text, Role.AST)
            self._send_transcript(ast_msg)
            self._send_status("speaking")
            ast_audio: AudioFrame = (
                await self.__synth_speech()
            )  # TODO handle network errors
            logger.debug(f"Got assistant response audio: {ast_audio}, sending...")
            try:
                await self.responder.send_utterance(
                    ast_audio
                )  # TODO handle: Raises: MediaStreamError
            except asyncio.TimeoutError as e:
                logger.debug(f"TimeoutError: {e}")
                raise UserResetError("timeout") from e
        else:
            logger.warning("Got empty assistant response")
            raise UserResetError("empty assistant response")

    def __add_message(self, content: str, role: Role) -> Message:
        assert isinstance(content, str)
        if not isinstance(role, Role):
            role = Role(role)
        msg = Message(role=role, content=content)
        logger.trace(f"Adding message: {msg}")
        self.act.add_msg(msg)
        return msg

    async def __synth_speech(self, text: str = None) -> AudioFrame:
        msg = self.messages[-1]
        logger.debug(f"Synthesizing to speech: {msg}")
        assert msg.role == Role.AST
        frame = await utils.speech.synthesize(msg.content, self.voice)
        logger.debug(f"Speech synthesized: {frame}")
        assert isinstance(frame, AudioFrame)
        return frame

    async def __get_response(self):
        """Retrieve the chatbot's response to the user utterance."""
        logger.debug(f"Getting assistant response...")
        ast_txts: str = await think.completion_from_assistant(
            self.messages,
            n=1,
            max_tokens=MAX_RESPONSE_TOKENS,
            stop=STOP_TOKENS,
            user=ctx.user.get().uid,
        )
        assert len(ast_txts) == 1
        ast_txt = ast_txts[0]
        logger.debug(f"Got assistant response: {textwrap.shorten(ast_txt, 64)}")
        return ast_txt

    async def __transcribe_audio(self, audio, role=Role.USR):
        logger.debug(f"Transcribing {role.value} audio: {audio}")
        transcript: str = await utils.speech.transcribe(audio, language=self.language)
        logger.debug(
            f"Transcribed {role.value} utterance: {textwrap.shorten(transcript, 64)}"
        )
        return transcript
