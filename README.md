# MIXI-CUT

**Open-source DVS timecode protocol --- generate, decode, cut.**

[![CI](https://github.com/fabriziosalmi/mixi-cut/actions/workflows/ci.yml/badge.svg)](https://github.com/fabriziosalmi/mixi-cut/actions/workflows/ci.yml)
[![Docs](https://github.com/fabriziosalmi/mixi-cut/actions/workflows/docs.yml/badge.svg)](https://fabriziosalmi.github.io/mixi-cut/)
[![License: MIT](https://img.shields.io/badge/License-MIT-cyan.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org)

MIXI-CUT generates stereo timecode WAV files designed to be **cut onto vinyl with a lathe**. The signal uses **3 kHz stereo quadrature** (L = sin, R = cos) with absolute position encoding (Barker-13 sync + CRC-16 + Reed-Solomon). Reference decoders in **Python, C, Rust, and JavaScript**.

> *"The best timecode is the one you can cut yourself."* --- ~8 EUR per vinyl vs ~40 EUR commercial.

**[Documentation](https://fabriziosalmi.github.io/mixi-cut/)** | **[Protocol Spec](PROTOCOL.md)** | **[Changelog](CHANGELOG.md)**

## Quick Start

```bash
# Install
pip install mixi-cut

# Generate a 15-minute DJ timecode
mixi-cut generate --preset dj-12inch --output side_a.wav

# Verify before cutting
mixi-cut verify side_a.wav --strict

# Decode (reference decoder)
mixi-cut decode side_a.wav
```

## Comparison

| Feature | Serato CV02.5 | Traktor MK2 | **MIXI-CUT v0.3** |
|---------|---------------|-------------|---------------------|
| Carrier | 1.0 kHz | 2.5 kHz | **3.0 kHz** |
| Encoding | Mono | Mono | **Stereo quadrature** |
| Scratch resolution | ~1.0 ms | ~0.4 ms | **~0.33 ms** |
| Error correction | Unknown | Unknown | **CRC-16 + RS(4)** |
| Sync word | Unknown | Unknown | **Barker-13** |
| Velocity channel | No | No | **500 Hz AM** |
| Speed range | Unknown | Unknown | **0.02x -- 3.0x** |
| Brake settle | Unknown | Unknown | **<100 ms** |
| Noise tolerance | Unknown | Unknown | **SNR = -24 dB** |
| Min ADC bits | 16-bit | 16-bit | **4-bit** |
| Decoder languages | 1 (proprietary) | 1 (proprietary) | **4 (open source)** |
| Vinyl cost | ~40 EUR | ~35 EUR | **~8 EUR** |
| License | Proprietary | Proprietary | **MIT** |

## Features

- **Generate** timecode WAVs with presets for 7", 10", 12" vinyl at 33-1/3 or 45 RPM
- **Verify** WAV files before cutting (carrier, quadrature, position encoding)
- **Decode** with reference decoders in Python, C, Rust, JavaScript
- **Benchmark** with 14-category stress test suite (1000 Monte Carlo simulations)
- **Barker-13 sync** for frame acquisition in <500 ms
- **CRC-16 fast-reject** for O(1) corrupted frame detection
- **Dual-PLL decoder** with adaptive bandwidth handoff (narrow 8% + wide 20%)
- **3-regime brake** with exponential traction for <100 ms vinyl brake settle
- **Multi-rate encoding** with 2x density on inner groove
- **Velocity subcarrier** at 500 Hz for instant speed readout
- **RIAA pre-emphasis** for PHONO input compatibility
- **Loop mode** for phase-continuous locked-groove cutting

## Installation

```bash
# From PyPI
pip install mixi-cut

# From source
git clone https://github.com/fabriziosalmi/mixi-cut.git
cd mixi-cut
pip install -e ".[all]"
```

## CLI

```bash
# Generate
mixi-cut generate --preset dj-12inch        # 15-min DJ vinyl
mixi-cut generate --preset test-cut          # 60s test for iteration
mixi-cut generate --preset dj-7inch          # 4-min 7" single
mixi-cut generate --preset phono             # with RIAA pre-emphasis
mixi-cut generate --preset locked-groove     # single revolution
mixi-cut generate --duration 480 --output custom.wav

# Verify
mixi-cut verify side_a.wav --strict

# Benchmark
mixi-cut bench                               # full 14-category suite
mixi-cut bench --category tonearm            # specific category

# Decode
mixi-cut decode side_a.wav

# Protocol info
mixi-cut info
```

<details>
<summary>Legacy generate.py is still supported</summary>

```bash
python generate.py                           # 15-min timecode
python generate.py --duration 480            # 8 minutes
python generate.py --edm-test               # 60s test
python generate.py --loop --riaa            # PHONO with loop
```
</details>

## Presets

| Preset | Duration | RPM | RIAA | Loop | Use case |
|--------|----------|-----|------|------|----------|
| `dj-12inch` | 15 min | 33-1/3 | No | Yes | Standard DJ vinyl |
| `dj-7inch` | 4 min | 45 | No | Yes | 7" single |
| `test-cut` | 60s | 33-1/3 | No | No | Quick iteration |
| `phono` | 15 min | 33-1/3 | Yes | Yes | PHONO preamp input |
| `locked-groove` | 1.8s | 33-1/3 | No | Yes | Single revolution |

## Decoders

MIXI-CUT has reference decoder implementations in 4 languages:

| Language | Location | Tests | Target |
|----------|----------|-------|--------|
| **Python** | `src/mixi_cut/decoder.py` | 133 | Reference, scripting |
| **C** | `decoder_c/` | 13 | Embedded (STM32, ESP32, RPi) |
| **Rust** | `decoder_rust/` | 9 | Native apps, Wasm |
| **JavaScript** | `docs/demo/app.js` | --- | Browser (Web Audio API) |

### C Decoder (zero-alloc, embeddable)

```c
#include "mixi_decoder.h"

mixi_decoder_t dec;
mixi_decoder_init_default(&dec);

mixi_result_t result;
mixi_decoder_process(&dec, left, right, 128, &result);
printf("Speed: %.2f, Lock: %.3f\n", result.speed, result.lock);
```

- Zero heap allocations, ~200 bytes per instance
- C99 compliant, no external dependencies
- Targets: STM32F4, ESP32-S3, Raspberry Pi

### Rust Decoder

```rust
use mixi_decoder::{Decoder, DecoderConfig};

let mut dec = Decoder::new(DecoderConfig::default());
let result = dec.process(&left, &right);
println!("Speed: {:.2}x, Lock: {:.3}", result.speed, result.lock);
```

- `cargo add mixi-decoder`
- Wasm support via `--features wasm`
- CLI: `mixi-decode file.wav`

### Web Demo

Open `docs/demo/index.html` or visit the [live demo](https://fabriziosalmi.github.io/mixi-cut/demo/) --- drag a WAV file to decode in-browser.

## Benchmark Results

14-category stress test with 1000+ Monte Carlo simulations:

| Category | Result | Verdict |
|----------|--------|---------|
| Noise floor | Survives SNR = -24 dB | Pass |
| Wow/flutter | Tolerates +/-5% | Pass |
| Dust/scratches | 1000/sec | Pass |
| Speed range | 0.02x -- 3.0x | Pass |
| Vinyl brake settle | <100 ms | Pass |
| Stop response | 3 ms | Pass |
| Ground loop hum | Immune at +6 dB | Pass |
| ADC clipping | Survives 1.2x overdrive | Pass |
| ADC quantization | Works at 4-bit | Pass |
| Channel crosstalk | 70% L/R bleed tolerated | Pass |
| Multi-skip | 10 rapid skips recovered | Pass |
| EDM beat drift | < 1.2 ms over 64 bars | Pass |
| Tonearm bounce | 0 ms P99, 100% success | Pass |
| Carrier frequency | 3 kHz confirmed optimal | Pass |

```bash
python benchmark.py               # run full suite
python benchmark.py --pdf         # generate PDF report
python benchmark.py --compare     # regression check
```

## Project Structure

```
mixi-cut/
  src/mixi_cut/              # Python package
    protocol.py              # Constants, presets, frame format
    gf256.py                 # GF(2^8) + Reed-Solomon + CRC-16
    encoder.py               # Position encoding (Barker-13, multi-rate)
    carrier.py               # Quadrature carrier + RIAA
    decoder.py               # Dual-PLL decoder + 3-regime brake
    generator.py             # WAV orchestrator
    verifier.py              # WAV verification
    cli.py                   # CLI entry point
  decoder_c/                 # C decoder (zero-alloc, embeddable)
    include/mixi_decoder.h
    src/mixi_decoder.c
    test/test_decoder.c
  decoder_rust/              # Rust crate (wasm-ready)
    src/lib.rs
    src/bin/decode.rs
  docs/                      # VitePress documentation site
    .vitepress/              # Theme + config
    guide/                   # User guides
    api/                     # API reference
    demo/                    # Web demo (JavaScript decoder)
  tests/                     # 133 Python tests
  benchmark.py               # 14-category benchmark suite
  generate.py                # Legacy generator (backward compat)
  pyproject.toml             # pip install mixi-cut
```

## Documentation

Full documentation at **[fabriziosalmi.github.io/mixi-cut](https://fabriziosalmi.github.io/mixi-cut/)**.

| Document | Audience |
|----------|----------|
| [Protocol Spec](PROTOCOL.md) | Protocol specification (v0.3) |
| [Cutting Guide](docs/CUTTING_GUIDE.md) | Lathe operators |
| [DJ Guide](docs/DJ_GUIDE.md) | DJs --- setup, techniques, troubleshooting |
| [Decoder Guide](docs/DECODER_GUIDE.md) | Developers implementing a decoder |
| [Hardware Guide](docs/HARDWARE_GUIDE.md) | Embedded engineers (STM32/ESP32) |
| [Comparison](docs/COMPARISON.md) | vs Serato, Traktor, RekordBox |
| [Contributing](CONTRIBUTING.md) | Contributors |
| [Changelog](CHANGELOG.md) | Release history |

## Development

```bash
# Setup
git clone https://github.com/fabriziosalmi/mixi-cut.git
cd mixi-cut
pip install -e ".[all]"

# Test (155 tests across 3 languages)
make test          # Python (133 tests)
make test-c        # C decoder (13 tests)
make test-rust     # Rust decoder (9 tests)
make test-all      # All of the above

# Lint
make lint

# Benchmark
make bench

# Generate + verify
make generate
make verify
```

## Downloads

Pre-generated WAV files in [Releases](https://github.com/fabriziosalmi/mixi-cut/releases):

| File | Duration | Use |
|------|----------|-----|
| `mixi_timecode_60s.wav` | 60s | Test cut |
| `mixi_timecode_240s.wav` | 4 min | 7" single |
| `mixi_timecode_480s.wav` | 8 min | Short side |
| `mixi_timecode_600s.wav` | 10 min | Standard side |
| `mixi_timecode_900s.wav` | 15 min | Full side |

## License

MIT --- No DRM, no vendor lock-in, free forever.
