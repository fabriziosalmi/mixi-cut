"""WAV file verification for MIXI-CUT timecode files.

Checks carrier frequency, quadrature phase, position encoding,
channel balance, DC offset, and overall EDM readiness.
"""

import numpy as np
import soundfile as sf

from mixi_cut.protocol import CARRIER_FREQ


def verify_timecode(filepath: str, strict: bool = False, verbose: bool = True) -> tuple[bool, dict]:
    """Verify a MIXI-CUT timecode WAV file.

    Args:
        filepath: Path to WAV file
        strict: If True, any warning is a failure
        verbose: Print results to stdout

    Returns:
        (passed, results_dict)
    """
    def log(msg):
        if verbose:
            print(msg)

    log(f"Verifying: {filepath}\n")

    data, sr = sf.read(filepath)

    results = {"file": filepath, "sr": sr, "checks": {}}

    if data.ndim != 2 or data.shape[1] != 2:
        log("  FAIL: Not a stereo file")
        results["checks"]["stereo"] = False
        return False, results

    left = data[:, 0]
    right = data[:, 1]
    duration = len(left) / sr

    log(f"  Sample rate:   {sr} Hz")
    log(f"  Duration:      {duration:.1f}s ({duration/60:.1f} min)")
    log(f"  Samples:       {len(left):,}")

    # Find signal region
    rms_window = sr // 10
    n_windows = len(left) // rms_window
    window_rms = np.array([
        np.sqrt(np.mean(left[i * rms_window:(i + 1) * rms_window] ** 2))
        for i in range(n_windows)
    ])
    threshold = np.max(window_rms) * 0.1
    active = np.where(window_rms > threshold)[0]

    if len(active) == 0:
        log("  FAIL: No signal detected")
        results["checks"]["signal"] = False
        return False, results

    sig_start = active[0] * rms_window
    sig_end = (active[-1] + 1) * rms_window
    sig_left = left[sig_start:sig_end]
    sig_right = right[sig_start:sig_end]
    sig_duration = len(sig_left) / sr

    lead_in_sec = sig_start / sr
    lead_out_sec = (len(left) - sig_end) / sr

    log(f"  Signal region: {sig_start/sr:.1f}s to {sig_end/sr:.1f}s ({sig_duration:.1f}s)")
    log(f"  Lead-in:       {lead_in_sec:.1f}s")
    log(f"  Lead-out:      {lead_out_sec:.1f}s")

    # Signal levels
    peak_l = np.max(np.abs(sig_left))
    peak_r = np.max(np.abs(sig_right))
    rms_l = np.sqrt(np.mean(sig_left ** 2))
    rms_r = np.sqrt(np.mean(sig_right ** 2))
    dc_l = np.mean(sig_left)
    dc_r = np.mean(sig_right)

    log(f"\n  Peak L/R:      {peak_l:.4f} / {peak_r:.4f}")
    log(f"  RMS L/R:       {rms_l:.4f} / {rms_r:.4f}")
    log(f"  DC offset L/R: {dc_l:+.6f} / {dc_r:+.6f}")

    checks = {}

    # DC offset
    dc_ok = abs(dc_l) < 0.001 and abs(dc_r) < 0.001
    checks["dc_offset"] = dc_ok
    log(f"  {'PASS' if dc_ok else 'WARN'}: DC offset {'negligible' if dc_ok else 'detected'}")

    # Quadrature check
    mid = len(sig_left) // 2
    seg = min(sr, len(sig_left) // 4)
    corr = np.corrcoef(sig_left[mid:mid + seg], sig_right[mid:mid + seg])[0, 1]
    log(f"\n  L/R correlation: {corr:.6f}")
    quad_ok = abs(corr) < 0.05
    checks["quadrature"] = quad_ok
    log(f"  {'PASS' if quad_ok else 'WARN'}: Quadrature phase {'OK' if quad_ok else 'off'}")

    # Frequency
    segment = sig_left[mid:mid + sr]
    fft_mag = np.abs(np.fft.rfft(segment))
    freqs = np.fft.rfftfreq(len(segment), 1.0 / sr)
    peak_freq = freqs[np.argmax(fft_mag[1:]) + 1]
    log(f"  Dominant freq: {peak_freq:.0f} Hz")
    freq_ok = abs(peak_freq - CARRIER_FREQ) < 100
    checks["frequency"] = freq_ok
    log(f"  {'PASS' if freq_ok else 'WARN'}: Carrier frequency {'OK' if freq_ok else 'off'}")

    # Position encoding
    envelope = np.abs(sig_left[:sr * 2])
    window = max(1, int(sr / CARRIER_FREQ))
    kernel = np.ones(window) / window
    smooth_env = np.convolve(envelope, kernel, mode='valid')
    mean_env = np.mean(smooth_env)
    dips = np.sum(smooth_env < mean_env * 0.6)
    pos_ok = dips > 0
    checks["position_encoding"] = pos_ok
    log(f"\n  Missing cycle dips: {dips} in first 2s")
    log(f"  {'PASS' if pos_ok else 'WARN'}: Position encoding {'detected' if pos_ok else 'not detected'}")

    # Channel balance
    balance = rms_r / (rms_l + rms_r) if (rms_l + rms_r) > 0 else 0.5
    balance_ok = 0.45 < balance < 0.55
    checks["balance"] = balance_ok
    log(f"\n  Channel balance: {balance:.3f} (0.5 = perfect)")
    log(f"  {'PASS' if balance_ok else 'WARN'}: Channels {'balanced' if balance_ok else 'imbalanced'}")

    # Lead-in
    leadin_ok = lead_in_sec >= 1.0
    checks["lead_in"] = leadin_ok
    log(f"  {'PASS' if leadin_ok else 'WARN'}: Lead-in {'present' if leadin_ok else 'missing'}")

    # Summary
    results["checks"] = checks
    results["peak_freq"] = float(peak_freq)
    results["correlation"] = float(corr)
    results["balance"] = float(balance)
    results["dc_l"] = float(dc_l)
    results["dc_r"] = float(dc_r)
    results["lead_in_sec"] = float(lead_in_sec)
    results["duration"] = float(duration)

    score = sum(1 for v in checks.values() if v)
    total = len(checks)

    log("\n  --- EDM Readiness ---")
    for name, ok in checks.items():
        log(f"  [{'OK' if ok else '!!'}] {name}")
    log(f"\n  Score: {score}/{total}")

    if strict:
        passed = score == total
    else:
        # Pass if critical checks are OK (quadrature, frequency, position)
        passed = checks.get("quadrature", False) and checks.get("frequency", False) and checks.get("position_encoding", False)

    log(f"  {'READY TO CUT' if passed else 'REVIEW warnings before cutting'}")

    return passed, results
