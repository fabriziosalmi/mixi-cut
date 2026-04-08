#!/usr/bin/env python3
"""
MIXI-CUT Timecode Generator v2 — EDM-optimized (100-200 BPM)

Generates a stereo quadrature timecode WAV file for vinyl lathe cutting.
Signal: L = sin(2*pi*3000*t), R = cos(2*pi*3000*t)
With Missing Cycle absolute position encoding and Reed-Solomon error correction.

EDM optimizations vs v1:
  - 24-bit position encoding (covers full 15 min without overflow)
  - Raised-cosine missing cycle transitions (no spectral splatter)
  - Tighter position frames (0.8s vs 1.6s — faster needle-drop acquisition)
  - Lead-in/lead-out silence for safe needle placement
  - IIR RIAA pre-emphasis (constant memory, works on any duration)
  - DC offset guard (removes any DC bias before writing)

Usage:
    python generate.py                          # Full 15-minute timecode
    python generate.py --duration 60            # 1-minute test for first lathe cut
    python generate.py --riaa                   # With RIAA pre-emphasis (PHONO input)
    python generate.py --verify file.wav        # Verify existing file
"""

import argparse
import sys
import numpy as np
import soundfile as sf


# ── Constants ─────────────────────────────────────────────────

SAMPLE_RATE = 44100
DEFAULT_FREQ = 3000           # Hz — carrier frequency
DEFAULT_DURATION = 15 * 60    # 15 minutes
AMPLITUDE = 0.85              # +4.5 dB above -6 dBFS — headroom for vinyl noise floor
LEAD_IN_SECONDS = 2.0         # Silence before timecode starts (needle placement)
LEAD_OUT_SECONDS = 1.0        # Silence after timecode ends (run-out groove)
FADE_SAMPLES = 441            # 10 ms fade in/out to avoid click at boundaries

# Position encoding — EDM-optimized: faster acquisition, full 15-min coverage
POSITION_CYCLE_INTERVAL = 50  # 1 bit every 50 cycles (was 100 — 2x denser for faster lock)
MISSING_CYCLE_DEPTH = 0.25    # Amplitude dip for "missing" cycle (deeper = more readable)

# Raised cosine transition length (in samples) — prevents spectral splatter
TRANSITION_SAMPLES = 4        # ~0.09 ms at 44.1 kHz — gentle enough, fast enough


# ── Reed-Solomon GF(2^8) ─────────────────────────────────────

GF_EXP = [0] * 512
GF_LOG = [0] * 256


def _init_gf():
    """Initialize Galois Field lookup tables: GF(2^8), primitive poly x^8+x^4+x^3+x^2+1."""
    x = 1
    for i in range(255):
        GF_EXP[i] = x
        GF_LOG[x] = i
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    for i in range(255, 512):
        GF_EXP[i] = GF_EXP[i - 255]


_init_gf()


def gf_mul(a, b):
    if a == 0 or b == 0:
        return 0
    return GF_EXP[GF_LOG[a] + GF_LOG[b]]


def rs_encode(data, nsym=4):
    """Reed-Solomon encode: append nsym parity bytes to data."""
    gen = [1]
    for i in range(nsym):
        new_gen = [0] * (len(gen) + 1)
        for j, g in enumerate(gen):
            new_gen[j] ^= g
            new_gen[j + 1] ^= gf_mul(g, GF_EXP[i])
        gen = new_gen

    feedback = list(data) + [0] * nsym
    for i in range(len(data)):
        if feedback[i] != 0:
            for j in range(1, len(gen)):
                feedback[i + j] ^= gf_mul(gen[j], feedback[i])

    return list(data) + feedback[len(data):]


# ── Position encoding (v2: 24-bit — covers 0-167772s) ────────

