""" This module provides audio processing utilities:
- wav2af: convert a wav file to an AudioFrame
- energy: calculate the RMS energy of an audio frame
- seconds: calculate the length in seconds of an audio frame
"""
import io
import os
from pathlib import Path
import tempfile
from textwrap import shorten

import av
from google.cloud import storage
from loguru import logger
import numpy as np

from . import wavfile

AUDIO_BUCKET = os.getenv("AUDIO_BUCKET", "moshi-3.appspot.com")  # NOTE default is emulator bucket
logger.info(f"AUDIO_BUCKET={AUDIO_BUCKET}")

storage_client = storage.Client()

def energy(af: av.AudioFrame) -> float:
    """Calculate the RMS energy of an audio frame."""
    arr = af.to_ndarray()  # produces array with dtype of int16
    # NOTE int16 is too small for squares of typical signal stregth so int32 is used
    energy = np.sqrt(np.mean(np.square(arr, dtype=np.int32)))
    logger.trace(f"frame energy: {energy:.3f}")
    assert not np.isnan(energy)
    return energy


def seconds(af: av.AudioFrame) -> float:
    """Calculate the length in seconds of an audio frame."""
    seconds = af.samples / af.rate
    return seconds


def _wavb2af(wav: io.BytesIO) -> av.AudioFrame:
    sample_rate, arr = wavfile.read(wav)
    if len(arr.shape) == 1:
        arr = arr.reshape(-1, 1)
    samples, channels = arr.shape
    layout = "stereo" if channels == 2 else "mono"
    assert channels == len(av.AudioLayout(layout).channels)
    format = av.AudioFormat("s16")
    # logger.debug(f"sample_rate={sample_rate}, samples={samples}, channels={channels}, layout={layout}, planar={format.is_planar}")
    with logger.contextualize(sample_rate=sample_rate, samples=samples, channels=channels, layout=layout, planar=format.is_planar):
        try:
            af = av.AudioFrame.from_ndarray(arr.ravel().reshape(1, -1), format='s16', layout=layout)
        except:
            logger.error(f"Failed to create AudioFrame from wav bytes (as hex): {shorten(wav.hex(), 100)}")
    af.rate = sample_rate
    logger.debug(f"af={af}")
    return af

def _wavp2af(waf: Path) -> av.AudioFrame:
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

def af2wav(af: av.AudioFrame) -> io.BytesIO:
    """Convert an AudioFrame to a wav file."""
    assert isinstance(af, av.AudioFrame)
    af.pts = None
    af.time_base = None
    af.layout = "stereo"
    af.format = "s16"
    af.rate = 24000
    af.samples = 24000
    af.planes = 1
    af.linesize = 1
    af = af.reformat(format="s16", layout="stereo", rate=24000)
    af = af.to_ndarray()
    wav = wavfile.write(af)
    return wav

def download(audio_path: str) -> str:
    """Download an audio file from storage to a local temporary file.
    Caller is responsible for deleting the temporary file.
    Returns:
        tfn: the path to the temporary file.
    """
    logger.trace("Downloading audio file...")
    logger.debug(f"audio_path={audio_path}")
    with logger.contextualize(audio_bucket=AUDIO_BUCKET, audio_path=audio_path):
        logger.trace("Creating objects...")
        afl = Path(audio_path)
        _, tfn = tempfile.mkstemp(suffix=afl.suffix, prefix=afl.stem, dir='/tmp')
        bucket = storage_client.bucket(AUDIO_BUCKET)
        blob = bucket.blob(audio_path)
        logger.trace("Downloading bytes...")
        blob.download_to_filename(tfn)
        logger.trace("Downloaded audio file.")
    return tfn

logger.success("Audio module loaded.")