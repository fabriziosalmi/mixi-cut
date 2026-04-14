"""Tests for the reference decoder (Bandpass, PLL, MassSpring, Decoder)."""

import numpy as np

from mixi_cut.decoder import PLL, Bandpass, Decoder, MassSpring
from mixi_cut.protocol import CARRIER_FREQ, SAMPLE_RATE

TAU = 2 * np.pi


def make_signal(duration=1.0, freq=CARRIER_FREQ, speed=1.0, amp=0.85, sr=SAMPLE_RATE):
    """Helper: generate a clean quadrature signal."""
    n = int(duration * sr)
    t = np.arange(n) / sr
    phase = TAU * freq * speed * t
    return np.sin(phase) * amp, np.cos(phase) * amp


class TestBandpass:
    """Biquad bandpass filter."""

    def test_passes_carrier(self):
        """Signal at carrier frequency passes through."""
        bp = Bandpass()
        left, _ = make_signal(0.1)
        out = np.array([bp.tick(x) for x in left])
        # After transient, output should be significant
        rms_out = np.sqrt(np.mean(out[len(out) // 2:] ** 2))
        assert rms_out > 0.1

    def test_rejects_dc(self):
        """DC signal is rejected."""
        bp = Bandpass()
        dc = np.ones(SAMPLE_RATE) * 0.85
        out = np.array([bp.tick(x) for x in dc])
        rms_out = np.sqrt(np.mean(out[len(out) // 2:] ** 2))
        assert rms_out < 0.01

    def test_rejects_low_frequency(self):
        """50 Hz hum is rejected."""
        bp = Bandpass()
        t = np.arange(SAMPLE_RATE) / SAMPLE_RATE
        hum = np.sin(TAU * 50 * t) * 0.85
        out = np.array([bp.tick(x) for x in hum])
        rms_out = np.sqrt(np.mean(out[len(out) // 2:] ** 2))
        assert rms_out < 0.01

    def test_reset(self):
        """Reset clears internal state."""
        bp = Bandpass()
        left, _ = make_signal(0.01)
        for x in left:
            bp.tick(x)
        bp.reset()
        assert bp.z1 == 0.0
        assert bp.z2 == 0.0


class TestPLL:
    """Phase-Locked Loop demodulator."""

    def test_locks_to_carrier(self):
        """PLL locks to a clean carrier signal."""
        pll = PLL()
        left, right = make_signal(0.5)
        locks = []
        for i in range(len(left)):
            _, lock = pll.tick(left[i], right[i])
            locks.append(lock)
        # Should be locked by the end
        assert locks[-1] > 0.8

    def test_speed_tracking(self):
        """PLL reports speed ≈ 1.0 for normal play."""
        pll = PLL()
        left, right = make_signal(0.5)
        speeds = []
        for i in range(len(left)):
            speed, _ = pll.tick(left[i], right[i])
            speeds.append(speed)
        # Last quarter should be stable near 1.0
        avg_speed = np.mean(speeds[-len(speeds) // 4:])
        assert abs(avg_speed - 1.0) < 0.02

    def test_silence_coasts(self):
        """PLL coasts (decays lock) during silence."""
        pll = PLL()
        # First: lock on signal
        left, right = make_signal(0.2)
        for i in range(len(left)):
            pll.tick(left[i], right[i])
        lock_before = pll.lock

        # Then: feed silence
        for _ in range(SAMPLE_RATE // 4):
            pll.tick(0.0, 0.0)
        assert pll.lock < lock_before

    def test_reset(self):
        pll = PLL()
        left, right = make_signal(0.1)
        for i in range(len(left)):
            pll.tick(left[i], right[i])
        pll.reset()
        assert pll.lock == 0.0
        assert pll.integral == 0.0


class TestMassSpring:
    """Mass-spring-damper platter physics."""

    def test_smooth_tracking(self):
        """Smoothly tracks constant speed."""
        ms = MassSpring()
        for _ in range(500):
            ms.tick(1.0)
        assert abs(ms.speed - 1.0) < 0.05

    def test_scratch_detection(self):
        """Large speed jump triggers scratch mode."""
        ms = MassSpring()
        for _ in range(100):
            ms.tick(1.0)
        ms.tick(3.0)  # big jump
        # Should snap to the new speed
        assert abs(ms.speed - 3.0) < 0.1

    def test_stop_response(self):
        """Near-zero speed with adaptive traction."""
        ms = MassSpring()
        # Get to normal speed
        for _ in range(200):
            ms.tick(1.0)
        # Sudden stop
        for _ in range(50):
            ms.tick(0.0)
        assert abs(ms.speed) < 0.1

    def test_dead_zone(self):
        """Low speeds snap to exactly 0.0."""
        ms = MassSpring()
        ms.tick(0.01)
        ms.tick(0.01)
        assert ms.speed == 0.0

    def test_brake_detection(self):
        """Gradual deceleration triggers faster tracking (v0.2.0 fix)."""
        ms = MassSpring()
        # Normal play
        for _ in range(200):
            ms.tick(1.0)
        # Gradual brake: 1.0 → 0.0 over 100 steps
        speeds = np.linspace(1.0, 0.0, 100)
        for v in speeds:
            ms.tick(v)
        # Should be near zero after brake
        # The old algorithm took 488ms; the new one should be much faster
        assert abs(ms.speed) < 0.15

    def test_reset(self):
        ms = MassSpring()
        ms.tick(1.0)
        ms.reset()
        assert ms.speed == 0.0
        assert ms._decel_count == 0


class TestDecoder:
    """Full decoder pipeline."""

    def test_decode_clean_signal(self):
        """Decoder locks and reports correct speed on clean signal."""
        dec = Decoder()
        left, right = make_signal(2.0)
        block = 128
        speeds = []
        locks = []
        for i in range(0, len(left), block):
            j = min(i + block, len(left))
            s, lk, _ = dec.process(left[i:j], right[i:j])
            speeds.append(s)
            locks.append(lk)

        # Last quarter should be stable
        n = len(speeds)
        avg_speed = np.mean(speeds[3 * n // 4:])
        avg_lock = np.mean(locks[3 * n // 4:])
        assert abs(avg_speed - 1.0) < 0.05
        assert avg_lock > 0.7

    def test_decode_with_noise(self):
        """Decoder works with moderate noise."""
        dec = Decoder()
        left, right = make_signal(2.0)
        np.random.seed(123)
        noise_level = 0.1
        left += np.random.randn(len(left)) * noise_level
        right += np.random.randn(len(right)) * noise_level

        block = 128
        locks = []
        for i in range(0, len(left), block):
            j = min(i + block, len(left))
            _, lk, _ = dec.process(left[i:j], right[i:j])
            locks.append(lk)

        avg_lock = np.mean(locks[-len(locks) // 4:])
        assert avg_lock > 0.5

    def test_position_increases(self):
        """Position estimate increases over time."""
        dec = Decoder()
        left, right = make_signal(1.0)
        block = 128
        positions = []
        for i in range(0, len(left), block):
            j = min(i + block, len(left))
            _, _, pos = dec.process(left[i:j], right[i:j])
            positions.append(pos)

        # Position should be monotonically increasing (roughly)
        assert positions[-1] > positions[0]

    def test_reset_clears_state(self):
        dec = Decoder()
        left, right = make_signal(0.5)
        block = 128
        for i in range(0, len(left), block):
            j = min(i + block, len(left))
            dec.process(left[i:j], right[i:j])

        dec.reset()
        assert dec.pos == 0.0
        assert dec.pll.lock == 0.0

    def test_silence_returns_zero_speed(self):
        """Decoder reports ~0 speed on silence."""
        dec = Decoder()
        # First feed some signal to stabilize
        left, right = make_signal(0.5)
        block = 128
        for i in range(0, len(left), block):
            j = min(i + block, len(left))
            dec.process(left[i:j], right[i:j])

        # Now feed silence
        silence = np.zeros(SAMPLE_RATE // 2)
        speeds = []
        for i in range(0, len(silence), block):
            j = min(i + block, len(silence))
            s, _, _ = dec.process(silence[i:j], silence[i:j])
            speeds.append(s)

        # Speed should decay toward 0
        assert abs(speeds[-1]) < 0.1


class TestBrakeSettle:
    """v0.3.1: Vinyl brake settle time — target <100ms."""

    def test_brake_settle_under_100ms(self):
        """Brake from 1.0x to 0.0 settles within 100ms."""
        ms = MassSpring()
        # Ramp to stable 1.0x
        for _ in range(500):
            ms.tick(1.0)
        assert abs(ms.speed - 1.0) < 0.05

        # Simulate vinyl brake: gradual decel then zero
        decel_steps = 50  # ~1.1ms per step at 44100 Hz
        for i in range(decel_steps):
            v = 1.0 * (1.0 - i / decel_steps)
            ms.tick(v)

        # Now feed constant 0.0 — should snap quickly
        settle_samples = int(0.100 * SAMPLE_RATE)  # 100ms budget
        for _ in range(settle_samples):
            ms.tick(0.0)

        # Must be under 0.01 within 100ms
        assert abs(ms.speed) < 0.01, f"Brake settle too slow: speed={ms.speed}"

    def test_brake_regime_transitions(self):
        """Verify regime state machine transitions."""
        ms = MassSpring()
        # Start: NORMAL
        assert ms._brake_regime == MassSpring.NORMAL

        # Ramp to stable
        for _ in range(200):
            ms.tick(1.0)

        # Gradual decel → should transition to DECEL
        for i in range(20):
            ms.tick(1.0 - i * 0.05)

        assert ms._brake_regime == MassSpring.DECEL

    def test_snap_to_zero(self):
        """SNAP regime immediately sets speed to input."""
        ms = MassSpring()
        for _ in range(200):
            ms.tick(1.0)
        # Fast decel
        for i in range(50):
            ms.tick(max(0.0, 1.0 - i * 0.03))
        # Feed zeros
        for _ in range(200):
            ms.tick(0.0)
        # Should be exactly 0.0 (dead zone snap)
        assert ms.speed == 0.0

    def test_brake_release_restarts_cleanly(self):
        """After brake, restarting restores normal traction."""
        ms = MassSpring()
        # Play → brake → stop
        for _ in range(200):
            ms.tick(1.0)
        for i in range(50):
            ms.tick(max(0.0, 1.0 - i * 0.03))
        for _ in range(200):
            ms.tick(0.0)
        assert ms.speed == 0.0

        # Restart playback
        for _ in range(500):
            ms.tick(1.0)
        assert abs(ms.speed - 1.0) < 0.05


class TestSpeedRange3x:
    """v0.3.1: Speed tracking at 3.0x — dual-PLL."""

    def test_speed_tracking_2x(self):
        """Decoder tracks 2.0x speed accurately."""
        dec = Decoder()
        left, right = make_signal(3.0, speed=2.0)
        block = 128
        speeds = []
        for i in range(0, len(left), block):
            j = min(i + block, len(left))
            s, _, _ = dec.process(left[i:j], right[i:j])
            speeds.append(s)

        # Last quarter should track 2.0x
        avg = np.mean(speeds[3 * len(speeds) // 4:])
        assert abs(avg - 2.0) < 0.15, f"2.0x tracking: {avg}"

    def test_speed_tracking_3x(self):
        """Decoder tracks 3.0x speed using wide PLL."""
        dec = Decoder()
        left, right = make_signal(3.0, speed=3.0)
        block = 128
        speeds = []
        locks = []
        for i in range(0, len(left), block):
            j = min(i + block, len(left))
            s, lk, _ = dec.process(left[i:j], right[i:j])
            speeds.append(s)
            locks.append(lk)

        # Last quarter should track 3.0x
        avg = np.mean(speeds[3 * len(speeds) // 4:])
        assert abs(avg - 3.0) < 0.3, f"3.0x tracking: {avg}"

    def test_speed_negative_2x(self):
        """Decoder tracks -2.0x (reverse play)."""
        dec = Decoder()
        left, right = make_signal(3.0, speed=-2.0)
        block = 128
        speeds = []
        for i in range(0, len(left), block):
            j = min(i + block, len(left))
            s, _, _ = dec.process(left[i:j], right[i:j])
            speeds.append(s)

        avg = np.mean(speeds[3 * len(speeds) // 4:])
        assert abs(avg - (-2.0)) < 0.3, f"-2.0x tracking: {avg}"

    def test_dual_pll_starts_wide(self):
        """Decoder starts with wide PLL for acquisition."""
        dec = Decoder()
        assert dec._using_wide is True

    def test_dual_pll_handoff_to_narrow(self):
        """After lock, decoder transitions to narrow PLL."""
        dec = Decoder()
        left, right = make_signal(2.0, speed=1.0)
        block = 128
        for i in range(0, len(left), block):
            j = min(i + block, len(left))
            dec.process(left[i:j], right[i:j])

        # After 2 seconds at 1.0x, should be using narrow
        assert dec._using_wide is False, "Should have handed off to narrow"

    def test_dual_pll_fallback_at_high_speed(self):
        """Narrow PLL falls back to wide at high speed."""
        dec = Decoder()
        # First lock at 1.0x
        left1, right1 = make_signal(1.5, speed=1.0)
        block = 128
        for i in range(0, len(left1), block):
            j = min(i + block, len(left1))
            dec.process(left1[i:j], right1[i:j])
        assert dec._using_wide is False

        # Now jump to 3.0x
        left3, right3 = make_signal(2.0, speed=3.0)
        for i in range(0, len(left3), block):
            j = min(i + block, len(left3))
            dec.process(left3[i:j], right3[i:j])

        # Should have fallen back to wide
        assert dec._using_wide is True, "Should fallback to wide at 3.0x"

