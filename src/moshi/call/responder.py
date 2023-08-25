""" This module provides the ResponsePlayer class that plays audio responses to the remote client speakers. """
import asyncio
import os
import time
from typing import Callable

from aiortc import MediaStreamTrack
from av import AudioFifo, AudioFrame
from loguru import logger

from moshi import AUDIO_FORMAT, AUDIO_LAYOUT, SAMPLE_RATE, audio

BUFFER_AHEAD_SEC = (
    0.5  # how far ahead of the current time to allow buffer audio frames on the client.
)
FRAME_SEND_TIMEOUT_SEC = 0.5  # how long beyond the length of the response to wait for the audio fifo to flush to the track.
FRAME_SIZE = 960
assert FRAME_SIZE >= 128 and FRAME_SIZE <= 4096
logger.info(f"Using transport frame size: {FRAME_SIZE}")

logger.debug("Loaded responder module.")


class ResponsePlayerStream(MediaStreamTrack):
    kind = "audio"

    def __init__(self):
        super().__init__()
        self.__fifo = AudioFifo()
        self.__sent = asyncio.Event()
        self.__send_start_time = None
        self.__sent_buffer_time = None

    async def recv(self) -> AudioFrame:
        """Return audio from the fifo whenever it exists.
        Otherwise, wait for audio to be written to the fifo.
        """
        frame = None
        while frame == None:
            frame = self.__fifo.read(FRAME_SIZE)
            if not frame:
                # NOTE must flush partial frames;
                #   these will otherwise cause big noise spikes at end of utterance.
                self.__fifo.read()
                self.__sent.set()
                await asyncio.sleep(0.05)
            else:  # NOTE must buffer or there will be SILENT buffer overflow on the client.
                frame_sec = audio.get_frame_seconds(frame)
                wall_elapsed_time = time.monotonic() - self.__send_start_time
                if self.__sent_buffer_time - wall_elapsed_time > BUFFER_AHEAD_SEC:
                    throttle_sec = BUFFER_AHEAD_SEC / 3.0
                    await asyncio.sleep(throttle_sec)
                    # logger.trace(f"playback throttled {throttle_sec} sec")
                self.__sent_buffer_time += frame_sec
                # logger.trace(f"frame.pts: {frame.pts}")
        return frame

    async def send_audio(self, frame: AudioFrame):
        self.__send_start_time = time.monotonic()
        self.__sent_buffer_time = 0.0
        frame.pts = self.__fifo.samples_written
        self.__fifo.write(frame)
        self.__sent.clear()
        await self.__sent.wait()


class ResponsePlayer:
    """When audio is set, it is sent over the track."""

    def __init__(self):
        self.__track = ResponsePlayerStream()

    @property
    def audio(self):
        return self.__track

    async def send_utterance(self, frame: AudioFrame):
        """Write the frame to the audio track, thereby sending it to the remote client.
        Raises:
            - aiortc.MediaStreamError if the remote client hangs up.
            - asyncio.TimeoutError if the audio track is busy for longer than: FRAME_SEND_TIMEOUT_SEC.
        """
        logger.trace(
            f"Sending utterance of length: {audio.get_frame_seconds(frame):.3f} sec"
        )
        assert frame.rate == SAMPLE_RATE
        timeout = audio.get_frame_seconds(frame) + FRAME_SEND_TIMEOUT_SEC
        await asyncio.wait_for(
            self.__track.send_audio(frame),
            timeout=timeout,
        )
        logger.trace(f"Utterance sent.")
