# MIXI-CUT Decoder Implementation Guide

> How to implement a MIXI-CUT decoder from scratch in any language.

## Architecture Overview

A MIXI-CUT decoder is a three-stage audio processing pipeline:

```
Stereo Audio → [Bandpass Filter] → [Phase-Locked Loop] → [Mass-Spring-Damper] → Speed, Lock, Position
                     ↓ L/R               ↓ frequency         ↓ smoothing
              Reject noise          Track carrier         Physical platter model
```

Each stage operates sample-by-sample (bandpass, PLL) or block-by-block (mass-spring, position output).

## Stage 1: Bandpass Filter

### Purpose
Reject everything except the 3 kHz carrier: rumble (< 100 Hz), hum (50/60 Hz), and hiss (> 10 kHz).

### Implementation
Standard biquad bandpass filter (2nd order IIR):

```
H(z) = b0 * (1 - z^-2) / (1 + a1*z^-1 + a2*z^-2)
```

Parameters:
- Center frequency: 3000 Hz
- Q factor: 2.5
- Sample rate: 44100 Hz

```python
# Python reference
w0 = 2π * 3000 / 44100
alpha = sin(w0) / (2 * 2.5)
a0 = 1 + alpha

b0 = alpha / a0
b2 = -alpha / a0
a1 = -2 * cos(w0) / a0
a2 = (1 - alpha) / a0

# Process one sample
def tick(x):
    y = b0 * x + z1
    z1 = -a1 * y + z2
    z2 = b2 * x - a2 * y
    return y
```

You need **two** bandpass filters: one for each channel (L and R).

## Stage 2: Phase-Locked Loop (PLL)

### Purpose
Track the instantaneous frequency of the quadrature carrier and extract the playback speed.

### How it works

1. Compute the phase error between the input signal and the PLL's internal oscillator
2. Apply a PI (proportional-integral) controller to adjust the oscillator frequency
3. The ratio `pll.freq / carrier_freq` gives the instantaneous speed

### Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| Center frequency | 3000 Hz | Expected carrier |
| Bandwidth | 8% (240 Hz) | Tracking range |
| Lock time constant | 50 ms | EMA for lock quality |
| Amplitude gate | 0.005 | Coast below this level |
| Integral drain | 0.98/sample | Decay when unlocked |

### Implementation

```python
# Phase error
err = atan2(left_filtered, right_filtered) - pll_phase

# Wrap to [-π, π]
if err > π: err -= 2π
if err < -π: err += 2π

# PI controller
integral = integral * drain + err * ki
freq = center + err * kp * sr + integral

# Update oscillator phase
phase += 2π * freq / sr
if phase >= 2π: phase -= 2π

# Lock quality (EMA of cos(error))
lock = lock * (1-α) + cos(err) * α

# Output
speed = freq / center  # 1.0 = normal play
```

### DJ Resilience Features (v3)

1. **Integral drain**: When `lock < 0.3`, multiply integral by 0.98 each sample. Prevents bias from needle drops.
2. **Amplitude gate**: When signal amplitude < 0.005 (-46 dBFS), coast — don't update PLL.
3. **Frequency clamp**: Limit PLL frequency to `[-2x, +3x]` of carrier to prevent runaway.

## Stage 3: Mass-Spring-Damper

### Purpose
Smooth the PLL's noisy speed output to match the physical behavior of a turntable platter (Technics SL-1200 model).

### The model

The output speed is a weighted average between the current speed and the PLL input:

```
speed = speed * (1 - traction) + pll_speed * traction
```

Where `traction` varies by context:

| Context | Traction | How detected |
|---------|----------|-------------|
| **Normal play** | 0.05 (= 1 - 0.95 inertia) | Default |
| **Scratch** | 1.0 (instant snap) | Speed delta > 0.3x |
| **Stop** | 0.5 | `|speed| < 0.1` and delta > 0.05 |
| **Vinyl brake** | 0.5–0.9 (ramp) | Sustained deceleration > 3 blocks |
| **Dead zone** | → 0.0 | `|speed| < 0.02` and `|input| < 0.02` |

