# Sound candidates — pick A, B, or C

Three original synthesized loops (procedural noise, CC0 — no recorded or
downloaded audio). The current app default (`../pencil_loop.wav`) is
unchanged; nothing here replaces it until a pick is made.

| Pick | File | Texture |
|---|---|---|
| A | `A_soft_smooth.wav` | Soft graphite on smooth paper — dark, smooth, sparse soft grains |
| B | `B_dry_textured.wav` | Dry graphite on textured paper — coarse, gritty, dense strong grains |
| C | `C_light_fine.wav` | Lighter, finer scratch — bright, thin, fine quick grains |

All three: 4.0 s seamless loops, no silent start, RMS-matched to the
baseline (2575) so the comparison is texture, not loudness. Verified by
`test_candidates.py` (loudness, seam, lead-in, distinct brightness
A < B < C, low self-similarity — no obvious repetition).

## Preview on Windows (no Clip Studio needed)

Same gain path as the drawing app, so volume is identical across picks:

```powershell
cd clipstudio-pencil-sound\clip_pencil_sound\sound_candidates
python preview.py all            # A, B, C in order, 6 s each, volume 50
python preview.py A              # re-play one
python preview.py B --volume 30  # any single shared volume 0-100
```

Then reply **A**, **B**, or **C**. Only after a pick will the chosen loop
become the app default (separate change; playback/hotkeys untouched).

## About the Facebook Reel reference

The Reel (facebook.com/reel/2409174939892566) could not be heard from
here — fetching it returns only a Facebook login shell, with no audio.
No match to it is claimed and none of its audio was used. If you want
the candidates matched to that sound, provide a 5–10 second clip
(WAV/MP3 of the target sound alone) and the synthesis will be re-tuned
against it as an original.
