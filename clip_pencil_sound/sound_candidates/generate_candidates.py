#!/usr/bin/env python3
"""Generate three original pencil-texture candidates (no recorded audio).

A: soft graphite on smooth paper  -- dark, smooth, sparse soft grains
B: dry graphite on textured paper -- coarse, gritty, dense strong grains
C: lighter, finer scratch         -- bright, thin, fine quick grains

All are procedural noise synthesis, written for this project (CC0).
Each is a seamless 4 s loop (end crossfaded into the start), starts at
full texture (no silent lead-in), and is RMS-matched to the baseline
pencil_loop.wav so A/B/C differ in texture, not loudness.

Run: python generate_candidates.py   (writes A/B/C WAVs next to this file)
"""
import math
import os
import random
import struct
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
BASELINE = os.path.join(HERE, "..", "pencil_loop.wav")
SAMPLE_RATE = 22050
DURATION_S = 4.0


def read_samples(path):
    with wave.open(path, "rb") as wf:
        frames = wf.readframes(wf.getnframes())
    return list(struct.unpack(f"<{len(frames) // 2}h", frames))


def rms(vals):
    return math.sqrt(sum(v * v for v in vals) / max(1, len(vals)))


def synth(seed, lowpass, hp_mix, wobble_rate, bursts, burst_gain, burst_len,
          grit_depth):
    n = int(SAMPLE_RATE * DURATION_S)
    fade = int(SAMPLE_RATE * 0.15)
    total = n + fade
    rng = random.Random(seed)
    out = []
    low = prev = 0.0
    phase = 0.0
    for i in range(total):
        phase += rng.uniform(0.5, 1.5) * wobble_rate
        grit = 1.0 - grit_depth + grit_depth * abs(math.sin(phase * 7.0)) * abs(
            math.sin(i * 0.013 + phase))
        white = rng.uniform(-1.0, 1.0)
        low += lowpass * (white - low)
        hp = low - prev
        prev = low
        out.append(((1.0 - hp_mix) * low + hp_mix * hp) * grit)
    for _ in range(bursts):
        start = rng.randrange(0, total - 1200)
        length = rng.randrange(*burst_len)
        for j in range(length):
            env = math.sin(math.pi * j / length)
            out[start + j] *= 1.0 + burst_gain * env
    # Seamless loop: the head crossfades from the signal's own continuation
    # (raw[n:n+fade]), so the last sample flows into the first with no jump.
    loop = out[:n]
    for i in range(fade):
        t = i / fade
        loop[i] = loop[i] * t + out[n + i] * (1.0 - t)
    return loop


def finish(samples, target_rms):
    """RMS-match to target, soft-limiting peaks; returns float samples."""
    vals = [s * 32767.0 for s in samples]
    peak = max(abs(v) for v in vals) or 1.0
    vals = [v / peak * 16000.0 for v in vals]
    for _ in range(3):
        scale = target_rms / (rms(vals) or 1.0)
        vals = [max(-15500.0, min(15500.0, v * scale)) for v in vals]
    return vals


def write_wav(path, vals):
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b"".join(struct.pack("<h", int(v)) for v in vals))


CANDIDATES = {
    "A_soft_smooth.wav": dict(seed=101, lowpass=0.07, hp_mix=0.25,
                              wobble_rate=0.0012, bursts=9, burst_gain=0.35,
                              burst_len=(700, 1600), grit_depth=0.25),
    "B_dry_textured.wav": dict(seed=202, lowpass=0.22, hp_mix=0.55,
                               wobble_rate=0.0035, bursts=44, burst_gain=0.9,
                               burst_len=(400, 1300), grit_depth=0.65),
    "C_light_fine.wav": dict(seed=303, lowpass=0.45, hp_mix=0.85,
                           wobble_rate=0.006, bursts=30, burst_gain=0.45,
                           burst_len=(150, 500), grit_depth=0.4),
}


def main():
    target = rms(read_samples(BASELINE))
    print(f"Baseline RMS target: {target:.0f}")
    for name, params in CANDIDATES.items():
        vals = finish(synth(**params), target)
        path = os.path.join(HERE, name)
        write_wav(path, vals)
        print(f"Wrote {name}: RMS={rms(vals):.0f} peak={max(abs(v) for v in vals):.0f}")


if __name__ == "__main__":
    main()
