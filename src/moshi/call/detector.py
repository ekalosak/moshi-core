""" This module provides the UtteranceDetector class that detects and extracts natural language utterances from audio
tracks.
"""
import asyncio
import time
from typing import Callable

from aiortc import MediaStreamTrack
from aiortc.mediastreams import MediaStreamError
from av import AudioFifo, AudioFrame
from loguru import logger

from moshi import audio

UTT_START_TIMEOUT_SEC = (
    5.0  # wait for the user to start speaking for this long before giving up.
)
# TODO tune the UTT_END_TIMEOUT_SEC param for typical network conditions.
UTT_END_TIMEOUT_SEC = 0.08  # when there's a gap of this length between frames, consider the utterance ended.
UTT_MAX_LEN_SEC = 25.0  # maximum length of an utterance.

logger.success("Loaded!")


class UtteranceTooLongError(Exception):
    ...


class UtteranceNotStartedError(Exception):
    ...


class UtteranceDetector:
    """An audio media sink that detects utterances."""

    def __init__(self):
        self.__fifo = AudioFifo()
        self.__track = None
        logger.debug("Initialized")

    def setTrack(self, track: MediaStreamTrack):
        """Set the audio track to listen to."""
        if track.kind != "audio":
            raise ValueError(
                f"Non-audio tracks not supported, got track: {audio.track_str(track)}"
            )
        if track.readyState != "live":
            raise ValueError(
                f"Non-live tracks not supported, got track: {audio.track_str(track)}"
            )
        if self.__track is not None:
            logger.warning(f"Track already set: {audio.track_str(self.__track)}")
        self.__track = track
        logger.debug("Track set")

    async def get_utterance(self) -> AudioFrame:
        """Raises:
        - aiortc.MediaStreamError if user hangs up.
        - UtteranceNotStartedError if the user doesn't start speaking within: UTT_START_TIMEOUT_SEC.
        - UtteranceTooLongError if the utterance is longer than the maximum allowed length: UTT_MAX_LEN_SEC.
        """
        logger.trace("Waiting for utterance to start...")
        try:
            first_frame = await asyncio.wait_for(
                self.__track.recv(),
                timeout=UTT_START_TIMEOUT_SEC,
            )
        except asyncio.TimeoutError as e:
            raise UtteranceNotStartedError(
                f"Utterance not started within {UTT_START_TIMEOUT_SEC} sec"
            ) from e
        logger.trace("Utterance started")
        self.__fifo.write(first_frame)
        utt_sec = 0.0
        while 1:
            try:
                frame = await asyncio.wait_for(
                    self.__track.recv(),
                    timeout=UTT_END_TIMEOUT_SEC,
                )
            except asyncio.TimeoutError as e:
                logger.trace("Utterance ended")
                break
            self.__fifo.write(frame)
            utt_sec += audio.get_frame_seconds(frame)
            if utt_sec > UTT_MAX_LEN_SEC:
                raise UtteranceTooLongError(
                    f"Utterance too long: {utt_sec:.3f} sec > {UTT_MAX_LEN_SEC} sec"
                )
        logger.debug(f"Detected utterance that is {utt_sec:.3f} sec long")
        return self.__fifo.read()
