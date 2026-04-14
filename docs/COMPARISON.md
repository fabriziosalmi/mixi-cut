# MIXI-CUT vs Commercial Timecode — Technical Comparison

> Objective comparison between MIXI-CUT and commercial DVS timecode systems.

## Overview

| Feature | MIXI-CUT | Serato NoiseMap™ | Traktor MK2 | Pioneer RekordBox DVS |
|---------|----------|-----------------|-------------|----------------------|
| **License** | MIT (open source) | Proprietary | Proprietary | Proprietary |
| **Carrier** | 3 kHz quadrature | ~1 kHz (complex) | ~2 kHz | ~1 kHz |
| **Channels** | Stereo (L=sin, R=cos) | Stereo | Stereo | Stereo |
| **Position encoding** | 24-bit + RS(4) | Proprietary | Proprietary | Proprietary |
| **Error correction** | Reed-Solomon GF(2^8) | Unknown | Unknown | Unknown |
| **Vinyl cost** | ~8 EUR (lathe cut) | ~40 EUR (retail) | ~35 EUR | ~35 EUR |
| **Replacement** | Generate + cut anytime | Buy from dealer | Buy from dealer | Buy from dealer |
| **Custom duration** | Any length | Fixed | Fixed | Fixed |
| **Loop mode** | Phase-continuous | N/A | N/A | N/A |
| **RIAA support** | Optional pre-emphasis | Built-in | Built-in | Built-in |
| **Decoder available** | Python, C, Rust, JS | Software-locked | Software-locked | Software-locked |
| **Embedded target** | STM32, ESP32, RPi | None | None | None |
| **Wasm decoder** | Yes | No | No | No |

## Signal Design

### MIXI-CUT Advantages

1. **Higher carrier frequency (3 kHz vs ~1 kHz)**
   - Better separation from music content and rumble
   - Narrower bandpass filter → better noise rejection
   - Shorter PLL lock time

2. **Stereo quadrature encoding**
   - L=sin, R=cos provides unambiguous direction detection
   - Instant forward/reverse discrimination
   - No direction detection delay

3. **Explicit error correction**
   - Reed-Solomon RS(4) over GF(2^8)
   - Detects up to 4 errored bytes per frame
   - Position accuracy guaranteed when RS validates

4. **Open protocol**
   - Full specification published
   - Anyone can implement a decoder
   - No proprietary hardware required

### MIXI-CUT Limitations

1. **Lathe-cut quality**
   - Lathe cuts have lower SNR than pressed vinyl
   - Groove noise is higher, especially on inner groove
   - Fewer play cycles before degradation

2. **No ecosystem lock-in (pro and con)**
   - Not compatible with Serato DJ, Traktor, RekordBox
   - Requires MIXI-CUT–compatible decoder software

3. **No needle-drop position** (yet)
   - Position requires a full frame decode (0.93s)
   - Commercial systems may have faster acquisition

## Performance Comparison

> Based on MIXI-CUT benchmark suite v3 and published data for commercial systems.

| Metric | MIXI-CUT | Serato (typical) | Source |
|--------|----------|-------------------|--------|
| Lock time | <2s | <1s | Serato: published spec |
| Position resolution | 10 ms | ~10 ms | Comparable |
| Speed range | -2x to +3x | -1x to +1x (estimated) | MIXI-CUT: PLL tested |
| Speed accuracy | ±0.005x | ±0.01x (estimated) | MIXI-CUT: benchmark |
| Noise tolerance | SNR >-24 dB | Unknown | MIXI-CUT: benchmark |
| Scratch latency | <3 ms | <5 ms (estimated) | MIXI-CUT: benchmark |
| Vinyl brake | 476 ms settle | Unknown | 500ms ramp, 24ms lag |
| Hum rejection | >40 dB at 50/60 Hz | Unknown | MIXI-CUT: benchmark |

## Cost Analysis

### Per-vinyl cost

| Item | MIXI-CUT | Serato CV02 |
|------|----------|-------------|
| Vinyl | ~8 EUR (lathe cut) | ~40 EUR (retail) |
| Availability | On-demand | Dealer stock |
| Bulk (10+) | ~5 EUR each | ~35 EUR each |
| Custom length | Yes | No |
| Replacement | Instant (re-cut) | Re-purchase |

### Total system cost

| Component | MIXI-CUT | Serato |
|-----------|----------|--------|
| Vinyl (pair) | 16 EUR | 80 EUR |
| Software | Free (Mixxx) | 129 EUR (Serato DJ Pro) |
| Hardware | Any soundcard | Serato-compatible |
| **Total** | **~16 EUR** | **~209 EUR** |

## When to Use MIXI-CUT

✅ **Good for:**
- Budget-conscious DJs
- Vinyl cutting enthusiasts
- Open-source advocates
- Embedded/hardware projects
- Educational/research use
- Custom timecode experiments

⚠️ **Not ideal for:**
- Professional touring DJs who need Serato/Traktor integration
- Situations where vinyl must last 500+ plays
- Environments where commercial DJ software is required

## Interoperability

MIXI-CUT vinyl **cannot** be used with commercial DVS software (Serato, Traktor, RekordBox). However:

- ✅ Compatible with **Mixxx** (open-source DJ software, plugin in progress)
- ✅ Compatible with **MIXI** (native support)
- ✅ Compatible with **any custom software** using the reference decoder
- ✅ Compatible with **hardware decoders** (MIDI output)
