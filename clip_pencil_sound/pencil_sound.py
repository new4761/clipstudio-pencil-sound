#!/usr/bin/env python3
"""Pencil-on-paper sound for Clip Studio Paint -- Windows prototype.

Plays a quiet looping scratch ONLY while all of these are true:
  * Clip Studio Paint is the foreground window,
  * the left button (mouse or pen-as-mouse) is held down, and
  * the pointer is actually moving.

It stops on pause, button release, foreground loss (e.g. Alt-Tab), mute
(F9), and exit. Playback is fixed-volume `winsound.PlaySound` looping;
speed-based volume is NOT implemented in this pass. It only *polls* input
state (GetAsyncKeyState / GetCursorPos); it never injects, hooks, or blocks
input. No admin rights, no driver or settings changes, no auto-start:
run it, draw, Ctrl+C to quit. `--test-audio` plays the WAV for 4 seconds
with no Clip Studio or input needed, to verify sound output itself.

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


# ----------------------------------------------------------------- audio ---
class AudioError(Exception):
    """Playback failed; callers must surface this, never continue silently."""


class WinsoundAudio:
    """Fixed-volume looping playback via winsound.PlaySound (Windows only).

    The previous MCI `waveaudio` backend sent `play ... repeat` and
    `setaudio ... volume` commands that this device does not support and
    discarded every MCI error code, so strokes were silent with no clue.
    winsound has no per-loop volume control, so playback is at the WAV's
    own (quiet) level: speed-based volume is not implemented.
    """

    def __init__(self, path, winsound_mod=None):
        if winsound_mod is None:
            try:
                import winsound as winsound_mod
            except ImportError as exc:
                raise AudioError(
                    "winsound is unavailable (this backend requires Windows)"
                ) from exc
        if not os.path.isfile(path):
            raise AudioError(f"WAV file not found: {path}")
        self._winsound = winsound_mod
        self._path = path
        self._playing = False

    def play(self):
        ws = self._winsound
        flags = ws.SND_FILENAME | ws.SND_ASYNC | ws.SND_LOOP | ws.SND_NODEFAULT
        try:
            ws.PlaySound(self._path, flags)
        except (RuntimeError, OSError) as exc:
            raise AudioError(f"winsound.PlaySound failed for {self._path}: {exc}") from exc
        self._playing = True

    def pause(self):
        self._stop()

    def close(self):
        self._stop()

    def _stop(self):
        if not self._playing:
            return
        self._playing = False
        try:
            self._winsound.PlaySound(None, self._winsound.SND_PURGE)
        except (RuntimeError, OSError) as exc:
            print(f"WARNING: stopping playback failed: {exc}", file=sys.stderr)


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
                if not gate.playing:
                    try:
                        audio.play()
                    except AudioError as exc:
                        print(f"ERROR: {exc}", file=sys.stderr)
                        print("Sound output failed; exiting instead of "
                              "running silently. Run with --test-audio to "
                              "diagnose playback.", file=sys.stderr)
                        raise
                    gate.playing = True
            elif gate.playing:
                audio.pause()
                gate.playing = False
            prev_pos, prev_t = pos, now
    except KeyboardInterrupt:
        print("\nExiting.")
    finally:
        if gate.playing:
            audio.pause()
        audio.close()
    return gate


def test_audio(path=WAV_PATH, duration_s=4.0, audio_factory=None, sleep=time.sleep):
    """Play the WAV unconditionally; return 0 only if no playback error.

    Needs no Clip Studio and no input, so it isolates 'can this PC play
    the file at all' from the foreground/button/movement gating.
    """
    if audio_factory is None:
        if sys.platform != "win32":
            print(f"ERROR: --test-audio requires Windows (winsound); "
                  f"this platform is '{sys.platform}'.", file=sys.stderr)
            return 2
        audio_factory = WinsoundAudio
    try:
        audio = audio_factory(path)
    except AudioError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    print(f"Playing {path} for {duration_s:.0f}s at fixed volume "
          f"(speed-based volume not implemented). You should hear a quiet "
          f"pencil scratch loop now...")
    try:
        audio.play()
        sleep(duration_s)
    except AudioError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    finally:
        audio.close()
    print("Playback finished without an error. If you heard nothing, check "
          "the Windows output device and volume mixer, then re-run.")
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv == ["--test-audio"]:
        return test_audio()
    if argv:
        print("Usage: python pencil_sound.py [--test-audio]", file=sys.stderr)
        return 2
    if sys.platform != "win32":
        print(
            "This prototype targets Windows (winsound + user32 polling).\n"
            f"Current platform is '{sys.platform}', so audio and pen input "
            "cannot be exercised here.\n"
            "Run test_logic.py to verify the gating logic, and run this file "
            "on the Windows PC to test the real stylus."
        )
        return 2
    try:
        audio = WinsoundAudio(WAV_PATH)
    except AudioError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("Run with --test-audio to diagnose playback.", file=sys.stderr)
        return 3
    print("Fixed-volume playback; speed-based volume not implemented.")
    try:
        run(WindowsInput(), audio)
    except AudioError:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
