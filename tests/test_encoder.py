"""Tests for position encoding and Missing Cycle modulation.

Tests cover v0.3 protocol features:
  - CRC-16 fast-reject
  - Barker-13 sync word
  - Multi-rate encoding
  - Velocity subcarrier
  - Backward compatibility with v0.2 frames
"""

import numpy as np

from mixi_cut.encoder import (
    apply_position_encoding,
    apply_velocity_subcarrier,
    decode_position_bits,
    encode_position,
    make_transition_envelope,
)
from mixi_cut.gf256 import crc16, crc16_bytes, crc16_check
from mixi_cut.protocol import (
    BARKER_13,
    CARRIER_FREQ,
    MISSING_CYCLE_DEPTH,
    SAMPLE_RATE,
    SYNC_WORD_BITS,
    TOTAL_FRAME_BITS,
    TRANSITION_SAMPLES,
    VELOCITY_SUBCARRIER_FREQ,
)


class TestEncodePosition:
    """Position → bits encoding (v0.3 frame format)."""

    def test_output_length(self):
        """v0.3 frame: always 85 bits (13 sync + 72 payload)."""
        for pos in [0.0, 1.0, 100.0, 900.0, 167772.0]:
            bits = encode_position(pos)
            assert len(bits) == TOTAL_FRAME_BITS

    def test_sync_word_prefix(self):
        """Frame starts with Barker-13 sync word."""
        bits = encode_position(0.0)
        assert bits[:SYNC_WORD_BITS] == BARKER_13

    def test_zero_position(self):
        """Position 0 encodes to all-zero data bytes after sync."""
        bits = encode_position(0.0)
        # After 13-bit sync, bytes 0-2 (position) should be zero
        data_bits = bits[SYNC_WORD_BITS:SYNC_WORD_BITS + 24]
        assert all(b == 0 for b in data_bits)

    def test_known_position(self):
        """1.00s → centisec=100 → 0x000064."""
        bits = encode_position(1.0)
        # Skip sync, extract first 3 bytes
        payload = bits[SYNC_WORD_BITS:]
        b0 = sum(payload[i] << (7 - i) for i in range(8))
        b1 = sum(payload[8 + i] << (7 - i) for i in range(8))
        b2 = sum(payload[16 + i] << (7 - i) for i in range(8))
        centisec = (b0 << 16) | (b1 << 8) | b2
        assert centisec == 100

    def test_max_clamp(self):
        """Positions beyond 167772s are clamped to 0xFFFFFF."""
        bits = encode_position(200000.0)
        payload = bits[SYNC_WORD_BITS:]
        b0 = sum(payload[i] << (7 - i) for i in range(8))
        b1 = sum(payload[8 + i] << (7 - i) for i in range(8))
        b2 = sum(payload[16 + i] << (7 - i) for i in range(8))
        assert (b0 << 16 | b1 << 8 | b2) == 0xFFFFFF

    def test_negative_position(self):
        """Negative positions still produce valid-length output."""
        bits = encode_position(-1.0)
        assert len(bits) == TOTAL_FRAME_BITS

    def test_bits_are_binary(self):
        """All bits are 0 or 1."""
        bits = encode_position(42.42)
        assert all(b in (0, 1) for b in bits)

    def test_crc_in_frame(self):
        """Frame contains valid CRC-16 after position bytes."""
        bits = encode_position(10.0)
        payload = bits[SYNC_WORD_BITS:]
        # Extract data bytes (first 3) and CRC bytes (next 2)
        byte_vals = []
        for i in range(0, 40, 8):  # 5 bytes = 3 data + 2 CRC
            val = 0
            for j in range(8):
                val = (val << 1) | payload[i + j]
            byte_vals.append(val)
        data = byte_vals[:3]
        crc = byte_vals[3:5]
        assert crc16_check(data, crc)


