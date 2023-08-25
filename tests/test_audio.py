from moshi.utils import audio

def test_wav(wavbytes):
    af = audio.wavb2af(wavbytes)
    audio.write_audio_frame_to_wav(af, "test.wav")


# def test_m4a(m4abytes):