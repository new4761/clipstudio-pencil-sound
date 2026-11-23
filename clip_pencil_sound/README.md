# Pencil-on-paper sound for Clip Studio Paint (prototype)

A quiet looping pencil scratch that plays **only** while Clip Studio Paint is
in the foreground, the left button (mouse or pen acting as mouse) is held,
and the pointer is moving. It stops on a pause mid-stroke, on button
release, on Alt-Tab away from Clip Studio, when muted (F9), and on exit.
Playback is `winsound.PlaySound` looping at an app-only `--volume 0-100`
(100 = the WAV's own level, 0 = silent; gain baked into one prepared copy
at launch, never per stroke; Windows/device volume untouched).
**Speed-based volume is not implemented.**

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
| `pencil_sound.py` | The prototype (Windows; stdlib only). Polls input, gates playback, loops via `winsound` at `--volume 0-100`. `--test-audio` plays the WAV 4 s with no Clip Studio/input needed. Prints code-side onset latency on exit. Speed-based volume not implemented. |
| `check_input.py` | Probe: prints lines while button-down + movement is seen, so you can tell whether the **pen** (not just the mouse) is visible to plain left-button polling. |
| `generate_wav.py` | Regenerates `pencil_loop.wav` (original synthesis, CC0). |
| `pencil_loop.wav` | 2.5 s seamless mono loop, deliberately quiet. |
| `test_logic.py` | Headless tests of the gating rules; runs anywhere. |

## Run it (Windows PC)

Launch/exit: from this folder run `python pencil_sound.py --volume 50`
(try 30–70 to taste; omit for full WAV level), draw in Clip Studio Paint,
press **F9** to mute/unmute, and **Ctrl+C** to exit — on exit it prints
the measured code-side onset latency (`Latency (code side): …`).

Requires Python 3 on the Windows PC (standard library only). Test on a
**blank canvas**, not a real artwork.

## Latency: what was measured, what changed

Two different delays must not be conflated:

- **Code side** — observed button-down + motion → the `PlaySound` call.
  The app now measures this per stroke onset and prints avg/max on exit.
- **Audible onset** — the call → sound leaving the speaker (Windows audio
  stack/device). Code cannot observe this; only the Windows retest can,
  e.g. by comparing perceived delay against `--test-audio`, which plays
  immediately with no input involved.

Measurements taken on the bundled WAV and the old constants (Mac, before
this change):

| Suspect | Measured | Verdict |
|---|---|---|
| WAV lead-in | First 5 ms RMS 2620 vs 2575 overall (≈102%); reaches 50% RMS at 0 ms | **Not a cause** — the loop starts at full texture; WAV unchanged |
| 20 ms polling | Average wait ≈10 ms, worst 20 ms | Minor contributor; poll is now 10 ms (avg ≈5 ms) |
| 2 px per single poll | Needs ≥100 px/s within one poll; a 30 px/s start moves 0.6 px/poll and **never** triggers | **Dominant code-side cause for slow starts.** Movement is now judged over a 60 ms sliding window (path ≥1.5 px and speed ≥20 px/s): a 30 px/s start registers in ≈70 ms in tests, stationary hold still measures exactly 0 |

No responsiveness was traded for noise: the automated tests re-verify
hover, stationary hold, mute, lift, and Alt-Tab after the change.

## Sound reference (Facebook Reel)

The target Reel (`facebook.com/reel/2409174939892566`) was fetched from
here but only returned a login shell — **its audio could not be heard**,
so no tone/texture was copied or guessed from it. The current sound
remains the original synthesized loop. To match the reference, drop a
short clip (5–10 s WAV/MP3 of the target sound alone) into this folder
and say so; it will be analyzed and re-synthesized as an original, never
ripped.

## To test on the Windows PC

0. Stand-alone volume ladder — **first, always** (no Clip Studio, no
   drawing):
   - `python pencil_sound.py --test-audio --volume 100` — hear the scratch at WAV level, no `ERROR:` (exit 0).
   - `python pencil_sound.py --test-audio --volume 50` — clearly quieter, same scratch.
   - `python pencil_sound.py --test-audio --volume 0` — must be **silent** for 4 s.
   If any prints `ERROR:` / exits 3, sound output itself is broken — fix
   the output device/mixer and re-run. If one finishes cleanly but you
   heard nothing (or heard something at 0), say so; do not proceed as if
   audio works. Note: drawing mode and `--test-audio` share this gain.
