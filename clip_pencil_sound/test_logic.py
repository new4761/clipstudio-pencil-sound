#!/usr/bin/env python3
"""Headless tests for the gating logic (no Windows, pen or audio needed).

Covers: hover quiet, stationary hold quiet, moving stroke sounds,
release stops, Alt-Tab (foreground loss) stops, mute silences, the
winsound backend (correct loop flags, errors surfaced not swallowed),
and --test-audio success/failure. Run: python test_logic.py
"""
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
    # Advance the script one step per poll without real sleeping.
    orig_sleep = lambda _s: setattr(fake, "i", fake.i + 1)
    ps.run(fake, audio, gate=gate, sleep=orig_sleep, max_polls=len(script))
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
    try:
        ps.run(fake_in, BrokenAudio(), sleep=lambda _s: setattr(fake_in, "i", fake_in.i + 1),
               max_polls=len(stroke))
        propagated = False
    except ps.AudioError:
        propagated = True
    ok &= check("run() propagates AudioError", propagated)

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
