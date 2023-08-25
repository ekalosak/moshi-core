from moshi.utils import audio

def test_wav(wavbytes):
    # https://docs.fileformat.com/audio/wav/
    af = audio.wavb2af(wavbytes)


# def test_m4a(m4abytes):