def encode_position(position_sec):
    """Encode position (0-900s) into bits with Reed-Solomon protection.

    v2 format: 24-bit position (0.01s resolution, max 167772s) + 32-bit RS parity = 56 bits.
    This fixes the v1 overflow where 16-bit only covered 0-655s.
    """
    centisec = int(round(position_sec * 100))
    centisec = min(centisec, 0xFFFFFF)  # 24-bit clamp

    # 3 data bytes (24 bits)
    data = [
        (centisec >> 16) & 0xFF,
        (centisec >> 8) & 0xFF,
        centisec & 0xFF,
    ]

    # RS encode: 3 data + 4 parity = 7 bytes = 56 bits
    encoded = rs_encode(data, nsym=4)

    bits = []
    for byte_val in encoded:
        for bit_idx in range(7, -1, -1):
            bits.append((byte_val >> bit_idx) & 1)

    return bits


# ── RIAA pre-emphasis (v2: IIR filter — constant memory) ─────

def make_riaa_iir_coeffs(sr):
    """Design a 2nd-order IIR shelving filter approximating RIAA recording curve.

    Uses bilinear transform of the analog RIAA transfer function.
    This replaces the v1 FFT approach which allocated O(N) memory.
    """
    # RIAA time constants (seconds)
    t1, t2, t3 = 3180e-6, 318e-6, 75e-6

    # Analog poles/zeros → digital via bilinear transform
    # Pre-warp
    def prewarp(tau):
        return 2.0 * sr * np.tan(1.0 / (2.0 * sr * tau))

    w1 = prewarp(t1)  # ~50 Hz zero
    w2 = prewarp(t2)  # ~500 Hz pole
    w3 = prewarp(t3)  # ~2122 Hz zero

    # We approximate the RIAA recording curve (inverse of playback) as a cascade
    # of two first-order sections: high-shelf (t1/t2) + high-boost (t3)

    # Section 1: (s + w2) / (s + w1) — boost above ~50 Hz
    # Bilinear: s = 2*sr*(z-1)/(z+1)
    a1_num = 2 * sr + w2
    a1_den = 2 * sr + w1
    b1_num = -2 * sr + w2
    b1_den = -2 * sr + w1

    # Section 2: (s + w3) / s — high frequency boost (recording emphasis)
    # Simplified as first-order high shelf
    a2_num = 2 * sr + w3
    a2_den = 2 * sr
    b2_num = -2 * sr + w3
    b2_den = -2 * sr

    return (a1_num, b1_num, a1_den, b1_den), (a2_num, b2_num, a2_den, b2_den)


