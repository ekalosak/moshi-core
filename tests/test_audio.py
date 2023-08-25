import av

from moshi.utils import audio

def write_audio_frame_to_wav(frame: av.AudioFrame, output_file):
    # Source: https://stackoverflow.com/a/56307655/5298555
    with av.open(output_file, "w") as container:
        stream = container.add_stream("pcm_s16le")
        for packet in stream.encode(frame):
            container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)
    print(f"Wrote WAV (pcm_s16le): {output_file}")


def test_wav(wavbytes):
    af = audio.wav2af(wavbytes)
    write_audio_frame_to_wav(af, "test.wav")

def test_seconds(wavbytes):
    af = audio.wav2af(wavbytes)
    assert 0.5 < audio.seconds(af) < 1.5, "Saying 'hello' should take ~1 second"

def test_energy(wavbytes):
    af = audio.wav2af(wavbytes)
    _ = audio.energy(af)