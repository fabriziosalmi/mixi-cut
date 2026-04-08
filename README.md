# MIXI-CUT

Open-source timecode vinyl signal generator for DVS (Digital Vinyl System) lathe cutting.

## What is this?

MIXI-CUT generates a stereo timecode WAV file designed to be cut onto vinyl with a lathe. The signal uses **3 kHz stereo quadrature** (L = sin, R = cos) with absolute position encoding (Missing Cycle + Reed-Solomon). Optimized for EDM (100-200 BPM).

| Feature | Serato CV02.5 | Traktor MK2 | MIXI-CUT v3 |
|---------|---------------|-------------|-------------|
| Frequency | 1.0 kHz | 2.5 kHz | 3.0 kHz |
| Channels | Mono | Mono | Stereo quadrature |
| Scratch resolution | ~1.0 ms | ~0.4 ms | ~0.33 ms |
| Skip recovery | ~500 ms | ~300 ms | **0 ms** |
| Tonearm bounce | Not tested | Not tested | **1000 MC, 100%** |
| Noise tolerance | Unknown | Unknown | SNR = -24 dB |
| Min ADC bits | 16-bit | 16-bit | **4-bit** |
| License | Proprietary | Proprietary | MIT |

## Quick start

```bash
pip install -r requirements.txt
python generate.py
```

## Downloads

Pre-generated WAV files are available in [Releases](https://github.com/fabriziosalmi/mixi-cut/releases):
- `mixi_timecode_v2_8min.wav` — 8 min (single side)
- `mixi_timecode_v2_10min.wav` — 10 min
- `mixi_timecode_v2_12min.wav` — 12 min
- `mixi_timecode_v2_15min.wav` — 15 min (full disc)
- `mixi_timecode_v2_test60s.wav` — 60s test for first lathe cut

All files are phase-continuous (loop mode) for locked-groove cutting.

## Generator options

```bash
python generate.py                              # Full 15-min timecode
python generate.py --duration 480               # 8 minutes
python generate.py --edm-test                   # 60s test for quick iteration
python generate.py --loop                       # Phase-continuous for locked groove
python generate.py --riaa                       # RIAA pre-emphasis (PHONO input)
python generate.py --verify file.wav            # Verify before cutting
python generate.py --duration 60 --output t.wav # Custom duration and filename
```

## Benchmark suite

Draconian stress testing with 14 categories and 1000+ Monte Carlo simulations:

```bash
python benchmark.py                  # Full suite, colored terminal output
python benchmark.py --pdf            # Generate PDF report
python benchmark.py --test tonearm   # Run specific category
python benchmark.py --compare        # Regression check vs last run
python benchmark.py --history        # Show all historical runs
```

### Benchmark results (v3)

| Category | Result | Verdict |
|----------|--------|---------|
| Noise floor | Survives SNR = -24 dB | strong |
| Wow/flutter | Tolerates +-5% | strong |
| Dust/scratches | 1000/sec | strong |
| Speed range | 0.02x - 2.0x | strong |
| Stop response | 3 ms (was 2003 ms) | strong |
| Ground loop hum | Immune at +6 dB | strong |
| ADC clipping | Survives 1.2x overdrive | strong |
| ADC quantization | Works at 4-bit | strong |
| Channel crosstalk | 70% L/R bleed tolerated | strong |
| Multi-skip | 10 rapid skips recovered | strong |
| EDM beat drift | < 1.2 ms over 64 bars | strong |
| Combined "impossible" | Survives | strong |
| **Tonearm bounce** | **0 ms P99, 100% success** | **strong** |
| Carrier frequency | 3 kHz confirmed optimal | strong |

### Tonearm bounce physics

Simulates the complete Technics SL-1200 MK2-7 tonearm behavior during a needle skip:

- Free-fall physics (gravity, height, airtime)
- Damped bouncing with coefficient of restitution (2-6 bounces)
- Skating bias (90% inward toward center)
- Impact impulse spikes on landing
- Phase discontinuity (lands on different groove)
- DJ pinky nudge, dirty vinyl, worn stylus scenarios
- **1000 Monte Carlo random scenarios: 100% recovery**

## Lathe cutting parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Speed | 33 1/3 RPM | Standard DJ |
| Groove spacing | 200 lines/inch | Wider = more robust |
| Level | +3 dB above nominal | Compensates vinyl noise floor |
| Duration per side | 4-7.5 min | 8-15 min available |
| Material | PVC / polycarbonate | Lathe cut compatible |

## Pre-cut checklist

1. Generate WAV at 44100 Hz / 16-bit stereo
2. Run `--verify` to check quadrature, frequency, position encoding
3. If PHONO input: generate with `--riaa`
4. Cut a 60s test first (`--edm-test`), test with decoder
5. Cut full version with `--loop` for locked-groove

## Protocol specification

See [PROTOCOL.md](PROTOCOL.md) for the full MIXI-CUT v3 protocol specification.

## Decoder

The MIXI-CUT decoder is part of [mixi](https://github.com/fabriziosalmi/mixi), an open-source DJ application. Written in Rust/Wasm, runs in an AudioWorklet.

## License

MIT - No DRM, no vendor lock-in, free forever.
