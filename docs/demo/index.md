# Web Demo

The MIXI-CUT web demo runs entirely in the browser using the JavaScript decoder.
Analyze a timecode WAV/FLAC, or feed a turntable **live** and drive a track with the
vinyl (relative DVS) — all in the browser, no install.

<div style="border: 1px solid var(--vp-c-divider); border-radius: 12px; padding: 24px; margin: 24px 0; text-align: center; background: var(--vp-c-bg-soft);">
  <p style="font-size: 18px; font-weight: 600; margin-bottom: 8px;">Live Decoder &amp; DVS Engine</p>
  <p style="color: var(--vp-c-text-2); margin-bottom: 16px;">Open the full-screen engine: file analysis + live turntable input.</p>
  <a href="/mixi-cut/live/" target="_blank" style="display: inline-block; padding: 10px 24px; background: var(--vp-c-brand-1); color: white; border-radius: 980px; text-decoration: none; font-weight: 500;">Open Demo →</a>
</div>

## How it works

**File mode** (analyze a cut)

1. Load a MIXI-CUT timecode **WAV/FLAC** (lossless — MP3 destroys the L/R quadrature)
2. The JavaScript decoder processes the audio in real-time
3. Speed, lock quality, and position are displayed live

**Live mode** (test a fresh cut / DVS)

1. Cut a MIXI-CUT timecode to vinyl, plug a **stereo line-in** into your machine
2. Press *Start input* (needs HTTPS — GitHub Pages is fine) and grant access
3. Load any track (MP3 ok here) — moving the record drives it, scratch and reverse included

## Source code

The demo source is in `docs/public/live/`:

- `index.html` --- HTML structure
- `app.js` --- JavaScript decoder + live DVS engine
- `style.css` --- Styling
