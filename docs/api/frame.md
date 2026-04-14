# Frame Format

## v0.3 Frame Structure

```
Bit offset:  0         13        37        53        85
             |---------|---------|---------|---------|
             | Barker  | Position| CRC-16  | RS(4)   |
             | 13 bits | 24 bits | 16 bits | 32 bits |
```

Total: **85 bits** per frame = **4250 carrier cycles** = **1.417 seconds**

## Sync Word: Barker-13

```
1 1 1 1 1 0 0 1 1 0 1 0 1
```

The Barker-13 code has the best known autocorrelation properties for its length. Peak autocorrelation is 13, and all sidelobes are exactly 0 or 1.

## Position Field

24-bit unsigned integer encoding position in centiseconds:

| Bits | Range | Resolution |
|------|-------|------------|
| 24 | 0 -- 167,772 seconds | 0.01 seconds |

This provides 46+ hours of unique position encoding.

## CRC-16

CRC-16/ARC polynomial (0x8005) with initial value 0xFFFF. Computed over the 3 position bytes only.

Purpose: O(1) fast-reject of corrupted frames before running the more expensive Reed-Solomon syndrome computation.

## Reed-Solomon RS(4)

4 parity symbols in GF(2^8) with primitive polynomial 0x11D. The RS codeword covers the position bytes plus CRC bytes (5 data bytes + 4 parity bytes = 9 total).

Can detect up to 4 symbol errors and correct up to 2 symbol errors.

## Modulation: Missing Cycle

Each bit is modulated onto the carrier using amplitude dips:

| Bit | Amplitude | Description |
|-----|-----------|-------------|
| 0 | 1.0 (full) | No change |
| 1 | 0.25 (dip) | Raised-cosine envelope |

Bits are spaced at 50 carrier cycles (~16.7 ms) apart.

## Multi-Rate Encoding

| Position | Frame interval | Frame rate |
|----------|----------------|------------|
| 0 -- 300 s | 4250 cycles | 0.706 frames/s |
| Over 300 s | 2125 cycles | 1.412 frames/s |
