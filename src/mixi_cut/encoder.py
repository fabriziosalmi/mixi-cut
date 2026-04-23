from __future__ import annotations

"""Position encoding for the MIXI-CUT protocol.

Encodes absolute vinyl position into bit sequences with Reed-Solomon
error correction, ready for Missing Cycle modulation onto the carrier.

Frame format (v0.3.0):
    13-bit Barker sync word
  + 24-bit position (centisecond resolution, 0-167772s)
  + 16-bit CRC-16 (fast-reject)
  + 32-bit Reed-Solomon parity (4 bytes, GF(2^8))
  = 85 bits per frame
  = 4250 carrier cycles
  = 1.417 seconds at 3 kHz

Multi-rate encoding:
  - Outer groove (0-300s): normal frame rate
  - Inner groove (>300s): 2x frame rate

Velocity subcarrier:
  - 500 Hz AM-modulated onto carrier amplitude
  - Encodes instantaneous speed (1.0x = no modulation)
"""

import numpy as np

from mixi_cut.gf256 import crc16_bytes, rs_encode
from mixi_cut.protocol import (
    BARKER_13,
    MISSING_CYCLE_DEPTH,
    MULTI_RATE_DENSE_FACTOR,
    MULTI_RATE_THRESHOLD_SEC,
    POSITION_CYCLE_INTERVAL,
    RS_PARITY_BYTES,
    SYNC_WORD_BITS,
    TOTAL_FRAME_BITS,
    TRANSITION_SAMPLES,
    VELOCITY_MODULATION_DEPTH,
    VELOCITY_SUBCARRIER_FREQ,
)


def encode_position(position_sec: float) -> list[int]:
    """Encode an absolute position into a bit sequence with CRC + RS protection.

    Frame structure:
        [13-bit Barker sync] [24-bit position] [16-bit CRC-16] [32-bit RS parity]

    Args:
        position_sec: Position in seconds (0.0 - 167772.0)

    Returns:
        List of 85 bits (13 sync + 24 position + 16 CRC + 32 RS parity)
    """
    centisec = int(round(position_sec * 100))
    centisec = min(centisec, 0xFFFFFF)  # 24-bit clamp

    data = [
        (centisec >> 16) & 0xFF,
        (centisec >> 8) & 0xFF,
        centisec & 0xFF,
    ]

    # CRC-16 over position data (fast-reject in decoder)
    crc = crc16_bytes(data)

    # RS encode: data + CRC → data + CRC + RS_parity
    payload = data + crc
    encoded = rs_encode(payload, nsym=RS_PARITY_BYTES)

    # Prepend Barker-13 sync word
    bits = list(BARKER_13)

    # Convert encoded bytes to bits
    for byte_val in encoded:
        for bit_idx in range(7, -1, -1):
            bits.append((byte_val >> bit_idx) & 1)

    return bits


def decode_position_bits(bits: list[int]) -> float | None:
    """Decode a position from a v0.3 frame (85 bits) or v0.2 frame (56 bits).

    For v0.3 (85 bits): strips Barker sync, checks CRC-16, then RS.
    For v0.2 (56 bits): legacy path, RS check only.

    Args:
        bits: List of 85 or 56 bits

    Returns:
        Position in seconds, or None if validation fails
    """
    from mixi_cut.gf256 import crc16_check, rs_check

    if len(bits) == TOTAL_FRAME_BITS:
        # v0.3 frame: strip sync word
        sync = bits[:SYNC_WORD_BITS]
        if sync != BARKER_13:
            return None  # sync mismatch
        payload_bits = bits[SYNC_WORD_BITS:]
    elif len(bits) == 56:
        # v0.2 legacy frame (no sync, no CRC)
        payload_bits = bits
    else:
        return None

    # Reconstruct bytes from bits
    n_bytes = len(payload_bits) // 8
    byte_vals = []
    for i in range(0, n_bytes * 8, 8):
        val = 0
        for j in range(8):
            val = (val << 1) | payload_bits[i + j]
        byte_vals.append(val)

    if len(bits) == TOTAL_FRAME_BITS:
        # v0.3: CRC-16 fast-reject (data = first 3 bytes, CRC = bytes 3-4)
        data_bytes = byte_vals[:3]
        crc_bytes = byte_vals[3:5]
        if not crc16_check(data_bytes, crc_bytes):
            return None  # fast CRC reject — skip expensive RS

    # RS check (full codeword)
    if not rs_check(byte_vals, nsym=RS_PARITY_BYTES):
        return None

    centisec = (byte_vals[0] << 16) | (byte_vals[1] << 8) | byte_vals[2]
    return centisec / 100.0