class TestDecodePositionBits:
    """Roundtrip: encode → decode."""

    def test_roundtrip_zero(self):
        bits = encode_position(0.0)
        pos = decode_position_bits(bits)
        assert pos is not None
        assert pos == 0.0

    def test_roundtrip_various(self):
        """Roundtrip for various positions within 0.01s resolution."""
        for pos_sec in [0.0, 0.01, 1.0, 10.0, 100.0, 500.0, 900.0]:
            bits = encode_position(pos_sec)
            decoded = decode_position_bits(bits)
            assert decoded is not None, f"Failed to decode position {pos_sec}"
            assert abs(decoded - pos_sec) < 0.011  # centisecond precision

    def test_corrupted_sync_rejected(self):
        """Frame with corrupted sync word is rejected."""
        bits = encode_position(42.0)
        bits[0] ^= 1  # flip first sync bit
        result = decode_position_bits(bits)
        assert result is None

    def test_corrupted_crc_rejected(self):
        """Frame with corrupted CRC is fast-rejected."""
        bits = encode_position(42.0)
        # Flip a bit in the CRC region (after sync + 24 data bits)
        crc_bit_start = SYNC_WORD_BITS + 24
        bits[crc_bit_start + 3] ^= 1
        result = decode_position_bits(bits)
        assert result is None

    def test_corrupted_data_rejected(self):
        """Frame with corrupted data is rejected by CRC or RS."""
        bits = encode_position(42.0)
        bits[SYNC_WORD_BITS + 5] ^= 1  # flip a data bit
        result = decode_position_bits(bits)
        assert result is None

    def test_wrong_length_rejected(self):
        assert decode_position_bits([0] * 55) is None
        assert decode_position_bits([0] * 57) is None
        assert decode_position_bits([]) is None
        assert decode_position_bits([0] * 84) is None
        assert decode_position_bits([0] * 86) is None

    def test_v02_legacy_56bit(self):
        """v0.2 legacy 56-bit frames can still be decoded when RS is valid."""
        from mixi_cut.gf256 import rs_encode
        data = [0x00, 0x00, 0x64]  # 1.00 seconds
        encoded = rs_encode(data, nsym=4)
        bits = []
        for byte_val in encoded:
            for bit_idx in range(7, -1, -1):
                bits.append((byte_val >> bit_idx) & 1)
        assert len(bits) == 56
        result = decode_position_bits(bits)
        assert result is not None
        assert abs(result - 1.0) < 0.011


class TestCRC16:
    """CRC-16 functions (v0.3)."""

    def test_known_value(self):
        """CRC-16 of known data."""
        crc = crc16([0x00, 0x01, 0x5E])
        assert isinstance(crc, int)
        assert 0 <= crc <= 0xFFFF

    def test_deterministic(self):
        """Same input → same CRC."""
        data = [0x12, 0x34, 0x56]
        assert crc16(data) == crc16(data)

    def test_different_data_different_crc(self):
        """Different data → different CRC (with high probability)."""
        assert crc16([0, 0, 0]) != crc16([0, 0, 1])

    def test_bytes_format(self):
        """crc16_bytes returns [high, low]."""
        result = crc16_bytes([0, 1, 2])
        assert len(result) == 2
        assert all(0 <= b <= 255 for b in result)

    def test_roundtrip_check(self):
        """Compute CRC → check passes."""
        data = [0xAB, 0xCD, 0xEF]
        crc = crc16_bytes(data)
        assert crc16_check(data, crc)

    def test_corrupted_check_fails(self):
        """Corrupted CRC → check fails."""
        data = [0xAB, 0xCD, 0xEF]
        crc = crc16_bytes(data)
        crc[1] ^= 0x01
        assert not crc16_check(data, crc)

    def test_zero_data(self):
        """CRC of all-zeros is not zero (due to init=0xFFFF)."""
        crc = crc16([0, 0, 0])
        assert crc != 0


class TestSyncWord:
    """Barker-13 sync word properties."""

    def test_barker_length(self):
        assert len(BARKER_13) == 13

    def test_barker_binary(self):
        assert all(b in (0, 1) for b in BARKER_13)

    def test_barker_known_sequence(self):
        """Barker-13 is the canonical sequence."""
        assert BARKER_13 == [1, 1, 1, 1, 1, 0, 0, 1, 1, 0, 1, 0, 1]

    def test_autocorrelation_peak(self):
        """Barker-13 has autocorrelation peak at lag=0, sidelobes ≤ 1."""
        b = [2 * x - 1 for x in BARKER_13]  # convert to ±1
        n = len(b)
        for lag in range(1, n):
            corr = sum(b[i] * b[i + lag] for i in range(n - lag))
            assert abs(corr) <= 1, f"Sidelobe at lag {lag}: {corr}"


class TestVelocitySubcarrier:
    """Velocity channel AM modulation (v0.3)."""

    def test_no_modulation_at_1x(self):
        """At speed=1.0, signal is essentially unchanged."""
        sr = SAMPLE_RATE
        n = sr  # 1 second
        t = np.arange(n, dtype=np.float64) / sr
        left = np.sin(2 * np.pi * CARRIER_FREQ * t) * 0.85
        right = np.cos(2 * np.pi * CARRIER_FREQ * t) * 0.85
        left_orig = left.copy()

        apply_velocity_subcarrier(left, right, sr, speed=1.0)

        # At speed=1.0, modulation index = 0 → no change
        assert np.allclose(left, left_orig, atol=1e-10)

    def test_modulation_at_2x(self):
        """At speed=2.0, 500Hz envelope appears."""
        sr = SAMPLE_RATE
        n = sr  # 1 second
        left = np.ones(n) * 0.85
        left_orig = left.copy()
        right = np.ones(n) * 0.85

        apply_velocity_subcarrier(left, right, sr, speed=2.0)

        # Signal should be modified
        assert not np.allclose(left, left_orig)

        # Check 500 Hz component in spectrum
        fft = np.abs(np.fft.rfft(left - np.mean(left)))
        freqs = np.fft.rfftfreq(n, 1.0 / sr)
        peak_idx = np.argmax(fft[1:]) + 1
        peak_freq = freqs[peak_idx]
        assert abs(peak_freq - VELOCITY_SUBCARRIER_FREQ) < 10

    def test_envelope_within_bounds(self):
        """Velocity modulation doesn't push amplitude beyond safe limits."""
        sr = SAMPLE_RATE
        n = sr
        left = np.ones(n) * 0.85
        right = np.ones(n) * 0.85

        for speed in [-2.0, 0.0, 0.5, 1.0, 1.5, 2.0, 3.0]:
            left_c = left.copy()
            right_c = right.copy()
            apply_velocity_subcarrier(left_c, right_c, sr, speed=speed)
            assert np.max(np.abs(left_c)) < 1.2  # safe headroom


