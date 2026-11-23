# Pencil-on-paper sound for Clip Studio Paint (prototype)

A quiet looping pencil scratch that plays **only** while Clip Studio Paint is
in the foreground, the left button (mouse or pen acting as mouse) is held,
and the pointer is moving. It stops on a pause mid-stroke, on button
release, on Alt-Tab away from Clip Studio, when muted (F9), and on exit.
Playback is fixed-volume `winsound.PlaySound` looping; **speed-based volume
is not implemented** in this pass.

> **Why the backend changed:** the first Windows test detected button-down +
> movement with Clip Studio in the foreground and showed "Unmuted", but the
> tester heard nothing. The old MCI `waveaudio` backend sent `play … repeat`
> and `setaudio … volume` commands the device does not support and discarded
> every MCI error code, so it failed silently. That backend is removed.
> Playback errors now raise `AudioError`, print `ERROR: …`, and exit (code
> 3) instead of running on silently. Note the probe device in that test is
> **unconfirmed** — it is not evidence the pen (vs mouse) was seen.

Safety properties, by design:

- Read-only: it polls `GetAsyncKeyState` / `GetCursorPos` and the foreground
  window. It never injects, hooks, or blocks input, so pen pressure and line
  quality are untouched (nothing sits between the tablet driver and Clip
  Studio).
- No admin rights, no driver install, no settings changes, no auto-start.
  Nothing is written outside this folder.
- The WAV is an original procedural synthesis (see `generate_wav.py`),
  released CC0. No recorded or third-party sample is used.

## Status of this build — read first

This prototype was **built and logic-tested on a Mac** (macOS 26.5, MacBook
Air). It has **not** been run on the target Windows PC, because from here:

- **No physical stylus is available** — no tablet is connected to this
  machine, so no pen result exists. A mouse result would not prove pen
  support anyway (see probe below).
- Clip Studio Paint is not installed here, and this is not Windows, so the
  `Wintab` vs `Tablet PC` question cannot be observed from here.

The Windows test pass below is therefore mostly **not tested**, honestly.
Run the two commands in "To test on the Windows PC" to complete it; do not
treat the Mac logic tests as pen evidence.

### Tablet / driver record (fill in on the Windows PC — do not guess)

| Field | Value |
|---|---|
| Tablet model | _not recorded — fill in (e.g. from the tablet itself / Device Manager)_ |
| Driver name + version | _not recorded — fill in (tablet maker's control panel)_ |
| Clip Studio tablet mode | _not recorded — File > Preferences > Tablet: `Wintab` or `Tablet PC`_ |
| Pen reports button-down + movement to `check_input.py`? | _not tested_ |

Nothing about the tablet driver or Clip Studio's tablet setting was changed
while building this prototype, and the prototype never changes them.

## Files

| File | Purpose |
|---|---|
| `pencil_sound.py` | The prototype (Windows; stdlib only). Polls input, gates playback, loops the WAV at fixed volume via `winsound`. `--test-audio` plays the WAV 4 s with no Clip Studio/input needed. Speed-based volume not implemented. |
| `check_input.py` | Probe: prints lines while button-down + movement is seen, so you can tell whether the **pen** (not just the mouse) is visible to plain left-button polling. |
| `generate_wav.py` | Regenerates `pencil_loop.wav` (original synthesis, CC0). |
| `pencil_loop.wav` | 2.5 s seamless mono loop, deliberately quiet. |
| `test_logic.py` | Headless tests of the gating rules; runs anywhere. |

## Run it (Windows PC)

Launch/exit: from this folder run `python pencil_sound.py`, draw in Clip
Studio Paint, press **F9** to mute/unmute, and **Ctrl+C** to exit.

Requires Python 3 on the Windows PC (standard library only). Test on a
**blank canvas**, not a real artwork.

## To test on the Windows PC

0. `python pencil_sound.py --test-audio` — **first, always.** It plays the
   WAV for 4 s with no Clip Studio and no drawing. You must hear the quiet
   scratch and see it finish with no `ERROR:` line (exit code 0). If it
   prints `ERROR:` / exits 3, sound output itself is broken — fix the
   output device/mixer and re-run before touching the steps below. If it
   finishes cleanly but you heard nothing, say so in the report; do not
   proceed as if audio works.
1. `python check_input.py` — draw ~5 s with the pen on a blank canvas, then
   ~5 s with the mouse. Pen lines appearing = pen is visible to this method.
   If the pen draws but prints nothing, note the tablet model/driver/mode in
   the table above; the prototype's polling cannot see that pen, and the
   mouse result must not be read as pen support.
2. `python pencil_sound.py` — run the matrix below for pen, then mouse,
   on a blank canvas. Pen and mouse are separate columns; a mouse pass
   never proves pen support.

## Known limitation: canvas vs UI false positives

The foreground check identifies the Clip Studio **window**, not the canvas.
Dragging a toolbar slider, a palette, or the title bar inside Clip Studio
will also produce sound. That is an expected false positive of this design;
note any cases you hit during testing rather than treating them as canvas
strokes. (Distinguishing canvas from UI would need hit-testing against
Clip Studio internals, which is out of scope for a no-admin prototype.)

## Test results

Mac (this machine) — gating logic + fake-winsound backend, `python3
test_logic.py`: **all pass** (hover quiet, stationary hold quiet, moving
stroke sounds, release stops, foreground loss stops, mute silences,
correct async+loop flags, stop purges, playback failure raises
`AudioError`, `--test-audio` success/failure exit codes, `run()`
propagates playback errors). No real audio was heard in these tests — a
fake `winsound` module records calls. On Mac, `--test-audio` itself exits
2 ("requires Windows"), which is correct, not a pass.

Windows PC — what actually ran, and what was heard:

- *First test (old MCI backend):* the probe detected button-down + movement
  with Clip Studio foreground and the app showed "Unmuted", but **no sound
  was heard**. The probe device is **unconfirmed** (pen vs mouse unknown),
  so this says nothing about pen support. Verdict for that backend: **fail
  (silent playback)** — now replaced.
- *New winsound backend:* **not yet run or heard on Windows.** Until
  `--test-audio` is heard on that PC, every row below stays Not tested.

Per-device matrix to fill in (`Pass` / `Fail` / `Not tested`), pen and
mouse separately, blank canvas:

| Behaviour (blank canvas) | Pen | Mouse |
|---|---|---|
| `--test-audio` heard, no `ERROR:` | Not tested | Not tested |
| Hover: quiet | Not tested | Not tested |
| Stationary hold: quiet | Not tested | Not tested |
| Slow stroke: quiet, natural scratch | Not tested | Not tested |
| Fast stroke: same fixed volume (speed volume not implemented), still natural | Not tested | Not tested |
| Lift mid-stroke / pause: sound stops | Not tested | Not tested |
| Alt-Tab away: sound stops; back: stays quiet until next stroke | Not tested | Not tested |
| F9 mute: silent; unmute resumes normally; Ctrl+C exit stops sound | Not tested | Not tested |
| Pressure + line quality unchanged vs prototype off | Not tested | Not tested |
| UI-drag false positives noted (sliders/title bar) | Not tested | Not tested |

Current honest summary: pen — **not tested**; mouse on Windows — **not
tested**; Mac logic/backend-unit tests — **pass** (simulated, nothing
heard). The one confirmed Windows fact is negative: the old backend was
silent despite visible input and "Unmuted".
