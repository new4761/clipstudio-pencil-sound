# Pencil-on-paper sound for Clip Studio Paint (prototype)

A quiet looping pencil scratch that plays **only** while Clip Studio Paint is
in the foreground, the left button (mouse or pen acting as mouse) is held,
and the pointer is moving. It fades/stops on a pause mid-stroke, on button
release, on Alt-Tab away from Clip Studio, and when muted (F9).

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
| `pencil_sound.py` | The prototype (Windows; stdlib only). Polls input, gates and plays the loop via MCI with speed-mapped volume. |
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

1. `python check_input.py` — draw ~5 s with the pen on a blank canvas, then
   ~5 s with the mouse. Pen lines appearing = pen is visible to this method.
   If the pen draws but prints nothing, note the tablet model/driver/mode in
   the table above; the prototype's polling cannot see that pen, and the
   mouse result must not be read as pen support.
2. `python pencil_sound.py` — run the matrix below for pen, then mouse.

## Known limitation: canvas vs UI false positives

The foreground check identifies the Clip Studio **window**, not the canvas.
Dragging a toolbar slider, a palette, or the title bar inside Clip Studio
will also produce sound. That is an expected false positive of this design;
note any cases you hit during testing rather than treating them as canvas
strokes. (Distinguishing canvas from UI would need hit-testing against
Clip Studio internals, which is out of scope for a no-admin prototype.)

## Test results

Mac (this machine) — gating logic only, `python3 test_logic.py`: **all
pass** (hover quiet, stationary hold quiet, moving stroke sounds, release
pauses, foreground loss pauses, mute silences, volume rises with speed).
The WAV was generated and verified (22050 Hz, 55125 frames, mono).

Windows PC — **not run yet**. Per-device matrix to fill in (`Pass` / `Fail`
/ `Not tested`):

| Behaviour (blank canvas) | Pen | Mouse |
|---|---|---|
| Hover: quiet | Not tested | Not tested |
| Stationary hold: quiet | Not tested | Not tested |
| Slow stroke: quiet, natural scratch | Not tested | Not tested |
| Fast stroke: louder/faster feel, still natural | Not tested | Not tested |
| Lift mid-stroke: sound stops | Not tested | Not tested |
| Alt-Tab away: sound stops; back: stays quiet until next stroke | Not tested | Not tested |
| F9 mute: silent; unmute resumes normally | Not tested | Not tested |
| Pressure + line quality unchanged vs prototype off | Not tested | Not tested |
| UI-drag false positives noted (sliders/title bar) | Not tested | Not tested |

Current honest summary: pen — **not tested (no physical stylus available
to this session)**; mouse on Windows — **not tested**; logic core —
**pass** (simulated inputs, no audio hardware or pen involved).
