#!/usr/bin/env python3
"""Headless tests for the gating logic (no Windows, pen or audio needed).

Covers: hover quiet, stationary hold quiet, moving stroke sounds,
release stops, Alt-Tab (foreground loss) stops, mute silences, the
winsound backend (correct loop flags, errors surfaced not swallowed),
and --test-audio success/failure. Run: python test_logic.py
"""
import os

import pencil_sound as ps


class FakeInput:
    def __init__(self, script):
        self.script = list(script)  # (foreground, down, pos, f9)
        self.i = 0

    def _cur(self):
        return self.script[min(self.i, len(self.script) - 1)]

    def foreground_is_clip_studio(self):
        return self._cur()[0]

    def left_button_down(self):
        return self._cur()[1]

    def cursor_pos(self):
        return self._cur()[2]

    def key_down(self, vk):
        return self._cur()[3]


def drive(script):
    audio = ps.NullAudio()
    fake = FakeInput(script)
    gate = ps.StrokeGate()
    # Advance the script and a fake clock (POLL_S per poll) together.
    t = [0.0]

    def advance(_s):
        fake.i += 1
        t[0] += ps.POLL_S

    ps.run(fake, audio, gate=gate, sleep=advance, max_polls=len(script),
           clock=lambda: t[0])
    return audio, gate


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    return cond