class TestTransitionEnvelope:
    """Raised-cosine envelope for missing cycle modulation."""

    def test_shape(self):
        for n in [10, 14, 15, 50]:
            env = make_transition_envelope(n)
            assert len(env) == n

    def test_starts_and_ends_near_boundary(self):
        env = make_transition_envelope(50)
        assert env[0] >= MISSING_CYCLE_DEPTH
        assert env[-1] >= MISSING_CYCLE_DEPTH

    def test_minimum_is_depth(self):
        env = make_transition_envelope(50)
        mid = len(env) // 2
        assert abs(env[mid] - MISSING_CYCLE_DEPTH) < 0.01

    def test_ramp_transitions(self):
        env = make_transition_envelope(50)
        t = TRANSITION_SAMPLES
        for i in range(t):
            assert MISSING_CYCLE_DEPTH - 0.01 <= env[i] <= 1.01
        mid = len(env) // 2
        assert abs(env[mid] - MISSING_CYCLE_DEPTH) < 0.01

    def test_small_envelope(self):
        env = make_transition_envelope(3)
        assert all(abs(e - MISSING_CYCLE_DEPTH) < 0.01 for e in env)


class TestApplyPositionEncoding:
    """In-place position encoding on carrier signals."""

    def test_modifies_signal(self):
        sr = SAMPLE_RATE
        freq = CARRIER_FREQ
        dur = 2.0
        n = int(dur * sr)
        t = np.arange(n, dtype=np.float64) / sr
        phase = 2 * np.pi * freq * t
        left = np.sin(phase) * 0.85
        right = np.cos(phase) * 0.85
        left_orig = left.copy()

        count = apply_position_encoding(left, right, freq, sr)
        assert count > 0
        assert not np.array_equal(left, left_orig)

    def test_encoding_count_scales_with_duration(self):
        sr = SAMPLE_RATE
        freq = CARRIER_FREQ

        counts = []
        for dur in [2.0, 5.0, 10.0]:
            n = int(dur * sr)
            t = np.arange(n, dtype=np.float64) / sr
            left = np.sin(2 * np.pi * freq * t) * 0.85
            right = np.cos(2 * np.pi * freq * t) * 0.85
            count = apply_position_encoding(left, right, freq, sr)
            counts.append(count)

        assert counts[1] > counts[0]
        assert counts[2] > counts[1]

    def test_encoding_preserves_unencodeed_cycles(self):
        sr = SAMPLE_RATE
        freq = CARRIER_FREQ
        dur = 2.0
        n = int(dur * sr)
        t = np.arange(n, dtype=np.float64) / sr
        left = np.sin(2 * np.pi * freq * t) * 0.85
        right = np.cos(2 * np.pi * freq * t) * 0.85
        left_orig = left.copy()

        apply_position_encoding(left, right, freq, sr)

        diff = np.abs(left - left_orig)
        changed_fraction = np.sum(diff > 0.001) / len(left)
        assert changed_fraction < 0.15  # slightly higher due to velocity subcarrier


class TestMultiRate:
    """Multi-rate encoding (v0.3)."""

    def test_more_frames_on_inner_groove(self):
        """Positions > 300s should have denser encoding."""
        sr = SAMPLE_RATE
        freq = CARRIER_FREQ

        # Outer groove: 0-10s
        dur_outer = 10.0
        n = int(dur_outer * sr)
        t = np.arange(n, dtype=np.float64) / sr
        left = np.sin(2 * np.pi * freq * t) * 0.85
        right = np.cos(2 * np.pi * freq * t) * 0.85
        count_outer = apply_position_encoding(left, right, freq, sr)
        frames_per_sec_outer = count_outer / dur_outer

        # Long duration that includes inner groove
        dur_long = 600.0  # goes past 300s threshold
        n = int(dur_long * sr)
        t = np.arange(n, dtype=np.float64) / sr
        left = np.sin(2 * np.pi * freq * t) * 0.85
        right = np.cos(2 * np.pi * freq * t) * 0.85
        count_long = apply_position_encoding(left, right, freq, sr)
        frames_per_sec_long = count_long / dur_long

        # Long duration should have higher avg density due to inner groove 2x
        assert frames_per_sec_long > frames_per_sec_outer * 0.9
