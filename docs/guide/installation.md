# Installation

## From PyPI

```bash
pip install mixi-cut
```

## From source

```bash
git clone https://github.com/fabriziosalmi/mixi-cut.git
cd mixi-cut
pip install -e ".[dev]"
```

## Verify installation

```bash
mixi-cut info
```

Expected output:

```
MIXI-CUT v0.3.0
  Protocol:  v0.3.0
  Carrier:   3000 Hz stereo quadrature
  Encoding:  24-bit position, Barker-13 sync, CRC-16 + RS(4)
  Presets:   dj-12inch, dj-7inch, test-cut, phono, locked-groove
```

## Requirements

- Python 3.9 or later
- NumPy
- SoundFile (libsndfile)

## Optional: C and Rust decoders

```bash
# C decoder
cd decoder_c
cc -std=c99 -O2 -Wall -Iinclude -o mixi_decode test/test_decoder.c src/mixi_decoder.c -lm

# Rust decoder
cd decoder_rust
cargo build --release
```
