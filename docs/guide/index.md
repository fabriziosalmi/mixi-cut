# Introduction

MIXI-CUT is an open-source DVS (Digital Vinyl System) timecode protocol designed from scratch for artisanal vinyl lathe cutting. It is not reverse-engineered from Serato or Traktor.

## What is MIXI-CUT?

A timecode vinyl contains a special audio signal that encodes the position and speed of the record. DJ software reads this signal through a sound card and maps it to digital audio playback, enabling scratching, beat-matching, and mixing with any audio file.

MIXI-CUT generates the WAV files that are cut onto vinyl with a lathe. The protocol uses a 3 kHz stereo quadrature carrier with absolute position encoding.

## Protocol v0.3.0

The current protocol version includes:

- **Barker-13 sync word** for fast frame acquisition
- **CRC-16** for O(1) corrupted frame rejection
- **Reed-Solomon RS(4)** for full error correction
- **Multi-rate encoding** for inner groove compensation
- **Velocity subcarrier** at 500 Hz for instant speed readout

## Design principles

  1. **Open** --- MIT license, no DRM, no vendor lock-in
  2. **Robust** --- survives -24 dB SNR, 4-bit ADC, 70% channel crosstalk
  3. **Affordable** --- ~8 EUR per vinyl vs ~40 EUR commercial
  4. **Portable** --- reference decoders in Python, C, Rust, JavaScript
  5. **Tested** --- 1000+ Monte Carlo tonearm bounce simulations