1. `python check_input.py` — draw ~5 s with the pen on a blank canvas, then
   ~5 s with the mouse. Pen lines appearing = pen is visible to this method.
   If the pen draws but prints nothing, note the tablet model/driver/mode in
   the table above; the prototype's polling cannot see that pen, and the
   mouse result must not be read as pen support.
2. `python pencil_sound.py --volume 50` — run the matrix below for pen,
   then mouse, on a blank canvas. State which device each column used;
   the previous drawing test's device was unconfirmed, and a mouse pass
   never proves pen support. On Ctrl+C, copy the printed
   `Latency (code side): …` line into the report, and separately say
   whether the *audible* onset still feels delayed (that half is the
   Windows audio path, not visible to the code-side number).

## Known limitation: canvas vs UI false positives

The foreground check identifies the Clip Studio **window**, not the canvas.
Dragging a toolbar slider, a palette, or the title bar inside Clip Studio
will also produce sound. That is an expected false positive of this design;
note any cases you hit during testing rather than treating them as canvas
strokes. (Distinguishing canvas from UI would need hit-testing against
Clip Studio internals, which is out of scope for a no-admin prototype.)

## Test results

Mac (this machine) — `python3 test_logic.py`: **all pass.** In addition
to the earlier gating/backend checks, they now prove: `--volume` parsing
and rejection of bad values; volume 50 exactly halves WAV RMS and volume
0 is all-zero samples (same preparation path for `--test-audio` and
drawing); gain is prepared once per launch and the temp copy is cleaned
up on close; a slow 30 px/s stroke registers in ≈70 ms under the windowed
rule (the old per-poll rule could never fire below 100 px/s) while a
stationary hold still measures exactly 0; the WAV lead-in measures ~0 ms.
They do **not** prove anything audible or Windows-specific: a fake
`winsound` records calls, and on Mac `--test-audio` exits 2 ("requires
Windows"), which is correct, not a pass.

Windows PC — what actually ran, and what was heard:

- *First test (old MCI backend):* the probe detected button-down + movement
  with Clip Studio foreground and the app showed "Unmuted", but **no sound
  was heard**. The probe device is **unconfirmed** (pen vs mouse unknown),
  so this says nothing about pen support. Verdict for that backend: **fail
  (silent playback)** — now replaced.
- *Second test (winsound backend, `e469ff9`):* the tester **heard the
  stand-alone audio** (`--test-audio`) — that half now works. During
  drawing they reported a **slight delay** and asked for quieter output.
  The drawing-test device is **unconfirmed**, and per-device drawing
  results (onset, lift, Alt-Tab, pressure) were not separately reported,
  so the matrix below remains Not tested for this build.
- *This build (volume + latency):* **not yet run or heard on Windows.**

Per-device matrix to fill in (`Pass` / `Fail` / `Not tested`), pen and
mouse separately, blank canvas:

| Behaviour (blank canvas) | Pen | Mouse |
|---|---|---|
| `--test-audio --volume 100` heard / `--volume 50` quieter / `--volume 0` silent | Not tested | Not tested |
| Drawing onset: starts promptly, no obvious delay (quote the printed code-side Latency line) | Not tested | Not tested |
| Hover: quiet | Not tested | Not tested |
| Stationary hold: quiet | Not tested | Not tested |
| Slow stroke: quiet, natural scratch (starts without waiting for speed) | Not tested | Not tested |
| Fast stroke: same app volume (speed volume not implemented), still natural | Not tested | Not tested |
| Lift mid-stroke / pause: sound stops | Not tested | Not tested |
| Alt-Tab away: sound stops; back: stays quiet until next stroke | Not tested | Not tested |
| F9 mute: silent; unmute resumes normally; Ctrl+C exit stops sound | Not tested | Not tested |
| Pressure + line quality unchanged vs prototype off | Not tested | Not tested |
| UI-drag false positives noted (sliders/title bar) | Not tested | Not tested |

Current honest summary: pen — **not tested**; mouse on Windows — **not
tested** (as named devices; one unconfirmed-device drawing report of
slight delay exists); Mac automated tests — **pass** (simulated, nothing
heard). Confirmed Windows facts: the old backend was silent despite
visible input and "Unmuted"; the winsound stand-alone audio was heard;
the Facebook Reel reference could not be accessed from here.
