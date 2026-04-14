# MIXI-CUT Cutting Guide

> Complete guide for cutting MIXI-CUT timecode onto vinyl using a lathe cutting machine.

## Overview

MIXI-CUT timecodes can be cut onto vinyl using any lathe cutting machine that accepts WAV audio input. The signal is designed to survive the physical limitations of the lathe-cut process while remaining decodable by any MIXI-CUT–compatible decoder.

## Preparing the Signal

### Generate the timecode

```bash
# Standard DJ 12" — full side, 15 minutes
mixi-cut generate --preset dj-12inch --output side_a.wav

# Quick test — 60 seconds for iteration
mixi-cut generate --preset test-cut --output test.wav

# PHONO input — with RIAA pre-emphasis
mixi-cut generate --preset phono --output side_a_phono.wav

# 7" single — 45 RPM
mixi-cut generate --preset dj-7inch --output seven_inch.wav
```

### Verify before cutting

Always verify the WAV file before sending it to the lathe:

```bash
mixi-cut verify side_a.wav --strict
```

All checks should pass:
- ✅ Stereo (2 channels)
- ✅ Carrier frequency at 3000 Hz
- ✅ Quadrature phase (L/R correlation ≈ 0)
- ✅ Position encoding detected
- ✅ Channel balance (±5%)
- ✅ DC offset negligible
- ✅ Lead-in present (≥1s)

## Lathe Parameters

### Recommended settings

| Parameter | Value | Notes |
|-----------|-------|-------|
| **RPM** | 33⅓ | Standard DJ speed |
| **Groove spacing** | 200 lines/inch | Wider than music vinyl for robustness |
| **Cutting depth** | Moderate | Deeper = better SNR, but more wear |
| **Level** | +3 dB | The signal is at -1.4 dBFS; boost slightly |
| **Channels** | Stereo | Both channels are required |
| **RIAA** | OFF (default) | Unless using `--riaa` preset |

### For different formats

| Format | RPM | Duration | Groove spacing |
|--------|-----|----------|---------------|
| 12" DJ | 33⅓ | 15 min | 200 LPI |
| 12" Extended | 33⅓ | 20 min | 250 LPI (tighter) |
| 7" Single | 45 | 4 min | 200 LPI |
| 10" | 33⅓ | 10 min | 200 LPI |

## Cutting Process

### Step 1: Material selection

| Material | Quality | Cost | Recommendation |
|----------|---------|------|----------------|
| **PVC** | Best | ~8 EUR | ✅ Recommended for DJ use |
| **Polycarbonate** | Good | ~5 EUR | Good for test cuts |
| **PET** | Fair | ~3 EUR | Budget option |
| **Lacquer** | Excellent | ~15 EUR | Professional, but expensive |

### Step 2: Lathe setup

1. Load the WAV file into the lathe's audio system
2. Set groove spacing to 200 LPI
3. Set cutting depth to moderate
4. Set level to +3 dB from nominal
5. Ensure stereo cutting head is calibrated

### Step 3: Test cut

Before cutting a full side:
1. Cut a 60-second test (`mixi-cut generate --preset test-cut`)
2. Play back on a turntable
3. Check decoder locks within 2-3 seconds
4. Verify position encoding is readable

### Step 4: Full cut

1. Start with the needle at the outer groove
2. The 2-second lead-in silence allows needle placement
3. Cut the full duration
4. The 1-second lead-out provides a clean ending

## Playback Testing

### Required equipment

- DJ turntable (Technics SL-1200 recommended)
- DJ cartridge (Ortofon Concorde, Shure M44-7, or similar)
- Audio interface with LINE input (or PHONO if using `--riaa`)
- MIXI-CUT decoder software

### Testing procedure

1. Place the stylus in the lead-in groove
2. Start the turntable
3. The decoder should lock within 2-3 seconds
4. Verify:
   - Speed reads 1.000x ±0.005
   - Lock quality > 0.8
   - Position increases monotonically
5. Test scratch response:
   - Forward/back scratch → speed should follow
   - Stop → speed should reach 0 within 3ms
   - Backspin → speed should go negative

### Troubleshooting

| Problem | Possible cause | Solution |
|---------|---------------|----------|
| No lock | Wrong input (PHONO vs LINE) | Check audio routing |
| Lock but wrong speed | RPM mismatch | Verify turntable is at 33⅓ |
| Dropouts | Groove damage or dust | Clean vinyl, check stylus |
| Position errors | Severe groove noise | Re-cut with deeper groove |
| Only one channel | Stylus alignment | Check cartridge mounting |

## Quality Benchmarks

After cutting, the playback signal should achieve:

| Metric | Target | Acceptable |
|--------|--------|------------|
| Lock quality | > 0.9 | > 0.7 |
| Speed accuracy | ±0.005x | ±0.02x |
| Position error | < 10 ms | < 50 ms |
| SNR | > 20 dB | > 12 dB |
| Lock time | < 2s | < 5s |

## Services

### Recommended lathe cutting services

| Service | Location | Notes |
|---------|----------|-------|
| Vinylify | EU | Custom vinyl, single copies |
| Rand Muzik | UK | Specializes in lathe cuts |
| Lathe-Cut Records | US | Good for small runs |

> **Note**: When ordering, specify "Stereo WAV, no processing, cut flat (no RIAA)" unless you generated with `--riaa`.

## Cost Analysis

| Item | MIXI-CUT | Serato CV02 |
|------|----------|-------------|
| Vinyl cost | ~8 EUR (single cut) | ~40 EUR (retail) |
| Signal quality | Optimized for lathe cut | Optimized for pressing |
| Availability | Generate + cut anytime | Buy from dealer |
| Customization | Full control | None |
| Replacement | Re-cut at will | Buy new |