def make_transition_envelope(n_samples: int) -> np.ndarray:
    """Create a raised-cosine envelope for smooth amplitude dips.

    The envelope transitions smoothly from 1.0 → MISSING_CYCLE_DEPTH → 1.0
    to avoid spectral splatter.

    Args:
        n_samples: Length of one carrier cycle in samples

    Returns:
        Amplitude envelope array
    """
    t = TRANSITION_SAMPLES
    env = np.ones(n_samples)

    if t > 0 and n_samples > 2 * t:
        # Ramp down at start: 1.0 → MISSING_CYCLE_DEPTH
        ramp = 0.5 * (1 + np.cos(np.linspace(0, np.pi, t)))
        ramp = 1.0 - ramp * (1.0 - MISSING_CYCLE_DEPTH)
        env[:t] = ramp

        # Flat bottom
        env[t:n_samples - t] = MISSING_CYCLE_DEPTH

        # Ramp up at end: MISSING_CYCLE_DEPTH → 1.0
        ramp_up = 0.5 * (1 + np.cos(np.linspace(np.pi, 0, t)))
        ramp_up = 1.0 - ramp_up * (1.0 - MISSING_CYCLE_DEPTH)
        env[n_samples - t:] = ramp_up
    else:
        env[:] = MISSING_CYCLE_DEPTH

    return env


def apply_velocity_subcarrier(
    sig_left: np.ndarray,
    sig_right: np.ndarray,
    sr: int,
    speed: float = 1.0,
) -> None:
    """Apply velocity subcarrier AM modulation to carrier signals.

    Encodes the playback speed as amplitude modulation at 500 Hz.
    At speed=1.0x, no modulation. At speed!=1.0x, the 500 Hz envelope
    carries the speed information, bypassing the mass-spring latency.

    Modifies signals in-place.

    Args:
        sig_left: Left channel (modified in-place)
        sig_right: Right channel (modified in-place)
        sr: Sample rate
        speed: Playback speed to encode (1.0 = normal)
    """
    n = len(sig_left)
    t = np.arange(n, dtype=np.float64) / sr

    # Map speed to modulation index: 1.0 → 0.0, 0.0 → -depth, 2.0 → +depth
    normalized = (speed - 1.0)
    modulation_index = np.clip(normalized * VELOCITY_MODULATION_DEPTH, -0.3, 0.3)

    # AM envelope: 1.0 + index * sin(2π * 500 * t)
    envelope = 1.0 + modulation_index * np.sin(2 * np.pi * VELOCITY_SUBCARRIER_FREQ * t)

    sig_left *= envelope
    sig_right *= envelope


def apply_position_encoding(
    sig_left: np.ndarray,
    sig_right: np.ndarray,
    freq: float,
    sr: int,
) -> int:
    """Apply Missing Cycle position encoding with sync + CRC + multi-rate.

    v0.3 features:
      - Barker-13 sync word prepended to each frame
      - CRC-16 parallel to RS for fast-reject
      - Multi-rate: 2x frame density after MULTI_RATE_THRESHOLD_SEC
      - Velocity subcarrier at 500 Hz (constant 1.0x during generation)

    Modifies sig_left and sig_right in-place.

    Args:
        sig_left: Left channel carrier (modified in-place)
        sig_right: Right channel carrier (modified in-place)
        freq: Carrier frequency in Hz
        sr: Sample rate in Hz

    Returns:
        Number of missing cycles encoded
    """
    signal_samples = len(sig_left)
    samples_per_cycle = sr / freq
    cycle_samples = int(round(samples_per_cycle))
    total_cycles = int(signal_samples / samples_per_cycle)

    bits_per_frame = TOTAL_FRAME_BITS
    cycles_per_frame = POSITION_CYCLE_INTERVAL * bits_per_frame

    transition_env = make_transition_envelope(cycle_samples)

    # Apply velocity subcarrier (constant 1.0x during generation)
    apply_velocity_subcarrier(sig_left, sig_right, sr, speed=1.0)

    encoded_count = 0
    cycle_cursor = 0

    while cycle_cursor + cycles_per_frame <= total_cycles:
        position_sec = cycle_cursor / freq

        # Multi-rate: double frame rate on inner groove.
        # Snap to the POSITION_CYCLE_INTERVAL grid so every frame lays bits
        # on the same 50-cycle lattice — keeps sync/CRC/RS decodable regardless
        # of which frame laid the bit down.
        if position_sec > MULTI_RATE_THRESHOLD_SEC:
            dense = cycles_per_frame // MULTI_RATE_DENSE_FACTOR
            current_interval = (dense // POSITION_CYCLE_INTERVAL) * POSITION_CYCLE_INTERVAL
        else:
            current_interval = cycles_per_frame

        bits = encode_position(position_sec)

        for bit_idx, bit_val in enumerate(bits):
            if bit_val == 1:
                target_cycle = cycle_cursor + bit_idx * POSITION_CYCLE_INTERVAL
                sample_start = int(target_cycle * samples_per_cycle)
                sample_end = sample_start + cycle_samples

                if sample_end <= signal_samples:
                    env = transition_env[:sample_end - sample_start]
                    sig_left[sample_start:sample_end] *= env
                    sig_right[sample_start:sample_end] *= env
                    encoded_count += 1

        cycle_cursor += current_interval

    return encoded_count
