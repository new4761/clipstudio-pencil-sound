#!/usr/bin/env python3
"""Pencil-on-paper sound for Clip Studio Paint -- Windows prototype.

Plays a quiet looping scratch ONLY while all of these are true:
  * Clip Studio Paint is the foreground window,
  * the left button (mouse or pen-as-mouse) is held down, and
  * the pointer is actually moving.

It stops on pause, button release, foreground loss (e.g. Alt-Tab), mute
(F9), and exit. Playback is `winsound.PlaySound` looping at an app-only
volume (`--volume 0-100`; 100 = WAV's own level, 0 = silent; Windows
volume/settings untouched; gain applied once per launch, not per stroke).
Speed-based volume is NOT implemented. It only *polls* input state
(GetAsyncKeyState / GetCursorPos); it never injects, hooks, or blocks
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
import struct
import sys
import tempfile
import time
import wave
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
WAV_PATH = os.path.join(HERE, "pencil_loop.wav")

POLL_S = 0.01            # 100 Hz polling (was 20 ms; halving measured below)
WINDOW_S = 0.06          # movement is judged over this sliding window
MOVE_MIN_PX = 1.5        # windowed path length; ignores sub-pixel jitter
SPEED_MIN_PX_S = 20.0    # windowed speed below this counts as stationary

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


class MovementWindow:
    """Path length and speed over a sliding window, not a single poll.

    The old per-poll check needed >=2 px inside one 20 ms poll, i.e. a
    >=100 px/s stroke, so slow stroke starts were never/were late to be
    seen. Windowing keeps stationary-hold protection (windowed path and
    speed both fall to ~0) while slow starts register in tens of ms.
    """

    def __init__(self, window_s=WINDOW_S):
        self.window_s = window_s
        self.samples = deque()

    def reset(self):
        self.samples.clear()

    def add(self, t, pos):
        self.samples.append((t, pos))
        while self.samples and t - self.samples[0][0] > self.window_s:
            self.samples.popleft()
        path = 0.0
        for (_, p0), (_, p1) in zip(self.samples, list(self.samples)[1:]):
            path += math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        span = self.samples[-1][0] - self.samples[0][0] if len(self.samples) > 1 else 0.0
        speed = path / span if span >= 0.02 else 0.0
        return path, speed


class LatencyStats:
    """Code-side onset latency: observed input -> playback call return.

    This deliberately excludes audible onset (Windows audio stack/speaker),
    which code here cannot observe; that half needs the Windows retest.
    """

    def __init__(self):
        self.onsets_ms = []

    def record(self, started, ended):
        self.onsets_ms.append((ended - started) * 1000.0)

    def summary(self):
        if not self.onsets_ms:
            return "onsets=0"
        avg = sum(self.onsets_ms) / len(self.onsets_ms)
        return (f"onsets={len(self.onsets_ms)} avg={avg:.1f}ms "
                f"max={max(self.onsets_ms):.1f}ms (observed->playback-call; "
                f"audible onset not included)")


# ----------------------------------------------------------------- audio ---
class AudioError(Exception):
    """Playback failed; callers must surface this, never continue silently."""


def validate_volume(volume):
    if isinstance(volume, bool) or not isinstance(volume, int) or not 0 <= volume <= 100:
        raise AudioError(f"--volume must be an integer 0-100, got {volume!r}")
    return volume


def prepare_scaled_wav(path, volume, out_dir=None):
    """Return a playback path with app-only gain applied (once per launch).

    100 returns the original file untouched; anything else writes one
    gain-scaled temp copy (0 = all-zero samples). Windows/device volume
    is never read or changed. Caller owns deleting the temp copy.
    """
    validate_volume(volume)
    if volume == 100:
        return path, False
    try:
        with wave.open(path, "rb") as wf:
            params = wf.getparams()
            frames = wf.readframes(wf.getnframes())
        if params.sampwidth != 2:
            raise AudioError(f"expected 16-bit WAV, got sampwidth={params.sampwidth}")
        count = len(frames) // 2
        samples = struct.unpack(f"<{count}h", frames)
        gain = volume / 100.0
        scaled = struct.pack(f"<{count}h", *(
            int(max(-32768, min(32767, round(s * gain)))) for s in samples))
        fd, tmp = tempfile.mkstemp(prefix="pencil_loop_vol", suffix=".wav",
                                   dir=out_dir)
        os.close(fd)
        with wave.open(tmp, "wb") as wf:
            wf.setparams(params)
            wf.writeframes(scaled)
    except (wave.Error, EOFError, OSError) as exc:
        raise AudioError(f"preparing volume-scaled WAV failed: {exc}") from exc
    return tmp, True


class WinsoundAudio:
    """Looping playback via winsound.PlaySound (Windows only).

    Volume is app-only gain baked into one prepared copy at construction
    (see prepare_scaled_wav); winsound itself has no volume control and
    Windows volume is untouched. Speed-based volume is not implemented.
    """

    def __init__(self, path, winsound_mod=None, volume=100):
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
        self.volume = validate_volume(volume)
        self._path, self._owns_copy = prepare_scaled_wav(path, volume)
        self._playing = False

    @property
    def play_path(self):
        return self._path

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
        if self._owns_copy:
            self._owns_copy = False
            try:
                os.remove(self._path)
            except OSError:
                pass

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
def run(input_src, audio, gate=None, sleep=time.sleep, max_polls=None,
        clock=time.monotonic):
    gate = gate or StrokeGate()
    window = MovementWindow()
    stats = LatencyStats()
    input_src.cursor_pos()
    prev_f9 = False
    muted = False
    polls = 0
    print("Running. Draw in Clip Studio Paint to hear the pencil. "
          "F9 = mute/unmute, Ctrl+C = exit.")
    try:
        while max_polls is None or polls < max_polls:
            polls += 1
            sleep(POLL_S)
            poll_start = clock()
            pos = input_src.cursor_pos()
            down = input_src.left_button_down()
            if down:
                moved, speed = window.add(poll_start, pos)
            else:
                window.reset()
                moved, speed = 0.0, 0.0

            f9 = input_src.key_down(VK_F9)
            if f9 and not prev_f9:
                muted = not muted
                print("Muted." if muted else "Unmuted.")
            prev_f9 = f9

            want = gate.decide(
                input_src.foreground_is_clip_studio(),
                down,
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
                    stats.record(poll_start, clock())
                    gate.playing = True
            elif gate.playing:
                audio.pause()
                gate.playing = False
    except KeyboardInterrupt:
        print("\nExiting.")
    finally:
        if gate.playing:
            audio.pause()
        audio.close()
        print(f"Latency (code side): {stats.summary()}")
    return gate


def parse_args(argv):
    """Return (test_audio: bool, volume: int) or raise AudioError."""
    test = False
    volume = 100
    args = list(argv)
    i = 0
    while i < len(args):
        if args[i] == "--test-audio":
            test = True
            i += 1
        elif args[i] == "--volume":
            if i + 1 >= len(args):
                raise AudioError("--volume needs a value 0-100")
            try:
                volume = int(args[i + 1])
            except ValueError:
                raise AudioError(f"--volume must be an integer 0-100, got {args[i + 1]!r}")
            i += 2
        else:
            raise AudioError(f"unknown argument: {args[i]}")
    return test, validate_volume(volume)


def test_audio(path=WAV_PATH, duration_s=4.0, audio_factory=None, sleep=time.sleep,
               volume=100):
    """Play the WAV unconditionally; return 0 only if no playback error.

    Needs no Clip Studio and no input, so it isolates 'can this PC play
    the file at all' from the foreground/button/movement gating.
    """
    if audio_factory is None:
        if sys.platform != "win32":
            print(f"ERROR: --test-audio requires Windows (winsound); "
                  f"this platform is '{sys.platform}'.", file=sys.stderr)
            return 2
        audio_factory = lambda p: WinsoundAudio(p, volume=volume)  # noqa: E731
    try:
        audio = audio_factory(path)
    except AudioError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    if volume == 0:
        print(f"Playing {path} for {duration_s:.0f}s at --volume 0: this "
              f"must be SILENT (gain applied once at launch).")
    else:
        print(f"Playing {path} for {duration_s:.0f}s at --volume {volume} "
              f"(100 = WAV level; same gain as drawing mode). You should "
              f"hear a quiet pencil scratch loop now...")
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
    try:
        test, volume = parse_args(argv)
    except AudioError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("Usage: python pencil_sound.py [--test-audio] [--volume 0-100]",
              file=sys.stderr)
        return 2
    if test:
        return test_audio(volume=volume)
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
        audio = WinsoundAudio(WAV_PATH, volume=volume)
    except AudioError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("Run with --test-audio to diagnose playback.", file=sys.stderr)
        return 3
    print(f"App volume {volume}/100 (gain prepared once at launch; "
          f"Windows volume untouched; speed-based volume not implemented).")
    try:
        run(WindowsInput(), audio)
    except AudioError:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
