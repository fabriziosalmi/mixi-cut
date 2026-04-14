"""End-to-end roundtrip test: generate → decode → verify position."""

import os
import tempfile

import numpy as np

from mixi_cut.decoder import Decoder
from mixi_cut.generator import generate_timecode, write_wav
from mixi_cut.protocol import CARRIER_FREQ, SAMPLE_RATE
from mixi_cut.verifier import verify_timecode


class TestRoundtrip:
    """Generate a timecode file, then decode and verify it."""

    def test_generate_and_verify(self):
        """Generated file passes verification."""
        left, right, meta = generate_timecode(
            duration=10, verbose=False
        )
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name
        try:
            write_wav(left, right, path, verbose=False)
            passed, results = verify_timecode(path, strict=True, verbose=False)
            assert passed, f"Verification failed: {results}"
        finally:
            os.unlink(path)

    def test_generate_loop_mode(self):
        """Loop mode produces phase-continuous signal."""
        left, right, meta = generate_timecode(
            duration=5, loop=True, verbose=False
        )
        assert "phase_error_deg" in meta
        assert meta["phase_error_deg"] < 1.0  # near-zero phase error

    def test_generate_riaa(self):
        """RIAA mode generates without error."""
        left, right, meta = generate_timecode(
            duration=5, apply_riaa=True, verbose=False
        )
        assert meta["riaa"] is True
        # Signal should not clip
        assert np.max(np.abs(left)) <= 1.0
        assert np.max(np.abs(right)) <= 1.0

    def test_decode_speed_from_generated(self):
        """Decoder locks and reports ~1.0 speed on generated signal."""
        left, right, meta = generate_timecode(
            duration=5, verbose=False
        )
        # Extract signal region (skip lead-in/lead-out)
        lead_in = int(2.0 * SAMPLE_RATE)
        signal_samples = meta["signal_samples"]
        sig_l = left[lead_in:lead_in + signal_samples]
        sig_r = right[lead_in:lead_in + signal_samples]

        dec = Decoder()
        block = 128
        speeds = []
        locks = []
        for i in range(0, len(sig_l), block):
            j = min(i + block, len(sig_l))
            s, lk, _ = dec.process(sig_l[i:j], sig_r[i:j])
            speeds.append(s)
            locks.append(lk)

        # Last quarter should be locked and at 1.0x
        n = len(speeds)
        avg_speed = np.mean(speeds[3 * n // 4:])
        avg_lock = np.mean(locks[3 * n // 4:])

        assert abs(avg_speed - 1.0) < 0.05, f"Speed: {avg_speed}"
        assert avg_lock > 0.7, f"Lock: {avg_lock}"

    def test_metadata_correctness(self):
        """Generator metadata has correct fields."""
        _, _, meta = generate_timecode(duration=10, verbose=False)
        assert meta["duration"] == 10
        assert meta["freq"] == CARRIER_FREQ
        assert meta["sr"] == SAMPLE_RATE
        assert meta["encoded_cycles"] > 0
        assert meta["total_cycles"] > 0
        assert meta["signal_samples"] > 0
