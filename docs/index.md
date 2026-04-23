---
layout: home

hero:
  name: "MIXI-CUT"
  text: "Open-source DVS timecode for vinyl."
  tagline: "Generate. Decode. Cut. The timecode protocol designed for lathe-cut vinyl --- from protocol to platter."
  image:
    src: /mixi-cut.png
    alt: "Stylus cutting a vinyl — SCREEECH!!"
  actions:
    - theme: brand
      text: Get Started
      link: /guide/
    - theme: alt
      text: View on GitHub
      link: https://github.com/fabriziosalmi/mixi-cut

features:
  - icon: |
      <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/><line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/><line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/></svg>
    title: 3 kHz Stereo Quadrature
    details: "Dual-channel carrier with 90-degree phase offset. 2.5x resolution of Serato, instant direction detection, 0 ms re-lock after needle skip."
  - icon: |
      <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></svg>
    title: CRC-16 + Reed-Solomon
    details: "Dual-layer error protection. CRC-16 for O(1) fast-reject of corrupted frames, Reed-Solomon for full correction. Survives -24 dB SNR."
  - icon: |
      <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12h4l3-9 4 18 3-9h4"/><circle cx="18" cy="12" r="2"/></svg>
    title: Barker-13 Sync
    details: "Frame acquisition in under 500 ms. Barker code autocorrelation guarantees sidelobe ratio of 1/13 --- no false lock."
  - icon: |
      <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
    title: Velocity Subcarrier
    details: "500 Hz AM-modulated channel for instantaneous speed readout. Bypasses mass-spring damper latency --- instant scratch response."
  - icon: |
      <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 3h-8l-2 4h12l-2-4z"/><line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/></svg>
    title: Multi-Rate Encoding
    details: "Adaptive frame density --- 2x encoding rate on inner groove where linear velocity drops. Compensates for reduced SNR automatically."
  - icon: |
      <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><path d="M22 6l-10 7L2 6"/></svg>
    title: 4 Reference Decoders
    details: "Python, C, Rust, JavaScript. Every decoder is open source, tested, and production-ready. No vendor lock-in, no DRM, MIT license."
---

<style>
.vp-doc .custom-block {
  border-radius: 12px;
}

/* Kill VitePress default hero image blob — our vinyl has its own halo */
.VPHero .image-bg { display: none !important; }

/* Pull the vinyl up-and-left so it fills the void next to the title
   instead of sitting low-right. Only applies on the 2-column layout
   (>=960px); below that VitePress stacks vertically and the image
   is already where it should be. */
@media (min-width: 960px) {
  .VPHero .image {
    transform: translate(-110px, -130px);
  }
}
@media (min-width: 1280px) {
  .VPHero .image {
    transform: translate(-200px, -210px);
  }
}
/* Extra-wide: nudge a touch more without running into the title column */
@media (min-width: 1600px) {
  .VPHero .image {
    transform: translate(-260px, -240px);
  }
}

/* Hero vinyl — spins like a 33⅓ RPM disc (slowed 3× for taste),
   pauses + pops on hover, respects reduced-motion.
   Halo is pure black so it blends into the image's black rim. */
.VPHero .VPImage,
.VPHero .image-src {
  border-radius: 50%;
  box-shadow:
    0 0 0 2px #000,
    0 0 60px 18px rgba(0, 0, 0, 0.88),
    0 30px 80px rgba(0, 0, 0, 0.55);
  animation: mixicut-spin 5.4s linear infinite;
  transform-origin: 50% 50%;
  will-change: transform;
  transition: transform 0.4s cubic-bezier(0.2, 0.9, 0.3, 1.2),
              box-shadow 0.4s ease;
  cursor: grab;
}

.VPHero .VPImage:hover,
.VPHero .image-src:hover {
  animation-play-state: paused;
  transform: scale(1.06) rotate(-6deg);
  box-shadow:
    0 0 0 2px #000,
    0 0 80px 28px rgba(0, 0, 0, 0.95),
    0 36px 100px rgba(0, 0, 0, 0.7);
}

.VPHero .VPImage:active,
.VPHero .image-src:active {
  cursor: grabbing;
  transform: scale(0.98) rotate(2deg);
  transition-duration: 0.08s;
}

@keyframes mixicut-spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}

/* Accessibility: no spin for users who opt out */
@media (prefers-reduced-motion: reduce) {
  .VPHero .VPImage,
  .VPHero .image-src {
    animation: none;
  }
  .VPHero .VPImage:hover,
  .VPHero .image-src:hover {
    transform: none;
  }
}

/* Stats section */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 24px;
  margin: 48px auto;
  max-width: 820px;
  padding: 0 24px;
}

.stat-card {
  text-align: center;
  padding: 24px 16px;
  border-radius: 16px;
  border: 1px solid var(--vp-c-divider);
  background: var(--vp-c-bg-soft);
}

