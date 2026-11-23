# Interchangeable samples

Drop any supported WAV here (or point `--sound` anywhere) — no Python
edits needed. The app's default stays `../pencil_loop.wav` until a
separate decision changes it; files in this folder are optional extras.

## Supported format

Uncompressed **PCM WAV, 16-bit, mono or stereo, any sample rate**.
MP3/OGG/etc. cannot be played and produce a clear `ERROR:` — convert a
copy first (originals are never modified):

```powershell
python convert_to_wav.py "%USERPROFILE%\Downloads\Pencil-Sounds-Recorded\<file>.mp3"
```

That writes `<file>_pcm.wav` (mono, 44.1 kHz) beside the original, using
an already-installed ffmpeg; if ffmpeg is absent it says so and changes
nothing — then prefer the source's original WAV download instead.

## First live test: real pencil recording (zakkolar)

A CC0 preview of zakkolar's pencil-on-paper recording is on the Windows
PC under `Downloads\Pencil-Sounds-Recorded` (MP3 preview). That folder
is not reachable from the Mac repo, so **no copy is bundled here** and
nothing about its content is claimed from here. On Windows:

1. If the folder also contains an original WAV, use it directly.
2. Else convert the MP3 copy as above.
3. Preview, then draw (blank canvas), e.g.:

```powershell
python pencil_sound.py --test-audio --volume 50 --sound samples\pencil_pcm.wav
python pencil_sound.py --volume 50 --sound samples\pencil_pcm.wav
```

Judge **sample quality** (tone, seam click when the file loops — a
property of the recording/edit, fixable by choosing a calmer excerpt)
separately from **response** (start on stroke, stop on lift/pause/
Alt-Tab/F9/Ctrl+C, and speed behavior). A click at the loop seam is not
a start/stop failure; report the two apart.

## Source & license notes (keep beside every sample)

| File | Source | License | Notes |
|---|---|---|---|
| `../pencil_loop.wav` | Original procedural synthesis (`../generate_wav.py`) | CC0 | Current default |
| `../sound_candidates/A_soft_smooth.wav` | Original synthesis (`../sound_candidates/generate_candidates.py`) | CC0 | Candidate, not default |
| `../sound_candidates/B_dry_textured.wav` | Original synthesis (same) | CC0 | Candidate, not default |
| `../sound_candidates/C_light_fine.wav` | Original synthesis (same) | CC0 | Candidate, not default |
| zakkolar pencil recording (Windows `Downloads\Pencil-Sounds-Recorded`, not bundled) | zakkolar, as downloaded by the tester | CC0 per the tester's download — **verify the license file/page in that folder before redistributing** | Optional first live test; record the exact WAV/MP3 filename used, here, once tested |

When Jasper adds a recording to this folder, add its row (creator,
source page/folder, license, date) **before** committing it. Do not
commit files whose license is unverified.

## Pressure note

This app reads button-down + pointer position/speed only. It does **not**
read stylus pressure, and pointer speed is not evidence of pressure.
Pressure support may only be claimed if actual stylus pressure turns out
to be readable on that PC **without** changing drivers or Clip Studio's
tablet mode — untested, and out of scope for the `--sound` work.
