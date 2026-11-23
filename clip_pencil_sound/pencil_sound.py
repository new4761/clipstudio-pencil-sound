#!/usr/bin/env python3
"""Pencil-on-paper sound for Clip Studio Paint -- Windows prototype.

Plays a quiet looping scratch ONLY while all of these are true:
  * Clip Studio Paint is the foreground window,
  * the left button (mouse or pen-as-mouse) is held down, and
  * the pointer is actually moving.

It stops/fades on pause, button release, foreground loss (e.g. Alt-Tab),
or mute (F9). It only *polls* input state (GetAsyncKeyState / GetCursorPos);
it never injects, hooks, or blocks input. No admin rights, no driver or
settings changes, no auto-start: run it, draw, Ctrl+C to quit.

Limitation: a foreground check cannot tell the canvas apart from the
toolbar/menus, so dragging a slider or title bar inside Clip Studio will
also sound. Treat any such sound as a known false positive (see README).

Requires: Windows + Python 3 (standard library only).
On other platforms it runs in a no-audio self-test mode so the gating
logic can be verified; it makes no claim about pen support there.
"""
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WAV_PATH = os.path.join(HERE, "pencil_loop.wav")

POLL_S = 0.02            # 50 Hz polling
MOVE_MIN_PX = 2.0        # ignore sub-pixel jitter
SPEED_MIN_PX_S = 15.0    # below this the stroke counts as stationary
SPEED_FULL_PX_S = 900.0  # speed mapped to full (still quiet) volume
VOLUME_MAX = 350         # MCI volume 0..1000; kept deliberately quiet
FADE_STEP = 90           # volume removed per poll while fading out

VK_LBUTTON = 0x01
VK_F9 = 0x78


# ---------------------------------------------------------------- gating ---
class StrokeGate:
    """Pure decision logic, kept separate so it can be unit-tested."""

    def __init__(self):
        self.playing = False

    def decide(self, foreground_clip, button_down, moved_px, speed_px_s, muted):
        want = (
            foreground_clip
            and button_down
            and not muted
            and moved_px >= MOVE_MIN_PX
            and speed_px_s >= SPEED_MIN_PX_S
        )
        return want

    @staticmethod
    def volume_for_speed(speed_px_s):
        t = (speed_px_s - SPEED_MIN_PX_S) / (SPEED_FULL_PX_S - SPEED_MIN_PX_S)
        t = max(0.0, min(1.0, t))
        return int(60 + t * (VOLUME_MAX - 60))


# ----------------------------------------------------------------- audio ---
class MciAudio:
    """Looping WAV playback with volume control via Windows MCI (winmm)."""

    def __init__(self, path):
        import ctypes
        self._mci = ctypes.windll.winmm.mciSendStringW
        self._path = path
        self._volume = 0
        self._send(f'open "{path}" type waveaudio alias pencil')
        self._send("set pencil time format milliseconds")

    def _send(self, cmd):
        import ctypes
        buf = ctypes.create_unicode_buffer(256)
        self._mci(cmd, buf, 256, None)

    def set_volume(self, vol):
        self._volume = max(0, min(1000, int(vol)))
        self._send(f"setaudio pencil volume to {self._volume}")

    def play(self):
        self._send("play pencil repeat")

    def pause(self):
        self._send("pause pencil")

    def close(self):
        try:
            self._send("stop pencil")
            self._send("close pencil")
        except Exception:
            pass


class NullAudio:
    """Records audio calls instead of playing; used for tests / non-Windows."""

    def __init__(self):
        self.calls = []
        self.volume = 0

    def set_volume(self, vol):
        self.volume = vol
        self.calls.append(("volume", vol))

    def play(self):
        self.calls.append(("play",))

    def pause(self):
        self.calls.append(("pause",))

    def close(self):
        self.calls.append(("close",))


