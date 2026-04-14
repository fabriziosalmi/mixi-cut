"""Carrier signal generation and RIAA pre-emphasis.

Generates stereo quadrature signals (L=sin, R=cos) and applies
RIAA recording curve via cascaded IIR filters.
"""

import numpy as np

from mixi_cut.protocol import (
    AMPLITUDE,
    CARRIER_FREQ,
    FADE_SAMPLES,
    SAMPLE_RATE,
)


def generate_quadrature(
    duration: float,
    freq: float = CARRIER_FREQ,
    sr: int = SAMPLE_RATE,
    amplitude: float = AMPLITUDE,
    speed: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate stereo quadrature carrier signals.

    Args:
        duration: Signal duration in seconds
        freq: Carrier frequency in Hz
        sr: Sample rate in Hz
        amplitude: Peak amplitude (linear)
        speed: Playback speed multiplier

    Returns:
        (left, right) arrays — L=sin, R=cos
    """
    n = int(duration * sr)
    t = np.arange(n, dtype=np.float64) / sr
    phase = 2 * np.pi * freq * speed * t
    return np.sin(phase) * amplitude, np.cos(phase) * amplitude


def make_riaa_iir_coeffs(sr: int) -> tuple:
    """Design cascaded IIR sections for RIAA recording pre-emphasis.

    Uses bilinear transform of the analog RIAA transfer function.
    Two first-order sections: high-shelf (t1/t2) + high-boost (t3).

    Args:
        sr: Sample rate in Hz

    Returns:
        (section1, section2) — each is (a_num, b_num, a_den, b_den)
    """
    t1, t2, t3 = 3180e-6, 318e-6, 75e-6

    def prewarp(tau):
        return 2.0 * sr * np.tan(1.0 / (2.0 * sr * tau))

    w1 = prewarp(t1)
    w2 = prewarp(t2)
    w3 = prewarp(t3)

    # Section 1: (s + w2) / (s + w1)
    a1_num = 2 * sr + w2
    b1_num = -2 * sr + w2
    a1_den = 2 * sr + w1
    b1_den = -2 * sr + w1

    # Section 2: (s + w3) / s
    a2_num = 2 * sr + w3
    b2_num = -2 * sr + w3
    a2_den = 2 * sr
    b2_den = -2 * sr

    return (a1_num, b1_num, a1_den, b1_den), (a2_num, b2_num, a2_den, b2_den)


def _apply_iir_section(signal: np.ndarray, section: tuple) -> np.ndarray:
    """Apply a single first-order IIR section to a signal.

    Args:
        signal: Input signal array
        section: (a_num, b_num, a_den, b_den) coefficients

    Returns:
        Filtered signal
    """
    result = signal.copy()
    b0 = section[0] / section[2]
    b1 = section[1] / section[2]
    a1 = section[3] / section[2]
    z1 = 0.0
    for i in range(len(result)):
        x = result[i]
        y = b0 * x + z1
        z1 = b1 * x - a1 * y
        result[i] = y
    return result


def apply_riaa_iir(signal: np.ndarray, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Apply RIAA pre-emphasis using cascaded IIR filters.

    O(1) memory — processes sample-by-sample.
    Normalizes to unity gain at 1 kHz.

    Args:
        signal: Input signal array
        sr: Sample rate in Hz

    Returns:
        Pre-emphasized signal
    """
    sec1, sec2 = make_riaa_iir_coeffs(sr)

    result = _apply_iir_section(signal, sec1)
    result = _apply_iir_section(result, sec2)

    # Normalize: unity gain at 1 kHz
    test_len = sr
    t_test = np.arange(test_len) / sr
    test_in = np.sin(2 * np.pi * 1000 * t_test)
    test_out = _apply_iir_section(test_in, sec1)
    test_out = _apply_iir_section(test_out, sec2)

    rms_in = np.sqrt(np.mean(test_in[sr // 2:] ** 2))
    rms_out = np.sqrt(np.mean(test_out[sr // 2:] ** 2))
    gain_1k = rms_out / rms_in if rms_in > 0 else 1.0

    result /= gain_1k
    return result


def apply_fades(
    left: np.ndarray,
    right: np.ndarray,
    lead_in_samples: int,
    signal_samples: int,
    fade_samples: int = FADE_SAMPLES,
) -> None:
    """Apply quadratic fade-in and fade-out to avoid clicks.

    Modifies arrays in-place.

    Args:
        left: Left channel array (full length with lead-in/out)
        right: Right channel array
        lead_in_samples: Number of lead-in silence samples
        signal_samples: Number of signal samples
        fade_samples: Number of fade transition samples
    """
    fade = np.linspace(0, 1, fade_samples) ** 2

    # Fade in
    s = lead_in_samples
    left[s:s + fade_samples] *= fade
    right[s:s + fade_samples] *= fade

    # Fade out
    e = lead_in_samples + signal_samples
    left[e - fade_samples:e] *= fade[::-1]
    right[e - fade_samples:e] *= fade[::-1]
