# Quick Start

## Generate a timecode

```bash
# Full 15-minute DJ vinyl
mixi-cut generate --preset dj-12inch --output side_a.wav

# Quick 60-second test
mixi-cut generate --preset test-cut --output test.wav

# 7-inch single at 45 RPM
mixi-cut generate --preset dj-7inch --output single.wav
```

## Verify before cutting

Always verify the WAV before sending it to the lathe:

```bash
mixi-cut verify side_a.wav --strict
```

All 6 checks must pass:

| Check | What it verifies |
|-------|------------------|
| dc_offset | DC component removed |
| quadrature | 90-degree L/R phase |
| frequency | Carrier at 3000 Hz |
| position_encoding | Missing cycle frames present |
| balance | L/R amplitude matched |
| lead_in | Silent lead-in for needle placement |

## Decode (reference)

```bash
mixi-cut decode side_a.wav
```

Output:

```
t=   0.0s  speed=+1.000x  lock=[████████████████████] 1.000  pos=0.00s
t=   1.0s  speed=+1.000x  lock=[████████████████████] 1.000  pos=1.00s
t=   2.0s  speed=+1.000x  lock=[████████████████████] 1.000  pos=2.00s
```

## Presets

| Preset | Duration | RPM | RIAA | Loop | Use case |
|--------|----------|-----|------|------|----------|
| `dj-12inch` | 15 min | 33.3 | No | Yes | Full side DJ vinyl |
| `dj-7inch` | 4 min | 45 | No | Yes | Single side 7-inch |
| `test-cut` | 60 s | 33.3 | No | No | Quick test iteration |
| `phono` | 15 min | 33.3 | Yes | Yes | PHONO input with RIAA |
| `locked-groove` | 1.8 s | 33.3 | No | Yes | Single revolution |
