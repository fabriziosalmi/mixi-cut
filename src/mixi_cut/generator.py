"""Timecode WAV generator — orchestrates carrier + encoder + RIAA.

This is the main generation pipeline. It creates a complete timecode WAV
file ready for vinyl lathe cutting.
"""

import numpy as np
import soundfile as sf

from mixi_cut import __version__
from mixi_cut.carrier import apply_fades, apply_riaa_iir
from mixi_cut.encoder import apply_position_encoding
from mixi_cut.protocol import (
    AMPLITUDE,
    CARRIER_FREQ,
    FADE_SAMPLES,
    LEAD_IN_SECONDS,
    LEAD_OUT_SECONDS,
    SAMPLE_RATE,
)


def generate_timecode(
    duration: float,
    freq: float = CARRIER_FREQ,
    sr: int = SAMPLE_RATE,
    amplitude: float = AMPLITUDE,
    apply_riaa: bool = False,
    loop: bool = False,
    verbose: bool = True,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Generate stereo quadrature timecode with position encoding.

    Args:
        duration: Signal duration in seconds
        freq: Carrier frequency in Hz
        sr: Sample rate in Hz
        amplitude: Peak amplitude (linear)
        apply_riaa: Apply RIAA pre-emphasis for PHONO input
        loop: Phase-continuous for locked-groove cutting
        verbose: Print progress to stdout

    Returns:
        (left, right, metadata) — full-length arrays with lead-in/out
    """
    lead_in = int(LEAD_IN_SECONDS * sr)
    lead_out = int(LEAD_OUT_SECONDS * sr)
    samples_per_cycle = sr / freq

    if loop:
        total_cycles = int(duration * freq)
        signal_samples = int(round(total_cycles * samples_per_cycle))
        actual_duration = signal_samples / sr
        if verbose:
            print(f"  Loop mode:   snapped {duration}s -> {actual_duration:.6f}s ({total_cycles} exact cycles)")
        duration = actual_duration
    else:
        signal_samples = int(duration * sr)
        total_cycles = int(signal_samples / samples_per_cycle)

    total_samples = lead_in + signal_samples + lead_out

    if verbose:
        print(f"MIXI-CUT v{__version__} timecode generator")
        print(f"  Duration:    {duration}s ({duration/60:.1f} min) + {LEAD_IN_SECONDS}s lead-in + {LEAD_OUT_SECONDS}s lead-out")
        print(f"  Frequency:   {freq} Hz (stereo quadrature)")
        print(f"  Samples:     {total_samples:,} ({signal_samples:,} signal)")
        print(f"  Cycles:      {total_cycles:,}")
        print(f"  Amplitude:   {amplitude:.2f} ({20*np.log10(amplitude):+.1f} dBFS)")

    # Generate carrier
    t = np.arange(signal_samples, dtype=np.float64) / sr
    phase = 2 * np.pi * freq * t
    sig_left = np.sin(phase) * amplitude
    sig_right = np.cos(phase) * amplitude

    # Position encoding
    encoded_count = apply_position_encoding(sig_left, sig_right, freq, sr)
    if verbose:
        print(f"  Encoded:     {encoded_count:,} missing cycles (raised-cosine transitions)")

    # RIAA pre-emphasis
    if apply_riaa:
        if verbose:
            print("  RIAA:        Applying IIR pre-emphasis...")
        sig_left = apply_riaa_iir(sig_left, sr)
        sig_right = apply_riaa_iir(sig_right, sr)
        peak = max(np.max(np.abs(sig_left)), np.max(np.abs(sig_right)))
        if peak > 0.98:
            scale = 0.98 / peak
            sig_left *= scale
            sig_right *= scale
            if verbose:
                print(f"               Re-normalized by {scale:.4f} to prevent clipping")

    # DC offset removal
    dc_l = np.mean(sig_left)
    dc_r = np.mean(sig_right)
    if abs(dc_l) > 1e-6 or abs(dc_r) > 1e-6:
        sig_left -= dc_l
        sig_right -= dc_r
        if verbose:
            print(f"  DC removal:  L={dc_l:+.6f}, R={dc_r:+.6f}")

    # Assemble with lead-in/lead-out
    left = np.zeros(total_samples, dtype=np.float64)
    right = np.zeros(total_samples, dtype=np.float64)
    left[lead_in:lead_in + signal_samples] = sig_left
    right[lead_in:lead_in + signal_samples] = sig_right

    metadata = {
        "duration": duration,
        "freq": freq,
        "sr": sr,
        "amplitude": amplitude,
        "total_samples": total_samples,
        "signal_samples": signal_samples,
        "total_cycles": total_cycles,
        "encoded_cycles": encoded_count,
        "loop": loop,
        "riaa": apply_riaa,
    }

    if loop:
        end_phase = 2 * np.pi * freq * (signal_samples / sr)
        phase_error_deg = abs((end_phase % (2 * np.pi)) - 0) * 180 / np.pi
        if phase_error_deg > 180:
            phase_error_deg = 360 - phase_error_deg
        metadata["phase_error_deg"] = phase_error_deg
        if verbose:
            print(f"  Loop:        phase-continuous (error: {phase_error_deg:.4f} deg)")
    else:
        apply_fades(left, right, lead_in, signal_samples)
        if verbose:
            print(f"  Fades:       {FADE_SAMPLES / sr * 1000:.0f}ms quadratic")

    if verbose:
        print(f"  Lead-in:     {LEAD_IN_SECONDS}s silence")
        print(f"  Lead-out:    {LEAD_OUT_SECONDS}s silence")

    return left, right, metadata


def write_wav(
    left: np.ndarray,
    right: np.ndarray,
    output: str,
    sr: int = SAMPLE_RATE,
    verbose: bool = True,
) -> str:
    """Write stereo timecode to WAV file.

    Args:
        left: Left channel array
        right: Right channel array
        output: Output file path
        sr: Sample rate in Hz
        verbose: Print summary to stdout

    Returns:
        Output file path
    """
    stereo = np.column_stack([left, right])

    if verbose:
        print(f"\nWriting {output}...")

    sf.write(output, stereo, sr, subtype='PCM_16')

    if verbose:
        file_size_mb = len(left) * 2 * 2 / (1024 * 1024)
        print(f"  File size: ~{file_size_mb:.1f} MB")
        print(f"  Format:    {sr} Hz / 16-bit / stereo")
        print("\nCut at 33 1/3 RPM, 200 lines/inch, +3 dB level.")

    return output
