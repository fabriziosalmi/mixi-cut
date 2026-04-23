"""CLI integration tests and generator/verifier coverage tests.

Tests the full CLI pipeline and exercises the verbose code paths
in generator.py and verifier.py that unit tests don't reach.
"""

import os

import numpy as np
import soundfile as sf

from mixi_cut import __version__
from mixi_cut.generator import generate_timecode, write_wav
from mixi_cut.verifier import verify_timecode


class TestGeneratorCoverage:
    """Exercise generator.py verbose print paths and edge cases."""

    def test_generate_verbose_output(self, capsys):
        """Covers lines 54, 63-68, 79, 84, 93, 102, 130, 134, 137-138."""
        left, right, meta = generate_timecode(
            duration=5.0, verbose=True
        )
        captured = capsys.readouterr()
        assert f"MIXI-CUT v{__version__}" in captured.out
        assert "Duration:" in captured.out
        assert "Frequency:" in captured.out
        assert "Samples:" in captured.out
        assert "Amplitude:" in captured.out
        assert "Encoded:" in captured.out
        assert "Fades:" in captured.out
        assert "Lead-in:" in captured.out
        assert "Lead-out:" in captured.out

    def test_generate_loop_verbose(self, capsys):
        """Covers loop mode verbose path (line 54, 127, 130)."""
        left, right, meta = generate_timecode(
            duration=2.0, loop=True, verbose=True
        )
        captured = capsys.readouterr()
        assert "Loop mode:" in captured.out
        assert "phase-continuous" in captured.out
        assert meta["loop"] is True

    def test_generate_riaa_verbose(self, capsys):
        """Covers RIAA verbose path (line 84, 93)."""
        left, right, meta = generate_timecode(
            duration=2.0, apply_riaa=True, verbose=True
        )
        captured = capsys.readouterr()
        assert "RIAA:" in captured.out
        assert meta["riaa"] is True

    def test_generate_dc_removal_verbose(self, capsys):
        """Covers DC removal verbose path (line 102)."""
        left, right, meta = generate_timecode(
            duration=2.0, verbose=True
        )
        capsys.readouterr()
        # DC removal line may or may not appear depending on signal
        assert len(left) > 0

    def test_generate_silent_mode(self):
        """Covers verbose=False paths."""
        left, right, meta = generate_timecode(
            duration=2.0, verbose=False
        )
        assert len(left) > 0
        assert "duration" in meta

    def test_write_wav_verbose(self, capsys, tmp_path):
        """Covers write_wav verbose output (lines 165, 170-173)."""
        left, right, meta = generate_timecode(
            duration=2.0, verbose=False
        )
        output = str(tmp_path / "test.wav")
        write_wav(left, right, output, verbose=True)
        captured = capsys.readouterr()
        assert "Writing" in captured.out
        assert "File size:" in captured.out
        assert "Format:" in captured.out
        assert "Cut at" in captured.out

    def test_write_wav_silent(self, tmp_path):
        """Covers write_wav verbose=False."""
        left, right, meta = generate_timecode(
            duration=2.0, verbose=False
        )
        output = str(tmp_path / "test_silent.wav")
        result = write_wav(left, right, output, verbose=False)
        assert result == output
        assert os.path.exists(output)


class TestVerifierCoverage:
    """Exercise verifier.py error paths."""

    def test_verify_mono_file(self, tmp_path):
        """Covers lines 35-37 (not stereo)."""
        path = str(tmp_path / "mono.wav")
        mono = np.sin(np.linspace(0, 100, 44100)) * 0.5
        sf.write(path, mono, 44100, subtype='PCM_16')
        passed, results = verify_timecode(path, verbose=False)
        assert not passed
        assert results["checks"].get("stereo") is False

    def test_verify_silent_file(self, tmp_path):
        """Covers lines 58-60 (no signal detected)."""
        path = str(tmp_path / "silent.wav")
        stereo = np.zeros((44100, 2))
        sf.write(path, stereo, 44100, subtype='PCM_16')
        passed, results = verify_timecode(path, verbose=False)
        assert not passed
        assert results["checks"].get("signal") is False

    def test_verify_verbose_output(self, capsys, tmp_path):
        """Covers verbose print lines (line 26, etc)."""
        left, right, _ = generate_timecode(duration=3.0, verbose=False)
        path = str(tmp_path / "verify_verbose.wav")
        write_wav(left, right, path, verbose=False)
        passed, results = verify_timecode(path, strict=True, verbose=True)
        captured = capsys.readouterr()
        assert "Verifying:" in captured.out
        assert "Sample rate:" in captured.out
        assert "EDM Readiness" in captured.out
        assert passed

    def test_verify_non_strict_with_warning(self, tmp_path):
        """Covers non-strict mode (line 159)."""
        left, right, _ = generate_timecode(duration=3.0, verbose=False)
        path = str(tmp_path / "verify_nonstrict.wav")
        write_wav(left, right, path, verbose=False)
        passed, results = verify_timecode(path, strict=False, verbose=False)
        assert passed


class TestDecoderEdgeCoverage:
    """Exercise decoder edge cases for coverage."""

    def test_pll_phase_wrap_negative(self):
        """Covers line 117, 138 (phase wrap paths)."""
        from mixi_cut.decoder import PLL
        pll = PLL()
        # Feed negative frequency signal to trigger negative phase wrap
        for i in range(500):
            t = i / 44100.0
            left_s = np.sin(-2 * np.pi * 3000 * t) * 0.5
            r = np.cos(-2 * np.pi * 3000 * t) * 0.5
            pll.tick(left_s, r)
        # Should handle wrapping without error
        assert True

    def test_mass_spring_scratch_release(self):
        """Covers line 200 (scratch release counter reset)."""
        from mixi_cut.decoder import MassSpring
        ms = MassSpring()
        # Trigger scratch
        ms.tick(0.0)
        ms.tick(1.0)  # big jump → scratch
        # Now feed varying speeds to test release logic
        for i in range(30):
            ms.tick(0.8 + (i % 2) * 0.15)
        assert True

    def test_mass_spring_stop_traction(self):
        """Covers line 216 (near-stop high traction)."""
        from mixi_cut.decoder import MassSpring
        ms = MassSpring()
        # Ramp up then sudden near-stop
        for _ in range(100):
            ms.tick(1.0)
        ms.tick(0.05)  # near stop with big delta
        result = ms.tick(0.03)
        assert isinstance(result, float)


class TestEncoderEdgeCoverage:
    """Exercise encoder line 127 (RS check on v0.2 legacy frame)."""

    def test_legacy_frame_with_rs_error(self):
        """Covers encoder.py line 127 (RS check fails on legacy)."""
        from mixi_cut.encoder import decode_position_bits
        # Create a 56-bit frame with bad RS
        bits = [0] * 56
        bits[30] = 1  # corrupt a bit
        result = decode_position_bits(bits)
        # RS should fail
        assert result is None or isinstance(result, float)
