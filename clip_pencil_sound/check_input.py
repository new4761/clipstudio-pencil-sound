#!/usr/bin/env python3
"""Probe: does the stylus report left-button-down + cursor movement?

Run this on the Windows PC, then, with Clip Studio Paint in front:
  1. Draw on a BLANK canvas with the pen for ~5 seconds.
  2. Draw with the mouse for ~5 seconds.
  3. Hover with the pen, then hold the pen still on the canvas.

It only reads input state (no hooks, no injection). If the pen draws in
Clip Studio but no "button-down + moving" lines appear for it, the pen is
likely arriving through Wintab/Tablet PC in a way this poll cannot see --
record the tablet model, driver version and Clip Studio's tablet mode
(File > Preferences > Tablet) in README.md instead of trusting the mouse
result.

Requires: Windows + Python 3 (standard library only). Ctrl+C to stop.
"""
import sys
import time

from pencil_sound import WindowsInput, VK_LBUTTON  # noqa: E402


def main():
    if sys.platform != "win32":
        print(
            f"check_input.py needs Windows; this machine reports "
            f"'{sys.platform}'.\nNo stylus result can be produced here -- "
            "run it on the Windows PC with the tablet connected."
        )
        return 2
    src = WindowsInput()
    print("Probing for 30s. Draw with pen, then mouse. Ctrl+C to stop early.")
    prev = src.cursor_pos()
    deadline = time.monotonic() + 30
    seen_button_move = False
    try:
        while time.monotonic() < deadline:
            time.sleep(0.02)
            pos = src.cursor_pos()
            moved = abs(pos[0] - prev[0]) + abs(pos[1] - prev[1])
            down = src.left_button_down()
            if down and moved >= 2:
                seen_button_move = True
                print(f"button-down + moving at {pos} "
                      f"(foreground Clip Studio: {src.foreground_is_clip_studio()})")
            prev = pos
    except KeyboardInterrupt:
        pass
    print("RESULT:", "button-down+movement OBSERVED" if seen_button_move
          else "NOT observed -- if the pen drew during this window, the pen "
               "input is not visible to plain left-button polling; see README.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
