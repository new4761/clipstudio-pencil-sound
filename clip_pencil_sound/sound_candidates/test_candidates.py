#!/usr/bin/env python3
"""Verify the A/B/C candidates: loudness match, seamlessness, no silent
start, and genuinely distinct textures. No audio is played.
Run: python test_candidates.py
"""
import math
import os
import struct
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ["A_soft_smooth.wav", "B_dry_textured.wav", "C_light_fine.wav"]


def load(name):
    with wave.open(os.path.join(HERE, name), "rb") as wf:
        sr = wf.getframerate()
        data = wf.readframes(wf.getnframes())
    return sr, list(struct.unpack(f"<{len(data) // 2}h", data))


def rms(v):
    return math.sqrt(sum(x * x for x in v) / max(1, len(v)))


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    return bool(cond)


def main():
    ok = True
    sr, base = load(os.path.join("..", "pencil_loop.wav"))
    base_rms = rms(base)
    stats = {}
    for name in FILES:
        sr, d = load(name)
        r = rms(d)
        # Brightness proxy: energy of the sample-to-sample difference.
        diff_rms = rms([d[i + 1] - d[i] for i in range(0, len(d) - 1, 7)])
        typical_step = sorted(abs(d[i + 1] - d[i]) for i in range(0, len(d) - 1, 13))[4000]
        seam = abs(d[0] - d[-1])
        first = rms(d[: int(sr * 0.005)])
        stats[name] = (r, diff_rms, seam, typical_step)
        ok &= check(f"{name}: loudness matched (RMS {r:.0f} vs baseline {base_rms:.0f})",
                    abs(r / base_rms - 1.0) < 0.03)
        ok &= check(f"{name}: no silence at start (first 5ms RMS {first:.0f})",
                    first >= 0.5 * r)
        ok &= check(f"{name}: no seam click (jump {seam} <= 3x typical step {typical_step})",
                    seam <= 3 * max(1, typical_step))
        ok &= check(f"{name}: 4s/22050Hz mono", len(d) == 4 * sr)
    ratios = [stats[n][1] / stats[n][0] for n in FILES]
    ok &= check(f"textures distinct (brightness A<B<C: "
                f"{ratios[0]:.2f} < {ratios[1]:.2f} < {ratios[2]:.2f})",
                ratios[0] < ratios[1] < ratios[2])
    print("ALL PASS" if ok else "SOME FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