### Brake detection (v0.2.0)

```python
# Count consecutive deceleration blocks
if input < prev_input - 0.001 and speed > 0.05:
    decel_count += 1
else:
    decel_count = max(0, decel_count - 2)

# Aggressive traction when brake detected
if decel_count > 3:
    factor = min((decel_count - 3) / 5.0, 1.0)
    traction = 0.5 + factor * 0.4  # ramps to 0.9
```

### Signal-aware feeding

Before feeding the PLL speed to the mass-spring, check the signal RMS:

```python
speed_input = pll_speed if rms > 0.01 else 0.0
```

This ensures the decoder outputs 0.0 during silence (lead-in, lead-out, needle lift).

## Block Processing

Process audio in blocks of 128 samples (2.9 ms at 44.1 kHz):

```python
def process_block(left_128, right_128):
    speed_sum = lock_sum = energy_sum = 0

    for i in range(128):
        fl = bandpass_l.tick(left_128[i])
        fr = bandpass_r.tick(right_128[i])
        speed, lock = pll.tick(fl, fr)
        position += pll.freq / sample_rate

        speed_sum += speed
        lock_sum += lock
        energy_sum += fl*fl + fr*fr

    avg_speed = speed_sum / 128
    avg_lock = lock_sum / 128
    rms = sqrt(energy_sum / 128)

    output_speed = mass_spring.tick(avg_speed if rms > 0.01 else 0.0)
    output_position = position / carrier_freq  # in seconds

    return output_speed, avg_lock, output_position
```

## Position Decoding

### Frame format

Every 2800 carrier cycles (0.933 seconds), a 56-bit position frame is modulated:

```
[24-bit position (centiseconds)] [32-bit Reed-Solomon parity]
 = 3 bytes data + 4 bytes RS(4) = 7 bytes = 56 bits
```

### Missing cycle modulation

- Bit `0`: normal carrier amplitude
- Bit `1`: carrier amplitude dips to 25% for one cycle (with raised-cosine transition)

### Detecting bits

1. Compute the envelope of the carrier signal over consecutive cycles
2. Every 50 carrier cycles, compare the amplitude:
   - If amplitude < 60% of mean → bit is `1`
   - Otherwise → bit is `0`

### Reed-Solomon validation

Use GF(2^8) with primitive polynomial 0x11D. Compute 4 syndromes; if all are zero, the frame is valid.

## Reference Implementations

| Language | Location | LOC | Notes |
|----------|----------|-----|-------|
| Python | `src/mixi_cut/decoder.py` | 300 | Reference, fully tested |
| C | `decoder_c/src/mixi_decoder.c` | 240 | Zero-alloc, C99 |
| Rust | `decoder_rust/src/lib.rs` | 350 | wasm-ready |
| JavaScript | `docs/demo/app.js` | 150 | Web Audio API |

## Testing Your Decoder

### Generate test signals

```bash
# Clean signal (should give speed=1.0, lock>0.9)
mixi-cut generate --duration 10 --output test.wav

# With noise (should still lock)
# Add noise in your test code at -20 dB SNR

# Variable speed (pitch up/down)
# Generate at normal speed, then resample to simulate pitch
```

### Expected behavior

| Input | Expected speed | Expected lock | Notes |
|-------|---------------|--------------|-------|
| Normal play | 1.000 ±0.005 | > 0.9 | Steady state |
| +8% pitch | 1.080 ±0.01 | > 0.9 | DJ pitch fader |
| Full stop | 0.000 | < 0.3 | Should reach 0 in <3ms |
| Reverse | -1.000 ±0.01 | > 0.8 | Negative speed |
| Silence | 0.000 | decaying | Signal-aware coast |
| 33% SNR | 1.000 ±0.02 | > 0.7 | Noisy environment |