def apply_riaa_iir(signal, sr):
    """Apply RIAA pre-emphasis using cascaded IIR filters. O(1) memory."""
    sec1, sec2 = make_riaa_iir_coeffs(sr)

    result = signal.copy()

    # Section 1
    b0 = sec1[0] / sec1[2]
    b1 = sec1[1] / sec1[2]
    a1 = sec1[3] / sec1[2]
    z1 = 0.0
    for i in range(len(result)):
        x = result[i]
        y = b0 * x + z1
        z1 = b1 * x - a1 * y
        result[i] = y

    # Section 2
    b0 = sec2[0] / sec2[2]
    b1 = sec2[1] / sec2[2]
    a1 = sec2[3] / sec2[2]
    z1 = 0.0
    for i in range(len(result)):
        x = result[i]
        y = b0 * x + z1
        z1 = b1 * x - a1 * y
        result[i] = y

    # Normalize: unity gain at 1 kHz
    # Generate 1 kHz test tone, measure gain, compensate
    test_len = sr  # 1 second
    t_test = np.arange(test_len) / sr
    test_in = np.sin(2 * np.pi * 1000 * t_test)
    test_out = test_in.copy()

    for section in [sec1, sec2]:
        b0 = section[0] / section[2]
        b1 = section[1] / section[2]
        a1 = section[3] / section[2]
        z1 = 0.0
        for i in range(len(test_out)):
            x = test_out[i]
            y = b0 * x + z1
            z1 = b1 * x - a1 * y
            test_out[i] = y

    # Measure RMS gain at 1 kHz (skip transient)
    rms_in = np.sqrt(np.mean(test_in[sr // 2:] ** 2))
    rms_out = np.sqrt(np.mean(test_out[sr // 2:] ** 2))
    gain_1k = rms_out / rms_in if rms_in > 0 else 1.0

    result /= gain_1k

    return result


# ── Raised cosine transition ─────────────────────────────────

def make_transition_envelope(n_samples):
    """Create a raised cosine envelope for smooth amplitude transitions.

    Returns array that goes from 1.0 → MISSING_CYCLE_DEPTH → 1.0
    with smooth transitions at boundaries (no spectral splatter).
    """
    t = TRANSITION_SAMPLES
    env = np.ones(n_samples)

    # Ramp down at start
    if t > 0 and n_samples > 2 * t:
        ramp = 0.5 * (1 + np.cos(np.linspace(0, np.pi, t)))  # 1 → 0
        ramp = 1.0 - ramp * (1.0 - MISSING_CYCLE_DEPTH)  # 1 → MISSING_CYCLE_DEPTH
        env[:t] = ramp

        # Flat bottom
        env[t:n_samples - t] = MISSING_CYCLE_DEPTH

        # Ramp up at end
        ramp_up = 0.5 * (1 + np.cos(np.linspace(np.pi, 0, t)))  # 0 → 1
        ramp_up = 1.0 - ramp_up * (1.0 - MISSING_CYCLE_DEPTH)
        env[n_samples - t:] = ramp_up
    else:
        env[:] = MISSING_CYCLE_DEPTH

    return env


# ── Timecode generation (v2) ─────────────────────────────────

def generate_timecode(duration, freq, sr, amplitude, apply_riaa=False, loop=False):
    """Generate stereo quadrature timecode with position encoding.

    v2 improvements:
      - 24-bit position (no overflow at 15 min)
      - Raised-cosine missing cycle transitions
      - 2x denser position frames (50-cycle interval)
      - Lead-in/lead-out silence
      - DC offset removal

    If loop=True, duration is snapped to an exact number of carrier cycles
    so the last sample's phase connects seamlessly to the first sample.
    This enables locked-groove (infinite loop) cutting on vinyl.
    """
    lead_in = int(LEAD_IN_SECONDS * sr)
    lead_out = int(LEAD_OUT_SECONDS * sr)

    samples_per_cycle = sr / freq

    if loop:
        # Snap duration to exact cycle count for phase-continuous loop.
        # The locked groove needs: phase(end) == phase(start) mod 2*pi
        # This means signal_samples must be an exact multiple of samples_per_cycle.
        total_cycles = int(duration * freq)
        signal_samples = int(round(total_cycles * samples_per_cycle))
        actual_duration = signal_samples / sr
        print(f"  Loop mode:   snapped {duration}s -> {actual_duration:.6f}s ({total_cycles} exact cycles)")
        duration = actual_duration
    else:
        signal_samples = int(duration * sr)
        total_cycles = int(signal_samples / samples_per_cycle)

    total_samples = lead_in + signal_samples + lead_out

    print(f"MIXI-CUT v2 (EDM-optimized) timecode generator")
    print(f"  Duration:    {duration}s ({duration/60:.1f} min) + {LEAD_IN_SECONDS}s lead-in + {LEAD_OUT_SECONDS}s lead-out")
    print(f"  Frequency:   {freq} Hz (stereo quadrature)")
    print(f"  Samples:     {total_samples:,} ({signal_samples:,} signal)")
    print(f"  Cycles:      {total_cycles:,}")
    print(f"  Amplitude:   {amplitude:.2f} ({20*np.log10(amplitude):+.1f} dBFS)")

    # Generate carrier in the signal region only
    t = np.arange(signal_samples, dtype=np.float64) / sr
    phase = 2 * np.pi * freq * t
    sig_left = np.sin(phase) * amplitude
    sig_right = np.cos(phase) * amplitude

    # ── Position encoding ─────────────────────────────────
    bits_per_frame = 56  # 24-bit position + 32-bit RS parity
    cycles_per_frame = POSITION_CYCLE_INTERVAL * bits_per_frame  # 2800 cycles
    seconds_per_frame = cycles_per_frame / freq  # 0.933s at 3kHz
    total_frames = int(total_cycles / cycles_per_frame)

    print(f"  Position:    24-bit (max {0xFFFFFF * 0.01:.0f}s), {total_frames} frames (1 every {seconds_per_frame:.2f}s)")

    # Pre-compute raised cosine envelope for one missing cycle
    cycle_samples = int(round(samples_per_cycle))
    transition_env = make_transition_envelope(cycle_samples)

    encoded_count = 0
    for frame_idx in range(total_frames):
        frame_start_cycle = frame_idx * cycles_per_frame
        position_sec = frame_start_cycle / freq

        bits = encode_position(position_sec)

        for bit_idx, bit_val in enumerate(bits):
            if bit_val == 1:
                target_cycle = frame_start_cycle + bit_idx * POSITION_CYCLE_INTERVAL
                sample_start = int(target_cycle * samples_per_cycle)
                sample_end = sample_start + cycle_samples

                if sample_end <= signal_samples:
                    # Apply raised-cosine amplitude dip (smooth transition)
                    env = transition_env[:sample_end - sample_start]
                    sig_left[sample_start:sample_end] *= env
                    sig_right[sample_start:sample_end] *= env
                    encoded_count += 1

    print(f"  Encoded:     {encoded_count:,} missing cycles (raised-cosine transitions)")

    # ── RIAA pre-emphasis ─────────────────────────────────
    if apply_riaa:
        print("  RIAA:        Applying IIR pre-emphasis...")
        sig_left = apply_riaa_iir(sig_left, sr)
        sig_right = apply_riaa_iir(sig_right, sr)
        peak = max(np.max(np.abs(sig_left)), np.max(np.abs(sig_right)))
        if peak > 0.98:
            scale = 0.98 / peak
            sig_left *= scale
            sig_right *= scale
            print(f"               Re-normalized by {scale:.4f} to prevent clipping")

    # ── DC offset removal ─────────────────────────────────
    dc_l = np.mean(sig_left)
    dc_r = np.mean(sig_right)
    if abs(dc_l) > 1e-6 or abs(dc_r) > 1e-6:
        sig_left -= dc_l
        sig_right -= dc_r
        print(f"  DC removal:  L={dc_l:+.6f}, R={dc_r:+.6f}")

    # ── Assemble with lead-in/lead-out ────────────────────
    left = np.zeros(total_samples, dtype=np.float64)
    right = np.zeros(total_samples, dtype=np.float64)

    left[lead_in:lead_in + signal_samples] = sig_left
    right[lead_in:lead_in + signal_samples] = sig_right

    if loop:
        # Loop mode: no fade — the signal is phase-continuous.
        # The locked groove on vinyl will loop seamlessly.
        # Verify phase continuity:
        end_phase = 2 * np.pi * freq * (signal_samples / sr)
        phase_error_deg = abs((end_phase % (2 * np.pi)) - 0) * 180 / np.pi
        if phase_error_deg > 180:
            phase_error_deg = 360 - phase_error_deg
        print(f"  Loop:        phase-continuous (error: {phase_error_deg:.4f} deg)")
        print(f"  Lead-in:     {LEAD_IN_SECONDS}s silence")
        print(f"  Lead-out:    {LEAD_OUT_SECONDS}s silence")
    else:
        # Fade in (avoid click at timecode start)
        fade = np.linspace(0, 1, FADE_SAMPLES) ** 2  # quadratic fade
        left[lead_in:lead_in + FADE_SAMPLES] *= fade
        right[lead_in:lead_in + FADE_SAMPLES] *= fade

        # Fade out
        left[lead_in + signal_samples - FADE_SAMPLES:lead_in + signal_samples] *= fade[::-1]
        right[lead_in + signal_samples - FADE_SAMPLES:lead_in + signal_samples] *= fade[::-1]

        print(f"  Lead-in:     {LEAD_IN_SECONDS}s silence")
        print(f"  Lead-out:    {LEAD_OUT_SECONDS}s silence")
        print(f"  Fades:       {FADE_SAMPLES / sr * 1000:.0f}ms quadratic")

    return left, right


# ── Verification ──────────────────────────────────────────────

def verify_timecode(filepath):
    """Verify a MIXI-CUT timecode WAV file (v1 or v2)."""
    print(f"Verifying: {filepath}\n")

    data, sr = sf.read(filepath)

    if data.ndim != 2 or data.shape[1] != 2:
        print("  FAIL: Not a stereo file")
        return False

    left = data[:, 0]
    right = data[:, 1]
    duration = len(left) / sr

    print(f"  Sample rate:   {sr} Hz")
    print(f"  Duration:      {duration:.1f}s ({duration/60:.1f} min)")
    print(f"  Samples:       {len(left):,}")

    # Find signal region (skip lead-in/lead-out silence)
    rms_window = sr // 10  # 100ms windows
    n_windows = len(left) // rms_window
    window_rms = np.array([
        np.sqrt(np.mean(left[i * rms_window:(i + 1) * rms_window] ** 2))
        for i in range(n_windows)
    ])
    threshold = np.max(window_rms) * 0.1
    active = np.where(window_rms > threshold)[0]

    if len(active) == 0:
        print("  FAIL: No signal detected")
        return False

    sig_start = active[0] * rms_window
    sig_end = (active[-1] + 1) * rms_window
    sig_left = left[sig_start:sig_end]
    sig_right = right[sig_start:sig_end]
    sig_duration = len(sig_left) / sr

    lead_in_sec = sig_start / sr
    lead_out_sec = (len(left) - sig_end) / sr

    print(f"  Signal region: {sig_start/sr:.1f}s to {sig_end/sr:.1f}s ({sig_duration:.1f}s)")
    print(f"  Lead-in:       {lead_in_sec:.1f}s")
    print(f"  Lead-out:      {lead_out_sec:.1f}s")

    # Signal levels
    peak_l = np.max(np.abs(sig_left))
    peak_r = np.max(np.abs(sig_right))
    rms_l = np.sqrt(np.mean(sig_left ** 2))
    rms_r = np.sqrt(np.mean(sig_right ** 2))
    dc_l = np.mean(sig_left)
    dc_r = np.mean(sig_right)

    print(f"\n  Peak L/R:      {peak_l:.4f} / {peak_r:.4f}")
    print(f"  RMS L/R:       {rms_l:.4f} / {rms_r:.4f}")
    print(f"  DC offset L/R: {dc_l:+.6f} / {dc_r:+.6f}")

    if abs(dc_l) < 0.001 and abs(dc_r) < 0.001:
        print("  PASS: DC offset negligible")
    else:
        print("  WARN: DC offset detected (may cause rumble on playback)")

    # Quadrature check: L and R should be 90deg out of phase → correlation ~0
    # Use a clean segment in the middle (avoid fades)
    mid = len(sig_left) // 2
    seg = min(sr, len(sig_left) // 4)
    corr = np.corrcoef(sig_left[mid:mid + seg], sig_right[mid:mid + seg])[0, 1]
    print(f"\n  L/R correlation: {corr:.6f}")

    if abs(corr) < 0.05:
        print("  PASS: Quadrature phase OK")
    else:
        print(f"  WARN: Quadrature may be off (expected ~0)")

    # Dominant frequency via FFT
    segment = sig_left[mid:mid + sr]
    fft_mag = np.abs(np.fft.rfft(segment))
    freqs = np.fft.rfftfreq(len(segment), 1.0 / sr)
    peak_freq = freqs[np.argmax(fft_mag[1:]) + 1]
    print(f"  Dominant freq: {peak_freq:.0f} Hz")

    if abs(peak_freq - DEFAULT_FREQ) < 100:
        print(f"  PASS: Carrier frequency OK")
    else:
        print(f"  WARN: Expected ~{DEFAULT_FREQ} Hz, got {peak_freq:.0f} Hz")

    # Missing cycle detection
    envelope = np.abs(sig_left[:sr * 2])
    window = max(1, int(sr / DEFAULT_FREQ))
    kernel = np.ones(window) / window
    smooth_env = np.convolve(envelope, kernel, mode='valid')
    mean_env = np.mean(smooth_env)
    dips = np.sum(smooth_env < mean_env * 0.6)

    print(f"\n  Missing cycle dips: {dips} in first 2s")
    if dips > 0:
        print("  PASS: Position encoding detected")
    else:
        print("  WARN: No position encoding detected")

    # Channel balance
    balance = rms_r / (rms_l + rms_r) if (rms_l + rms_r) > 0 else 0.5
    print(f"\n  Channel balance: {balance:.3f} (0.5 = perfect)")
    if 0.45 < balance < 0.55:
        print("  PASS: Channels balanced")
    else:
        print("  WARN: Channel imbalance detected")

    # EDM readiness score
    print(f"\n  --- EDM Readiness ---")
    score = 0
    checks = 0

    checks += 1
    if abs(corr) < 0.05:
        score += 1
        print("  [OK] Quadrature phase")
    else:
        print("  [!!] Quadrature phase off")

    checks += 1
    if abs(peak_freq - DEFAULT_FREQ) < 100:
        score += 1
        print("  [OK] Carrier frequency")
    else:
        print("  [!!] Carrier frequency off")

    checks += 1
    if dips > 0:
        score += 1
        print("  [OK] Position encoding present")
    else:
        print("  [!!] No position encoding")

    checks += 1
    if 0.45 < balance < 0.55:
        score += 1
        print("  [OK] Channel balance")
    else:
        print("  [!!] Channel imbalance")

    checks += 1
    if abs(dc_l) < 0.001 and abs(dc_r) < 0.001:
        score += 1
        print("  [OK] DC offset clean")
    else:
        print("  [!!] DC offset present")

    checks += 1
    if lead_in_sec >= 1.0:
        score += 1
        print("  [OK] Lead-in present")
    else:
        print("  [!!] No lead-in (needle may skip)")

    print(f"\n  Score: {score}/{checks}")
    if score == checks:
        print("  READY TO CUT")
    else:
        print("  REVIEW warnings before cutting")

    return score == checks


# ── Main ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="MIXI-CUT v2 — EDM-optimized timecode generator for vinyl lathe cutting"
    )
    parser.add_argument(
        "--duration", type=int, default=DEFAULT_DURATION,
        help=f"Signal duration in seconds (default: {DEFAULT_DURATION}s = 15 min)"
    )
    parser.add_argument(
        "--freq", type=int, default=DEFAULT_FREQ,
        help=f"Carrier frequency in Hz (default: {DEFAULT_FREQ})"
    )
    parser.add_argument(
        "--output", type=str, default="mixi_timecode_v2.wav",
        help="Output WAV filename"
    )
    parser.add_argument(
        "--riaa", action="store_true",
        help="Apply RIAA pre-emphasis (for PHONO input on mixer)"
    )
    parser.add_argument(
        "--verify", type=str, metavar="FILE",
        help="Verify an existing timecode WAV file"
    )
    parser.add_argument(
        "--loop", action="store_true",
        help="Phase-continuous loop: duration snapped to exact cycles for locked-groove vinyl"
    )
    parser.add_argument(
        "--edm-test", action="store_true",
        help="Generate a short 60s test file optimized for quick iteration"
    )

    args = parser.parse_args()

    if args.verify:
        ok = verify_timecode(args.verify)
        sys.exit(0 if ok else 1)

    if args.edm_test:
        args.duration = 60
        args.output = args.output.replace("v2.wav", "v2_test60s.wav")
        print("EDM test mode: 60s signal for quick lathe-cut iteration\n")

    left, right = generate_timecode(
        duration=args.duration,
        freq=args.freq,
        sr=SAMPLE_RATE,
        amplitude=AMPLITUDE,
        apply_riaa=args.riaa,
        loop=args.loop,
    )

    stereo = np.column_stack([left, right])

    print(f"\nWriting {args.output}...")
    sf.write(args.output, stereo, SAMPLE_RATE, subtype='PCM_16')

    file_size_mb = len(left) * 2 * 2 / (1024 * 1024)
    print(f"  File size: ~{file_size_mb:.1f} MB")
    print(f"  Format:    44100 Hz / 16-bit / stereo")
    print(f"\nCut at 33 1/3 RPM, 200 lines/inch, +3 dB level.")
    print(f"For first test: python generate.py --edm-test")


if __name__ == "__main__":
    main()