# --------------------------------------------------------------- windows ---
class WindowsInput:
    """Read-only polling of foreground window, button state and cursor."""

    def __init__(self):
        import ctypes
        self._ctypes = ctypes
        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32

    def foreground_is_clip_studio(self):
        hwnd = self.user32.GetForegroundWindow()
        if not hwnd:
            return False
        title = self._window_text(hwnd)
        proc = self._process_name(hwnd)
        text = f"{title} {proc}".lower()
        return "clip studio" in text or "clipstudiopaint" in text.replace(" ", "")

    def _window_text(self, hwnd):
        length = self.user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buf = self._ctypes.create_unicode_buffer(length + 1)
        self.user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value

    def _process_name(self, hwnd):
        pid = self._ctypes.c_ulong(0)
        self.user32.GetWindowThreadProcessId(hwnd, self._ctypes.byref(pid))
        if not pid.value:
            return ""
        handle = self.kernel32.OpenProcess(0x1000, False, pid.value)  # QUERY_LIMITED_INFORMATION
        if not handle:
            return ""
        try:
            size = self._ctypes.c_ulong(1024)
            buf = self._ctypes.create_unicode_buffer(1024)
            ok = self.kernel32.QueryFullProcessImageNameW(
                handle, 0, buf, self._ctypes.byref(size)
            )
            return os.path.basename(buf.value) if ok else ""
        finally:
            self.kernel32.CloseHandle(handle)

    def left_button_down(self):
        return bool(self.user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)

    def key_down(self, vk):
        return bool(self.user32.GetAsyncKeyState(vk) & 0x8000)

    def cursor_pos(self):
        class POINT(self._ctypes.Structure):
            _fields_ = [("x", self._ctypes.c_long), ("y", self._ctypes.c_long)]

        pt = POINT()
        self.user32.GetCursorPos(self._ctypes.byref(pt))
        return float(pt.x), float(pt.y)


# -------------------------------------------------------------- main loop --
def run(input_src, audio, gate=None, sleep=time.sleep, max_polls=None):
    gate = gate or StrokeGate()
    prev_pos = input_src.cursor_pos()
    prev_t = time.monotonic()
    prev_f9 = False
    muted = False
    fading_to = None
    polls = 0
    print("Running. Draw in Clip Studio Paint to hear the pencil. "
          "F9 = mute/unmute, Ctrl+C = exit.")
    try:
        while max_polls is None or polls < max_polls:
            polls += 1
            sleep(POLL_S)
            now = time.monotonic()
            dt = max(now - prev_t, 1e-6)
            pos = input_src.cursor_pos()
            moved = math.hypot(pos[0] - prev_pos[0], pos[1] - prev_pos[1])
            speed = moved / dt

            f9 = input_src.key_down(VK_F9)
            if f9 and not prev_f9:
                muted = not muted
                print("Muted." if muted else "Unmuted.")
            prev_f9 = f9

            want = gate.decide(
                input_src.foreground_is_clip_studio(),
                input_src.left_button_down(),
                moved,
                speed,
                muted,
            )
            if want:
                target = StrokeGate.volume_for_speed(speed)
                if not gate.playing:
                    audio.set_volume(target)
                    audio.play()
                    gate.playing = True
                    fading_to = None
                else:
                    audio.set_volume(target)
            elif gate.playing:
                # Fade quickly, then pause, so lifts and Alt-Tab end cleanly.
                fading_to = (fading_to if fading_to is not None else VOLUME_MAX) - FADE_STEP
                if fading_to <= 0:
                    audio.set_volume(0)
                    audio.pause()
                    gate.playing = False
                    fading_to = None
                else:
                    audio.set_volume(fading_to)
            prev_pos, prev_t = pos, now
    except KeyboardInterrupt:
        print("\nExiting.")
    finally:
        if gate.playing:
            audio.pause()
        audio.close()
    return gate


def main():
    if sys.platform != "win32":
        print(
            "This prototype targets Windows (winmm/MCI + user32 polling).\n"
            f"Current platform is '{sys.platform}', so audio and pen input "
            "cannot be exercised here.\n"
            "Run test_logic.py to verify the gating logic, and run this file "
            "on the Windows PC to test the real stylus."
        )
        return 2
    if not os.path.exists(WAV_PATH):
        print(f"Missing {WAV_PATH}. Run: python generate_wav.py")
        return 2
    run(WindowsInput(), MciAudio(WAV_PATH))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
