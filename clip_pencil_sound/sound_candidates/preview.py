#!/usr/bin/env python3
"""Preview the A/B/C candidates at one shared volume (Windows, winsound).

No Clip Studio needed. Uses the same app-only gain preparation as the
drawing app, so every candidate is heard at exactly the same volume and
only the texture differs. The app's default sound is NOT changed.

  python preview.py A            # one candidate, 6 s loop
  python preview.py B --volume 50
  python preview.py all          # A, then B, then C, 6 s each
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import pencil_sound as ps  # noqa: E402

FILES = {
    "A": "A_soft_smooth.wav",
    "B": "B_dry_textured.wav",
    "C": "C_light_fine.wav",
}
LABELS = {
    "A": "soft graphite on smooth paper",
    "B": "dry graphite on textured paper",
    "C": "lighter, finer scratch",
}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    choice = "all"
    volume = 50
    i = 0
    while i < len(argv):
        if argv[i] in ("A", "B", "C", "all"):
            choice = argv[i]
            i += 1
        elif argv[i] == "--volume" and i + 1 < len(argv):
            try:
                volume = ps.validate_volume(int(argv[i + 1]))
            except (ValueError, ps.AudioError) as exc:
                print(f"ERROR: --volume must be 0-100 ({exc})", file=sys.stderr)
                return 2
            i += 2
        else:
            print("Usage: python preview.py [A|B|C|all] [--volume 0-100]",
                  file=sys.stderr)
            return 2
    if sys.platform != "win32":
        print(f"ERROR: preview requires Windows (winsound); this platform "
              f"is '{sys.platform}'. Files are present at {HERE}.",
              file=sys.stderr)
        return 2
    keys = ["A", "B", "C"] if choice == "all" else [choice]
    for key in keys:
        path = os.path.join(HERE, FILES[key])
        print(f"{key}: {LABELS[key]} -- {FILES[key]} at volume {volume} ...")
        try:
            audio = ps.WinsoundAudio(path, volume=volume)
        except ps.AudioError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 3
        try:
            audio.play()
            time.sleep(6)
        except ps.AudioError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 3
        finally:
            audio.close()
    print("Done. Reply with your pick: A, B, or C.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
