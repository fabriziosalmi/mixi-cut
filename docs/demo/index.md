# Web Demo

The MIXI-CUT web demo runs entirely in the browser using the JavaScript decoder.

<div style="border: 1px solid var(--vp-c-divider); border-radius: 12px; padding: 24px; margin: 24px 0; text-align: center; background: var(--vp-c-bg-soft);">
  <p style="font-size: 18px; font-weight: 600; margin-bottom: 8px;">Web Decoder Demo</p>
  <p style="color: var(--vp-c-text-2); margin-bottom: 16px;">Load a MIXI-CUT WAV file and decode it in real-time using Web Audio API.</p>
  <a href="https://fabriziosalmi.github.io/mixi-cut/demo/" style="display: inline-block; padding: 10px 24px; background: var(--vp-c-brand-1); color: white; border-radius: 980px; text-decoration: none; font-weight: 500;">Open Demo</a>
</div>

## How it works

1. Load a MIXI-CUT WAV file (or drag and drop)
2. The JavaScript decoder processes the audio in real-time
3. Speed, lock quality, and position are displayed live

## Source code

The demo source is in `docs/demo/`:

- `index.html` --- HTML structure
- `app.js` --- JavaScript decoder (464 lines)
- `style.css` --- Styling