def main():
    ok = True
    g = ps.StrokeGate()
    # Unit-level decisions.
    ok &= check("hover (no button) is quiet", not g.decide(True, False, 50, 300, False))
    ok &= check("stationary hold is quiet", not g.decide(True, True, 0, 0, False))
    ok &= check("moving stroke sounds", g.decide(True, True, 10, 300, False))
    ok &= check("background app is quiet", not g.decide(False, True, 10, 300, False))
    ok &= check("muted stroke is quiet", not g.decide(True, True, 10, 300, True))

    # winsound backend: looping flags, purge-on-stop, surfaced errors.
    class FakeWinsound:
        SND_FILENAME, SND_ASYNC, SND_LOOP, SND_NODEFAULT, SND_PURGE = 1, 2, 4, 8, 16

        def __init__(self, fail=False):
            self.calls = []
            self.fail = fail

        def PlaySound(self, path, flags):
            self.calls.append((path, flags))
            if self.fail:
                raise RuntimeError("no audio device")

    fake = FakeWinsound()
    backend = ps.WinsoundAudio(ps.WAV_PATH, winsound_mod=fake)
    backend.play()
    played_path, played_flags = fake.calls[0]
    ok &= check("winsound plays WAV async+loop",
                bool(played_path == ps.WAV_PATH
                     and played_flags & fake.SND_LOOP and played_flags & fake.SND_ASYNC))
    backend.pause()
    ok &= check("winsound stop purges sound", fake.calls[-1] == (None, fake.SND_PURGE))
    try:
        ps.WinsoundAudio(ps.WAV_PATH, winsound_mod=FakeWinsound(fail=True)).play()
        raised = False
    except ps.AudioError:
        raised = True
    ok &= check("winsound failure raises AudioError (not silent)", raised)
    try:
        ps.WinsoundAudio("no_such_file.wav", winsound_mod=FakeWinsound())
        missing = False
    except ps.AudioError:
        missing = True
    ok &= check("missing WAV raises AudioError", missing)
    ok &= check("--test-audio succeeds with working backend",
                ps.test_audio(audio_factory=lambda p: ps.WinsoundAudio(p, winsound_mod=FakeWinsound()),
                              sleep=lambda _s: None) == 0)
    ok &= check("--test-audio reports failure (exit 3, no silent pass)",
                ps.test_audio(audio_factory=lambda p: ps.WinsoundAudio(p, winsound_mod=FakeWinsound(fail=True)),
                              sleep=lambda _s: None) == 3)

    # Playback failure mid-run must propagate, not run on silently.
    class BrokenAudio(ps.NullAudio):
        def play(self):
            raise ps.AudioError("boom")

    stroke = ([(True, False, (0.0, 0.0), False)]
              + [(True, True, (float(x * 8), 0.0), False) for x in range(1, 5)])
    fake_in = FakeInput(stroke)
    t2 = [0.0]

    def advance2(_s):
        fake_in.i += 1
        t2[0] += ps.POLL_S

    try:
        ps.run(fake_in, BrokenAudio(), sleep=advance2, max_polls=len(stroke),
               clock=lambda: t2[0])
        propagated = False
    except ps.AudioError:
        propagated = True
    ok &= check("run() propagates AudioError", propagated)

    # --volume: parsing, gain math, once-per-launch preparation.
    ok &= check("parse --test-audio --volume 50",
                ps.parse_args(["--test-audio", "--volume", "50"]) == (True, 50, ps.WAV_PATH))
    ok &= check("parse defaults (default sound kept)",
                ps.parse_args([]) == (False, 100, ps.WAV_PATH))
    cand_a = os.path.join(os.path.dirname(ps.WAV_PATH),
                          "sound_candidates", "A_soft_smooth.wav")
    ok &= check("parse --sound accepts a path in both modes",
                ps.parse_args(["--sound", cand_a]) == (False, 100, cand_a)
                and ps.parse_args(["--test-audio", "--volume", "50",
                                   "--sound", cand_a]) == (True, 50, cand_a))
    for bad in (["--volume", "101"], ["--volume", "-1"], ["--volume", "x"],
                ["--bogus"], ["--sound"], ["--volume"]):
        try:
            ps.parse_args(bad)
            rejected = False
        except ps.AudioError:
            rejected = True
        ok &= check(f"parse rejects {bad}", rejected)

    import math as _math
    import struct as _struct
    import wave as _wave

    def rms_of(path):
        with _wave.open(path, "rb") as wf:
            data = wf.readframes(wf.getnframes())
        vals = _struct.unpack(f"<{len(data) // 2}h", data)
        return _math.sqrt(sum(v * v for v in vals) / max(1, len(vals))), max(
            (abs(v) for v in vals), default=0)

    base_rms, _ = rms_of(ps.WAV_PATH)
    half_path, half_owned = ps.prepare_scaled_wav(ps.WAV_PATH, 50)
    half_rms, _ = rms_of(half_path)
    ok &= check("volume 50 halves RMS (same gain test-audio/drawing)",
                bool(half_owned and abs(half_rms / base_rms - 0.5) < 0.02))
    zero_path, _ = ps.prepare_scaled_wav(ps.WAV_PATH, 0)
    zero_rms, zero_peak = rms_of(zero_path)
    ok &= check("volume 0 is silent (all-zero samples)", zero_rms == 0.0 and zero_peak == 0)
    ok &= check("volume 100 reuses original WAV (no copy)",
                ps.prepare_scaled_wav(ps.WAV_PATH, 100) == (ps.WAV_PATH, False))

    fake50 = FakeWinsound()
    backend50 = ps.WinsoundAudio(ps.WAV_PATH, winsound_mod=fake50, volume=50)
    first_path = backend50.play_path
    backend50.play(); backend50.pause(); backend50.play()
    ok &= check("gain prepared once per launch (path stable across strokes)",
                backend50.play_path == first_path
                and all(c[0] in (first_path, None) for c in fake50.calls))
    backend50.close()
    import os as _os
    ok &= check("prepared temp copy cleaned up on close", not _os.path.exists(first_path))
    for p in (half_path, zero_path):
        _os.remove(p)

    # Latency evidence: windowed slow onset, WAV lead-in, stats separation.
    win = ps.MovementWindow()
    onset_ms = None
    for step in range(1, 40):  # 30 px/s in 10 ms polls = 0.3 px/poll
        path, speed = win.add(step * ps.POLL_S, (step * 0.3, 0.0))
        if path >= ps.MOVE_MIN_PX and speed >= ps.SPEED_MIN_PX_S:
            onset_ms = step * ps.POLL_S * 1000
            break
    ok &= check(f"slow 30px/s stroke registers (onset {onset_ms and round(onset_ms)}ms, "
                f"old per-poll rule: never below 100px/s)",
                onset_ms is not None and onset_ms <= 80)
    win2 = ps.MovementWindow()
    still = [win2.add(i * ps.POLL_S, (10.0, 10.0)) for i in range(20)]
    ok &= check("stationary hold window stays zero (no onset trade-off)",
                still[-1] == (0.0, 0.0))
    with _wave.open(ps.WAV_PATH, "rb") as wf:
        sr = wf.getframerate()
        data = wf.readframes(wf.getnframes())
    vals = _struct.unpack(f"<{len(data) // 2}h", data)
    k = int(sr * 0.005)
    first_rms = _math.sqrt(sum(v * v for v in vals[:k]) / k)
    ok &= check(f"WAV lead-in ~0ms (first 5ms RMS {first_rms:.0f} >= 50% overall "
                f"{base_rms:.0f})", first_rms >= 0.5 * base_rms)
    stats = ps.LatencyStats()
    stats.record(1.000, 1.004)
    ok &= check("latency stats report code-side ms only",
                "avg=4.0ms" in stats.summary() and "audible onset not included" in stats.summary())

    # --sound: validation and interchangeable-file playback path.
    ok &= check("validate_wav accepts a candidate WAV",
                ps.validate_wav(cand_a) == cand_a)
    for bad_path, why in ((cand_a + ".missing.wav", "missing file"),
                          (os.path.abspath(__file__), "non-WAV file")):
        try:
            ps.validate_wav(bad_path)
            rejected = False
            msg = ""
        except ps.AudioError as exc:
            rejected, msg = True, str(exc)
        ok &= check(f"validate_wav rejects {why} with clear error",
                    bool(rejected and "Supported:" in msg or rejected and "not found" in msg))
    seen = {}

    def recording_factory(path):
        seen["path"] = path
        return ps.WinsoundAudio(path, winsound_mod=FakeWinsound(), volume=50)

    ok &= check("--test-audio --sound plays the chosen file",
                ps.test_audio(path=cand_a, audio_factory=recording_factory,
                              sleep=lambda _s: None, volume=50) == 0
                and seen.get("path") == cand_a)
    ok &= check("--test-audio with bogus --sound exits 3 (clear error)",
                ps.test_audio(path="no_such_sound.wav",
                              audio_factory=recording_factory,
                              sleep=lambda _s: None) == 3)

    # End-to-end through the poll loop: stroke, lift, Alt-Tab.
    script = (
        [(True, False, (0.0, 0.0), False)] * 3          # hover
        + [(True, True, (float(x * 8), 0.0), False) for x in range(1, 8)]  # stroke
        + [(True, False, (56.0, 0.0), False)] * 8       # lift -> fade/pause
        + [(True, True, (float(56 + x * 8), 0.0), False) for x in range(1, 6)]  # stroke
        + [(False, True, (120.0, 0.0), False)] * 8      # Alt-Tab away -> stop
    )
    audio, gate = drive(script)
    actions = [c[0] for c in audio.calls]
    ok &= check("loop played during stroke", "play" in actions)
    ok &= check("loop paused after lift / Alt-Tab", actions.count("pause") >= 1)
    ok &= check("gate ends stopped", not gate.playing)
    print("ALL PASS" if ok else "SOME FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
