#!/usr/bin/env python3
"""Convert a copy of an MP3 (e.g. a CC0 pencil recording) to supported WAV.

The app plays only uncompressed PCM WAV (16-bit, mono/stereo). This
helper never modifies the original: it writes `<name>_pcm.wav` beside it
(or to an explicit output path) using ffmpeg, which must already be
installed -- nothing is installed by this script. If ffmpeg is missing,
use the original WAV from the source instead, or export a WAV copy with
any audio editor you already have.

  python convert_to_wav.py "%USERPROFILE%\\Downloads\\Pencil-Sounds-Recorded\\pencil.mp3"
"""
import os
import shutil
import subprocess
import sys


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) not in (1, 2):
        print("Usage: python convert_to_wav.py <input.mp3> [output.wav]",
              file=sys.stderr)
        return 2
    src = argv[0]
    if not os.path.isfile(src):
        print(f"ERROR: input not found: {src}", file=sys.stderr)
        return 2
    dst = argv[1] if len(argv) == 2 else os.path.splitext(src)[0] + "_pcm.wav"
    if os.path.abspath(dst) == os.path.abspath(src):
        print("ERROR: output must differ from the original", file=sys.stderr)
        return 2
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("ERROR: ffmpeg not found on PATH. Nothing was installed or "
              "changed. Use the source's original WAV if available, or "
              "export a 16-bit PCM WAV copy with an audio editor you "
              "already have.", file=sys.stderr)
        return 3
    cmd = [ffmpeg, "-y", "-i", src, "-ac", "1", "-ar", "44100",
           "-sample_fmt", "s16", dst]
    print("Running:", " ".join(cmd))
    if subprocess.run(cmd).returncode != 0:
        print(f"ERROR: ffmpeg failed; no usable WAV produced at {dst}",
              file=sys.stderr)
        return 3
    print(f"Wrote converted copy: {dst} (original untouched: {src})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
