"""PCM16 volume helper; FFmpeg is not required by the relay."""
from array import array
from relay import state

def apply_volume(pcm16: bytes) -> bytes:
    volume = float(state.volume)
    if volume == 1.0:
        return pcm16
    samples = array("h")
    samples.frombytes(pcm16)
    if samples.itemsize != 2:
        return pcm16
    for i, sample in enumerate(samples):
        value = int(sample * volume)
        samples[i] = max(-32768, min(32767, value))
    return samples.tobytes()

def start_ffmpeg():
    raise RuntimeError("FFmpeg pipe is no longer used; PyTgCalls handles PCM frames directly.")
