""" This module provide audio processing utilities. """
import io
from pathlib import Path
from textwrap import shorten

import av
import numpy as np
from av import AudioFifo, AudioFormat, AudioFrame, AudioLayout
from loguru import logger

from . import wavfile

logger.success("Loaded!")


def get_frame_energy(af: AudioFrame) -> float:
    """Calculate the RMS energy of an audio frame."""
    arr = af.to_ndarray()  # produces array with dtype of int16
    # NOTE int16 is too small for squares of typical signal stregth so int32 is used
    energy = np.sqrt(np.mean(np.square(arr, dtype=np.int32)))
    logger.trace(f"frame energy: {energy:.3f}")
    assert not np.isnan(energy)
    return energy


def get_frame_seconds(af: AudioFrame) -> float:
    """Calculate the length in seconds of an audio frame."""
    seconds = af.samples / af.rate
    return seconds


def get_frame_start_time(frame) -> float:
    """Get the clock time (relative to the start of the stream) at which the frame should start"""
    return frame.pts / frame.rate


# def empty_frame(
#     length=128, format=AUDIO_FORMAT, layout=AUDIO_LAYOUT, rate=SAMPLE_RATE, pts=None
# ) -> AudioFrame:
#     fmt = AudioFormat(format)
#     lay = AudioLayout(layout)
#     size = (len(lay.channels), length)
#     samples = np.zeros(size, dtype=np.int16)
#     if not fmt.is_planar:
#         samples = samples.reshape(1, -1)
#     frame = AudioFrame.from_ndarray(samples, format=format, layout=layout)
#     frame.rate = rate
#     frame.pts = pts
#     return frame


def write_audio_frame_to_wav(frame: AudioFrame, output_file):
    # Source: https://stackoverflow.com/a/56307655/5298555
    with av.open(output_file, "w") as container:
        stream = container.add_stream("pcm_s16le")
        for packet in stream.encode(frame):
            container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)
    logger.debug(f"Wrote audio in WAV (pcm_s16le) format to {output_file}")


def write_bytes_to_wav_file(filename: str, bytestring: bytes):
    with open(filename, "wb") as f:
        f.write(bytestring)


def load_wav_to_buffer(fp: str) -> AudioFifo:
    with av.open(fp, "r") as container:
        fifo = AudioFifo()
        for frame in container.decode(audio=0):
            fifo.write(frame)
    return fifo


def wavb2af(wav: bytes) -> AudioFrame:
    """Parse wav file format, returning an AudioFrame of the body."""
    assert isinstance(wav, bytes)
    buf = io.BytesIO(wav) 
    sample_rate, arr = wavfile.read(buf)
    samples, channels = arr.shape
    layout = "stereo" if channels == 2 else "mono"
    assert channels == len(av.AudioLayout(layout).channels)
    format = av.AudioFormat("s16")
    # logger.debug(f"sample_rate={sample_rate}, samples={samples}, channels={channels}, layout={layout}, planar={format.is_planar}")
    with logger.contextualize(sample_rate=sample_rate, samples=samples, channels=channels, layout=layout, planar=format.is_planar):
        try:
            af = AudioFrame.from_ndarray(arr.ravel().reshape(1, -1), format='s16', layout=layout)
            logger.debug(f"af={af}")
        except:
            logger.error(f"Failed to create AudioFrame from wav bytes (as hex): {shorten(wav.hex(), 100)}")
    return af

def wav2af(waf: Path) -> AudioFrame:
    with open(waf, "rb") as f:
        wav = f.read()
    return wavb2af(wav)