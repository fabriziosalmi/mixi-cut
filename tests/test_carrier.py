"""Tests for carrier generation and RIAA pre-emphasis."""

import numpy as np

from mixi_cut.carrier import (
    apply_fades,
    apply_riaa_iir,
    generate_quadrature,
    make_riaa_iir_coeffs,
)
from mixi_cut.protocol import AMPLITUDE, CARRIER_FREQ, SAMPLE_RATE


class TestGenerateQuadrature:
    """Stereo quadrature carrier generation."""

    def test_output_shape(self):
        """Returns two arrays of correct length."""
        left, right = generate_quadrature(1.0)
        assert len(left) == SAMPLE_RATE
        assert len(right) == SAMPLE_RATE

    def test_amplitude(self):
        """Peak amplitude matches AMPLITUDE constant."""
        left, right = generate_quadrature(0.1)
        assert abs(np.max(np.abs(left)) - AMPLITUDE) < 0.01
        assert abs(np.max(np.abs(right)) - AMPLITUDE) < 0.01

    def test_quadrature_phase(self):
        """L and R are 90° out of phase (correlation ≈ 0)."""
        left, right = generate_quadrature(1.0)
        mid = len(left) // 4
        seg = SAMPLE_RATE // 2
        corr = np.corrcoef(left[mid:mid + seg], right[mid:mid + seg])[0, 1]
        assert abs(corr) < 0.02

    def test_frequency(self):
        """Dominant frequency is the carrier frequency."""
        left, _ = generate_quadrature(1.0)
        fft_mag = np.abs(np.fft.rfft(left))
        freqs = np.fft.rfftfreq(len(left), 1.0 / SAMPLE_RATE)
        peak_freq = freqs[np.argmax(fft_mag[1:]) + 1]
        assert abs(peak_freq - CARRIER_FREQ) < 10

    def test_speed_multiplier(self):
        """Speed=2.0 doubles the frequency."""
        left, _ = generate_quadrature(1.0, speed=2.0)
        fft_mag = np.abs(np.fft.rfft(left))
        freqs = np.fft.rfftfreq(len(left), 1.0 / SAMPLE_RATE)
        peak_freq = freqs[np.argmax(fft_mag[1:]) + 1]
        assert abs(peak_freq - CARRIER_FREQ * 2) < 20

    def test_custom_params(self):
        """Custom frequency, amplitude, sample rate."""
        left, right = generate_quadrature(0.5, freq=1000, sr=22050, amplitude=0.5)
        assert len(left) == 11025
        assert np.max(np.abs(left)) <= 0.51

    def test_zero_duration(self):
        """Zero duration produces empty arrays."""
        left, right = generate_quadrature(0.0)
        assert len(left) == 0
        assert len(right) == 0


class TestRIAA:
    """RIAA pre-emphasis filter."""

    def test_output_same_length(self):
        """Output has same length as input."""
        sig = np.sin(2 * np.pi * 1000 * np.arange(SAMPLE_RATE) / SAMPLE_RATE)
        result = apply_riaa_iir(sig)
        assert len(result) == len(sig)

    def test_unity_gain_at_1khz(self):
        """RIAA pre-emphasis is normalized to unity at 1 kHz."""
        t = np.arange(SAMPLE_RATE) / SAMPLE_RATE
        sig = np.sin(2 * np.pi * 1000 * t) * 0.5
        result = apply_riaa_iir(sig)
        # Compare RMS in steady state (skip transient)
        rms_in = np.sqrt(np.mean(sig[SAMPLE_RATE // 2:] ** 2))
        rms_out = np.sqrt(np.mean(result[SAMPLE_RATE // 2:] ** 2))
        gain = rms_out / rms_in
        assert abs(gain - 1.0) < 0.05

    def test_frequency_shaping(self):
        """RIAA filter applies non-flat frequency response (shaping)."""
        t = np.arange(SAMPLE_RATE * 2) / SAMPLE_RATE

        gains = {}
        for freq in [300, 1000, 3000]:
            sig = np.sin(2 * np.pi * freq * t) * 0.3
            result = apply_riaa_iir(sig, SAMPLE_RATE)
            rms_in = np.sqrt(np.mean(sig[SAMPLE_RATE:] ** 2))
            rms_out = np.sqrt(np.mean(result[SAMPLE_RATE:] ** 2))
            gains[freq] = rms_out / rms_in if rms_in > 0 else 0

        # Filter should apply differential gain across frequencies
        # (not a flat passthrough). At 1 kHz it's normalized to ~1.0
        assert abs(gains[1000] - 1.0) < 0.1  # unity at 1 kHz
        # 300 Hz and 3 kHz should differ from 1 kHz significantly
        assert abs(gains[300] - gains[3000]) > 0.1  # non-flat

    def test_coefficients_exist(self):
        """make_riaa_iir_coeffs returns two sections."""
        sec1, sec2 = make_riaa_iir_coeffs(SAMPLE_RATE)
        assert len(sec1) == 4
        assert len(sec2) == 4
        # No NaN or inf
        for s in sec1 + sec2:
            assert np.isfinite(s)


class TestFades:
    """Fade in/out application."""

    def test_fade_in_starts_at_zero(self):
        """Signal starts at zero after fade."""
        n = SAMPLE_RATE
        left = np.ones(n + 5000, dtype=np.float64)
        right = np.ones(n + 5000, dtype=np.float64)
        apply_fades(left, right, lead_in_samples=1000, signal_samples=n, fade_samples=441)
        # First signal sample should be near zero
        assert abs(left[1000]) < 0.01

    def test_fade_out_ends_at_zero(self):
        """Signal ends at zero after fade."""
        n = SAMPLE_RATE
        left = np.ones(n + 5000, dtype=np.float64)
        right = np.ones(n + 5000, dtype=np.float64)
        apply_fades(left, right, lead_in_samples=1000, signal_samples=n, fade_samples=441)
        # Last signal sample should be near zero
        assert abs(left[1000 + n - 1]) < 0.01

    def test_middle_unchanged(self):
        """Middle of signal is not affected by fades."""
        n = SAMPLE_RATE
        left = np.ones(n + 5000, dtype=np.float64) * 0.85
        right = np.ones(n + 5000, dtype=np.float64) * 0.85
        apply_fades(left, right, lead_in_samples=1000, signal_samples=n, fade_samples=441)
        mid = 1000 + n // 2
        assert abs(left[mid] - 0.85) < 0.001
