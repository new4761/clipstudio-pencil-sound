#!/usr/bin/env python3
"""Headless tests for the gating logic (no Windows, pen or audio needed).

Covers: hover quiet, stationary hold quiet, moving stroke sounds,
release stops, Alt-Tab (foreground loss) stops, mute silences, and
volume rising with stroke speed. Run: python test_logic.py
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
    ok &= check("slow stroke quieter than fast",
                ps.StrokeGate.volume_for_speed(40) < ps.StrokeGate.volume_for_speed(800))

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
