""" This module provides audio processing utilities:
- wav2af: convert a wav file to an AudioFrame
- energy: calculate the RMS energy of an audio frame
- seconds: calculate the length in seconds of an audio frame
"""
import io
from pathlib import Path
from textwrap import shorten

import av
import numpy as np
from av import AudioFifo, AudioFrame
from loguru import logger

from . import wavfile

def energy(af: AudioFrame) -> float:
    """Calculate the RMS energy of an audio frame."""
    arr = af.to_ndarray()  # produces array with dtype of int16
    # NOTE int16 is too small for squares of typical signal stregth so int32 is used
    energy = np.sqrt(np.mean(np.square(arr, dtype=np.int32)))
    logger.trace(f"frame energy: {energy:.3f}")
    assert not np.isnan(energy)
    return energy


def seconds(af: AudioFrame) -> float:
    """Calculate the length in seconds of an audio frame."""
    seconds = af.samples / af.rate
    return seconds


def _wavb2af(wav: io.BytesIO) -> AudioFrame:
    sample_rate, arr = wavfile.read(wav)
    samples, channels = arr.shape
    layout = "stereo" if channels == 2 else "mono"
    assert channels == len(av.AudioLayout(layout).channels)
    format = av.AudioFormat("s16")
    # logger.debug(f"sample_rate={sample_rate}, samples={samples}, channels={channels}, layout={layout}, planar={format.is_planar}")
    with logger.contextualize(sample_rate=sample_rate, samples=samples, channels=channels, layout=layout, planar=format.is_planar):
        try:
            af = AudioFrame.from_ndarray(arr.ravel().reshape(1, -1), format='s16', layout=layout)
        except:
            logger.error(f"Failed to create AudioFrame from wav bytes (as hex): {shorten(wav.hex(), 100)}")
    af.rate = sample_rate
    logger.debug(f"af={af}")
    return af

def _wavp2af(waf: Path) -> AudioFrame:
    with open(waf, "rb") as f:
        wavb = f.read()
    return _wavb2af(wavb)

def wav2af(wav: bytes | io.BytesIO | Path):
    """Convert a wav file to an AudioFrame."""
    if isinstance(wav, bytes):
        wav = io.BytesIO(wav)
        return _wavb2af(wav)
    elif isinstance(wav, io.BytesIO):
        return _wavb2af(wav)
    elif isinstance(wav, Path):
        return _wavp2af(wav)
    else:
        raise TypeError(f"wav must be bytes, io.BytesIO, or Path, not {type(wav)}")