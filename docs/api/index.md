# Protocol Constants

All protocol parameters are defined in `protocol.py`. Every module imports from this single source of truth.

## Carrier

| Constant | Value | Description |
|----------|-------|-------------|
| `SAMPLE_RATE` | 44100 Hz | CD quality |
| `CARRIER_FREQ` | 3000 Hz | Stereo quadrature carrier |
| `AMPLITUDE` | 0.85 | -1.4 dBFS peak |

## Velocity Subcarrier

| Constant | Value | Description |
|----------|-------|-------------|
| `VELOCITY_SUBCARRIER_FREQ` | 500 Hz | AM-modulated onto carrier |
| `VELOCITY_MODULATION_DEPTH` | 0.15 | Max 15% amplitude modulation |

## Frame Format

| Constant | Value | Description |
|----------|-------|-------------|
| `BARKER_13` | `[1,1,1,1,1,0,0,1,1,0,1,0,1]` | Sync word |
| `POSITION_BITS` | 24 | Max 167772 seconds |
| `CRC_BYTES` | 2 | CRC-16 fast-reject |
| `RS_PARITY_BYTES` | 4 | Reed-Solomon parity |
| `TOTAL_FRAME_BITS` | 85 | Complete frame |
| `CYCLES_PER_FRAME` | 4250 | At 50 cycles/bit |
| `SECONDS_PER_FRAME` | 1.417 s | Normal rate |

## Multi-Rate

| Constant | Value | Description |
|----------|-------|-------------|
| `MULTI_RATE_THRESHOLD_SEC` | 300 s | Switch to dense mode |
| `MULTI_RATE_DENSE_FACTOR` | 2 | Double frame rate |

## Decoder

| Constant | Value | Description |
|----------|-------|-------------|
| `PLL_BANDWIDTH_PCT` | 0.08 | 8% of carrier |
| `PLL_Q` | 2.5 | Bandpass quality factor |
| `PLL_LOCK_TAU` | 0.05 s | Lock detector time constant |
| `PLL_AMPLITUDE_GATE` | 0.005 | Coast threshold |
| `PLL_INTEGRAL_DRAIN` | 0.98 | Decay rate when unlocked |
| `MASS_SPRING_INERTIA` | 0.95 | Platter inertia |
| `MASS_SPRING_DEAD_ZONE` | 0.02 | Snap-to-zero threshold |