.stat-card .number {
  font-size: 36px;
  font-weight: 700;
  letter-spacing: -0.03em;
  color: var(--vp-c-brand-1);
  line-height: 1.2;
}

.stat-card .label {
  font-size: 13px;
  font-weight: 500;
  color: var(--vp-c-text-2);
  margin-top: 4px;
  letter-spacing: 0.01em;
}

/* Comparison section */
.compare-section {
  max-width: 820px;
  margin: 64px auto;
  padding: 0 24px;
}

.compare-section h2 {
  font-size: 32px;
  font-weight: 700;
  letter-spacing: -0.03em;
  text-align: center;
  margin-bottom: 8px;
}

.compare-section .subtitle {
  text-align: center;
  color: var(--vp-c-text-2);
  margin-bottom: 32px;
  font-size: 16px;
}

.compare-table {
  width: 100%;
  border-collapse: collapse;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid var(--vp-c-divider);
  font-size: 14px;
}

.compare-table th {
  padding: 12px 16px;
  text-align: left;
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--vp-c-text-2);
  background: var(--vp-c-bg-soft);
  border-bottom: 1px solid var(--vp-c-divider);
}

.compare-table td {
  padding: 10px 16px;
  border-bottom: 1px solid var(--vp-c-divider);
  color: var(--vp-c-text-1);
}

.compare-table tr:last-child td {
  border-bottom: none;
}

.compare-table .highlight {
  color: var(--vp-c-brand-1);
  font-weight: 600;
}

/* Install section */
.install-section {
  max-width: 820px;
  margin: 64px auto;
  padding: 0 24px;
  text-align: center;
}

.install-section h2 {
  font-size: 32px;
  font-weight: 700;
  letter-spacing: -0.03em;
  margin-bottom: 24px;
}

.install-code {
  background: var(--vp-c-bg-soft);
  border: 1px solid var(--vp-c-divider);
  border-radius: 12px;
  padding: 20px 24px;
  font-family: var(--vp-font-family-mono);
  font-size: 15px;
  text-align: left;
  max-width: 480px;
  margin: 0 auto;
  color: var(--vp-c-text-1);
  line-height: 2;
}
</style>

<div class="stats-grid">
  <div class="stat-card">
    <div class="number">3 kHz</div>
    <div class="label">Carrier Frequency</div>
  </div>
  <div class="stat-card">
    <div class="number">0.33 ms</div>
    <div class="label">Scratch Resolution</div>
  </div>
  <div class="stat-card">
    <div class="number">0 ms</div>
    <div class="label">Skip Recovery</div>
  </div>
  <div class="stat-card">
    <div class="number">~8 EUR</div>
    <div class="label">Per Vinyl</div>
  </div>
</div>

<div class="compare-section">
  <h2>How it compares.</h2>
  <p class="subtitle">MIXI-CUT vs proprietary timecode systems.</p>
  <table class="compare-table">
    <thead>
      <tr>
        <th>Feature</th>
        <th>Serato CV02.5</th>
        <th>Traktor MK2</th>
        <th>MIXI-CUT v0.3</th>
      </tr>
    </thead>
    <tbody>
      <tr><td>Carrier</td><td>1.0 kHz</td><td>2.5 kHz</td><td class="highlight">3.0 kHz</td></tr>
      <tr><td>Encoding</td><td>Mono</td><td>Mono</td><td class="highlight">Stereo quadrature</td></tr>
      <tr><td>Error correction</td><td>Unknown</td><td>Unknown</td><td class="highlight">CRC-16 + RS(4)</td></tr>
      <tr><td>Sync word</td><td>Unknown</td><td>Unknown</td><td class="highlight">Barker-13</td></tr>
      <tr><td>Velocity channel</td><td>No</td><td>No</td><td class="highlight">500 Hz AM</td></tr>
      <tr><td>Noise tolerance</td><td>Unknown</td><td>Unknown</td><td class="highlight">-24 dB SNR</td></tr>
      <tr><td>Skip recovery</td><td>~500 ms</td><td>~300 ms</td><td class="highlight">0 ms</td></tr>
      <tr><td>License</td><td>Proprietary</td><td>Proprietary</td><td class="highlight">MIT</td></tr>
      <tr><td>Vinyl cost</td><td>~40 EUR</td><td>~35 EUR</td><td class="highlight">~8 EUR</td></tr>
    </tbody>
  </table>
</div>

<div class="install-section">
  <h2>Get started in seconds.</h2>
  <div class="install-code">
    <span style="color: var(--vp-c-text-3);">$</span> pip install mixi-cut<br>
    <span style="color: var(--vp-c-text-3);">$</span> mixi-cut generate --preset dj-12inch<br>
    <span style="color: var(--vp-c-text-3);">$</span> mixi-cut verify side_a.wav --strict
  </div>
</div>
