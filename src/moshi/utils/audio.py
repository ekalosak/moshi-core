""" This module provide audio processing utilities. """
from pathlib import Path
from textwrap import shorten

import av
import numpy as np
from av import AudioFifo, AudioFormat, AudioFrame, AudioLayout
from loguru import logger

# defaults
SAMPLE_RATE = 48000
AUDIO_FORMAT = "s16"
AUDIO_LAYOUT = "stereo"
logger.info(f"Audio defaults: {SAMPLE_RATE}Hz {AUDIO_FORMAT} {AUDIO_LAYOUT}")

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


def empty_frame(
    length=128, format=AUDIO_FORMAT, layout=AUDIO_LAYOUT, rate=SAMPLE_RATE, pts=None
) -> AudioFrame:
    fmt = AudioFormat(format)
    lay = AudioLayout(layout)
    size = (len(lay.channels), length)
    samples = np.zeros(size, dtype=np.int16)
    if not fmt.is_planar:
        samples = samples.reshape(1, -1)
    frame = AudioFrame.from_ndarray(samples, format=format, layout=layout)
    frame.rate = rate
    frame.pts = pts
    return frame


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
    # https://docs.fileformat.com/audio/wav/
    logger.debug(f"len(wav)={len(wav)}")
    assert isinstance(wav, bytes)
    assert len(wav) > 0, "Empty wav file."
    header, body = wav[0:44], wav[44:]
    logger.debug(f"len(body)={len(body)}")
    # validate header
    assert header.startswith(b"RIFF"), "Invalid wav header."
    assert int.from_bytes(header[4:8], "little") == len(wav) - 8, "File size mismatch, header invalid."
    assert header[8:12] == b"WAVE", "Invalid wav header."
    assert header[12:16] == b"fmt ", "Invalid wav header."
    fmt_len = int.from_bytes(header[16:20], "little")
    assert fmt_len == 16, "Only PCM format is supported."
    channels = int.from_bytes(header[22:24], "little")
    sample_rate = int.from_bytes(header[24:28], "little")
    bits_per_sample = int.from_bytes(header[34:36], "little")
    # sample_format = f'flt{bits_per_sample}'  # 'flt32' for 32-bit floating-point samples
    # audio_format = av.AudioFormat(sample_rate=sample_rate, layout=f'stereo{channels}', format=sample_format)
    assert channels in [1, 2], "Only mono and stereo wav files are supported."
    assert header[36:40] == b"data"
    data_size = int.from_bytes(header[40:44], "little")
    assert len(body) > 0, "Empty wav body."
    assert len(body) % 8 == 0
    arr = np.frombuffer(body, dtype=np.float32)
    arr = arr.reshape(channels, -1)
    layout = 'stereo' if channels == 2 else 'mono'
    logger.debug(f"channels={channels} sample_rate={sample_rate} bit_per_sample={bits_per_sample} data_size={data_size}")
    # afmt = av.AudioFormat(sample_rate=sample_rate, layout=f'stereo{channels}', format=sample_format)
    af = AudioFrame.from_ndarray(arr, format=AUDIO_FORMAT, layout=layout)
    logger.debug(f"af={af}")
    return af

def wav2af(waf: Path) -> AudioFrame:
    with open(waf, "rb") as f:
        wav = f.read()
    return wavb2af(wav)