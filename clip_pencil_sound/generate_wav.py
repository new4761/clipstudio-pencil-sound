#!/usr/bin/env python3
"""Generate an original, synthetic pencil-on-paper loop (no recorded sample).

The sound is procedural: band-passed noise with a gritty amplitude texture,
crossfaded at the ends so it loops seamlessly. It is an original synthesis
written for this prototype and released as CC0 -- use it freely.

Run:  python generate_wav.py [output.wav]
Requires only the Python standard library.
"""
import math
import random
import struct
import sys
import wave

SAMPLE_RATE = 22050
DURATION_S = 2.5
SEED = 20261123


def make_samples():
    n = int(SAMPLE_RATE * DURATION_S)
    rng = random.Random(SEED)
    out = []
    # Simple one-pole low-pass + high-pass chain to shape white noise into
    # a papery scratch band; grit comes from a slow random amplitude wobble.
    low = 0.0
    prev = 0.0
    wobble_phase = 0.0
    for i in range(n):
        wobble_phase += rng.uniform(0.5, 1.5) * 0.002
        grit = 0.55 + 0.45 * math.sin(wobble_phase * 7.0) * math.sin(i * 0.011)
        white = rng.uniform(-1.0, 1.0)
        low += 0.18 * (white - low)          # low-pass
        hp = low - prev                       # crude high-pass (difference)
        prev = low
        out.append(hp * grit)
    # Gentle grain bursts: short louder scrapes, like graphite catching paper.
    for _ in range(26):
        start = rng.randrange(0, n - 900)
        length = rng.randrange(300, 900)
        for j in range(length):
            env = math.sin(math.pi * j / length)
            out[start + j] *= 1.0 + 0.5 * env
    # Normalize to a quiet ceiling; the player also keeps volume low.
    peak = max(abs(v) for v in out) or 1.0
    out = [v / peak * 0.5 for v in out]
    # Crossfade the last 120 ms into the start for a seamless loop.
    fade = int(SAMPLE_RATE * 0.12)
    for i in range(fade):
        t = i / fade
        out[i] = out[i] * t + out[n - fade + i] * (1.0 - t)
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "pencil_loop.wav"
    samples = make_samples()
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        frames = b"".join(
            struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)) for s in samples
        )
        wf.writeframes(frames)
    print(f"Wrote {path}: {len(samples)} samples @ {SAMPLE_RATE} Hz, "
          f"{DURATION_S:.1f}s mono loop (original synthesis, CC0).")


if __name__ == "__main__":
    main()
