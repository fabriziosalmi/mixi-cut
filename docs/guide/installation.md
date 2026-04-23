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

Expected output (package version line will track your installed build;
the protocol version stays at `v0.3.0` until the wire format changes):

```
MIXI-CUT v0.3.x
Protocol: v0.3.0
Carrier: 3000 Hz stereo quadrature
Sample rate: 44100 Hz

Presets:
  dj-12inch            Full side 12" DJ vinyl (15 min)
  dj-7inch             Single side 7" (4 min)
  test-cut             60s test for quick iteration
  phono                Full side with RIAA pre-emphasis
  locked-groove        Single revolution locked groove
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
