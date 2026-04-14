from __future__ import annotations

"""Reference decoder for the MIXI-CUT protocol.

Python port of the Rust decoder from mixi-core.
Three-stage pipeline: Bandpass → PLL → Mass-Spring-Damper.

Includes v0.2 DJ resilience features:
  - PLL integral drain (prevents bias after needle drops)
  - Adaptive stop traction (3ms stop response)
  - Vinyl brake detection
  - Low-speed dead zone
  - Signal-aware pipeline
"""

import numpy as np

from mixi_cut.protocol import (
    CARRIER_FREQ,
    MASS_SPRING_BRAKE_EXP_RATE,
    MASS_SPRING_BRAKE_RELEASE_SAMPLES,
    MASS_SPRING_BRAKE_SNAP_THRESHOLD,
    MASS_SPRING_DEAD_ZONE,
    MASS_SPRING_INERTIA,
    MASS_SPRING_SCRATCH_THRESHOLD,
    MASS_SPRING_STOP_TRACTION_MULT,
    PLL_AMPLITUDE_GATE,
    PLL_BANDWIDTH_PCT,
    PLL_FALLBACK_LOCK_THRESHOLD,
    PLL_FALLBACK_SAMPLES,
    PLL_HANDOFF_LOCK_THRESHOLD,
    PLL_HANDOFF_SAMPLES,
    PLL_INTEGRAL_DRAIN,
    PLL_LOCK_TAU,
    PLL_Q,
    PLL_WIDE_BANDWIDTH_PCT,
    PLL_WIDE_SPEED_THRESHOLD,
    SAMPLE_RATE,
)

TAU = 2 * np.pi
DEFAULT_BLOCK = 128


class Bandpass:
    """Biquad bandpass filter centered at carrier frequency.

    Rejects rumble, hum (50/60 Hz), and hiss above the carrier band.
    """

    def __init__(self, freq: float = CARRIER_FREQ, sr: float = SAMPLE_RATE, q: float = PLL_Q):
        w0 = TAU * min(freq, sr * 0.45) / sr
        alpha = np.sin(w0) / (2.0 * max(q, 0.1))
        a0 = 1.0 + alpha
        self.b0 = alpha / a0
        self.b2 = -alpha / a0
        self.a1 = -2.0 * np.cos(w0) / a0
        self.a2 = (1.0 - alpha) / a0
        self.z1 = 0.0
        self.z2 = 0.0

    def tick(self, x: float) -> float:
        y = self.b0 * x + self.z1
        self.z1 = -self.a1 * y + self.z2
        self.z2 = self.b2 * x - self.a2 * y
        return y

    def reset(self):
        self.z1 = 0.0
        self.z2 = 0.0


class PLL:
    """Phase-Locked Loop demodulator with DJ resilience features.

    Tracks the instantaneous frequency of the quadrature carrier
    and provides speed + lock quality outputs.

    v0.2 features:
      - Integral drain: 2%/sample decay when unlocked, prevents
        bias accumulation during needle drops
      - Amplitude gate: PLL coasts on silence (< -46 dBFS)
    """

    def __init__(
        self,
        freq: float = CARRIER_FREQ,
        sr: float = SAMPLE_RATE,
        bw_pct: float = PLL_BANDWIDTH_PCT,
    ):
        self.center = freq
        self.sr = sr
        self.phase = 0.0
        self.freq = freq
        self.integral = 0.0
        self.lock = 0.0

        bw = freq * bw_pct
        omega = TAU * bw / sr
        self.kp = 2.0 * omega
        self.ki = omega * omega

    def tick(self, left_sample: float, r: float) -> tuple[float, float]:
        """Process one sample pair.

        Args:
            left_sample: Left channel sample (sin component)
            r: Right channel sample (cos component)

        Returns:
            (speed_ratio, lock_quality) — speed as fraction of center freq
        """
        amp = np.sqrt(left_sample * left_sample + r * r)

        if amp < PLL_AMPLITUDE_GATE:
            # Coast: no signal, decay lock
            a = 1.0 / (self.sr * PLL_LOCK_TAU)
            self.lock *= (1.0 - a)
            self.phase += TAU * self.freq / self.sr
            if self.phase >= TAU:
                self.phase -= TAU
            return self.freq / self.center, self.lock

        err = np.arctan2(left_sample, r) - self.phase
        if err > np.pi:
            err -= TAU
        elif err < -np.pi:
            err += TAU

        # Integral drain when unlocked (v3)
        drain = PLL_INTEGRAL_DRAIN if self.lock < 0.3 else 1.0
        self.integral = np.clip(
            self.integral * drain + err * self.ki,
            -self.center * 0.5,
            self.center * 0.5,
        )
        self.freq = np.clip(
            self.center + err * self.kp * self.sr + self.integral,
            -self.center * 2,
            self.center * 3,
        )

        self.phase += TAU * self.freq / self.sr
        if self.phase >= TAU:
            self.phase -= TAU
        elif self.phase < 0:
            self.phase += TAU

        a = 1.0 / (self.sr * PLL_LOCK_TAU)
        self.lock = self.lock * (1 - a) + np.cos(err) * a
        return self.freq / self.center, np.clip(self.lock, 0, 1)

    def reset(self):
        self.phase = 0.0
        self.freq = self.center
        self.integral = 0.0
        self.lock = 0.0


class MassSpring:
    """Mass-spring-damper filter simulating turntable platter physics.

    Smooths PLL speed output to match the physical inertia of a
    Technics SL-1200 platter while allowing instant response to
    DJ scratch gestures.

    v0.3.1 features:
      - 3-regime adaptive brake: DECEL → SNAP → RELEASE
      - Exponential traction curve during deceleration
      - Near-zero snap bypass (instant stop)
      - Gradual traction restore on restart (prevents oscillation)
      - Low-speed dead zone: snaps to 0.0 below 2% speed
    """

    # Brake regimes
    NORMAL = 0
    DECEL = 1
    SNAP = 2
    RELEASE = 3

    def __init__(self, inertia: float = MASS_SPRING_INERTIA):
        self.speed = 0.0
        self.prev = 0.0
        self.inertia = inertia
        self.traction = 1.0 - inertia
        self.scratching = False
        self.release = 0
        # Brake state
        self._decel_count = 0
        self._prev_input = 0.0
        self._brake_regime = self.NORMAL
        self._release_counter = 0

    def tick(self, v: float) -> float:
        """Process one speed measurement.

        Args:
            v: Instantaneous speed from PLL (1.0 = normal play)

        Returns:
            Smoothed speed output
        """
        self.prev = self.speed
        d = abs(v - self.speed)

        if d > MASS_SPRING_SCRATCH_THRESHOLD:
            # Scratch detected: instant snap
            self.speed = v
            self.scratching = True
            self.release = 0
            self._brake_regime = self.NORMAL
        elif self.scratching:
            self.speed = self.speed * 0.3 + v * 0.7
            if d < 0.05:
                self.release += 1
                if self.release > 20:
                    self.scratching = False
            else:
                self.release = 0
        else:
            # ── v0.3.1: 3-regime adaptive brake ──

            # Detect sustained deceleration
            is_decelerating = (v < self._prev_input - 0.001 and self.speed > 0.05)
            if is_decelerating:
                self._decel_count += 1
            else:
                self._decel_count = max(0, self._decel_count - 2)

            # State machine transitions
            if self._brake_regime == self.NORMAL:
                if self._decel_count > 3:
                    self._brake_regime = self.DECEL
            elif self._brake_regime == self.DECEL:
                if (abs(self.speed) < MASS_SPRING_BRAKE_SNAP_THRESHOLD
                        and abs(v) < MASS_SPRING_BRAKE_SNAP_THRESHOLD):
                    self._brake_regime = self.SNAP
                elif self._decel_count == 0 and v > self._prev_input + 0.01:
                    self._brake_regime = self.RELEASE
                    self._release_counter = 0
            elif self._brake_regime == self.SNAP:
                if v > 0.05:
                    self._brake_regime = self.RELEASE
                    self._release_counter = 0
            elif self._brake_regime == self.RELEASE:
                self._release_counter += 1
                if self._release_counter > MASS_SPRING_BRAKE_RELEASE_SAMPLES:
                    self._brake_regime = self.NORMAL
                    self._decel_count = 0

            # Apply traction based on regime
            if self._brake_regime == self.DECEL:
                # Exponential traction: aggressive convergence
                exp_factor = 1.0 - np.exp(-self._decel_count / MASS_SPRING_BRAKE_EXP_RATE)
                t = 0.7 + 0.25 * exp_factor  # 0.7 → 0.95
            elif self._brake_regime == self.SNAP:
                # Bypass spring: instant snap to PLL value
                self.speed = v
                self._prev_input = v
                if abs(self.speed) < MASS_SPRING_DEAD_ZONE:
                    self.speed = 0.0
                return self.speed
            elif self._brake_regime == self.RELEASE:
                # Gradual restore: blend from aggressive to normal
                blend = self._release_counter / MASS_SPRING_BRAKE_RELEASE_SAMPLES
                t = (1.0 - blend) * 0.5 + blend * self.traction
            elif abs(v) < 0.1 and d > 0.05:
                # Near-stop: high traction for fast stop response
                t = min(self.traction * MASS_SPRING_STOP_TRACTION_MULT, 0.5)
            else:
                t = self.traction

            self.speed = self.speed * (1.0 - t) + v * t

        self._prev_input = v

        # Low-speed dead zone
        if abs(self.speed) < MASS_SPRING_DEAD_ZONE and abs(v) < MASS_SPRING_DEAD_ZONE:
            self.speed = 0.0

        return self.speed

    def reset(self):
        self.speed = 0.0
        self.prev = 0.0
        self.scratching = False
        self.release = 0
        self._decel_count = 0
        self._prev_input = 0.0
        self._brake_regime = self.NORMAL
        self._release_counter = 0


class Decoder:
    """Complete MIXI-CUT decoder: Bandpass → Dual-PLL → Mass-Spring.

    Processes stereo audio blocks and outputs:
      - speed: playback speed ratio (1.0 = normal)
      - lock: PLL lock quality (0.0-1.0)
      - position: estimated position in seconds

    v0.3.1: Dual-PLL with adaptive bandwidth handoff:
      - Wide PLL (20%) for acquisition and high-speed (>1.8x)
      - Narrow PLL (8%) for precision tracking at normal speed
      - Automatic handoff based on lock quality and speed

    Example:
        >>> dec = Decoder()
        >>> for i in range(0, len(left), 128):
        ...     speed, lock, pos = dec.process(left[i:i+128], right[i:i+128])
        ...     print(f"Speed: {speed:.2f}x, Lock: {lock:.3f}, Pos: {pos:.2f}s")
    """

    def __init__(
        self,
        freq: float = CARRIER_FREQ,
        sr: float = SAMPLE_RATE,
        q: float = PLL_Q,
        bw: float = PLL_BANDWIDTH_PCT,
    ):
        self.freq = freq
        self.sr = sr
        self.bp_l = Bandpass(freq, sr, q)
        self.bp_r = Bandpass(freq, sr, q)
        # Dual PLLs
        self.pll_narrow = PLL(freq, sr, bw)
        self.pll_wide = PLL(freq, sr, PLL_WIDE_BANDWIDTH_PCT)
        self._using_wide = True  # start with wide for acquisition
        self._handoff_counter = 0
        self._fallback_counter = 0
        self.ms = MassSpring()
        self.pos = 0.0

    @property
    def pll(self) -> PLL:
        """Active PLL (for backward compatibility)."""
        return self.pll_wide if self._using_wide else self.pll_narrow

    def process(self, left: np.ndarray, right: np.ndarray) -> tuple[float, float, float]:
        """Process a block of stereo audio.

        Args:
            left: Left channel samples
            right: Right channel samples

        Returns:
            (speed, lock, position_seconds)
        """
        n = len(left)
        ss = sl = se = 0.0
        active_pll = self.pll

        for i in range(n):
            fl = self.bp_l.tick(left[i])
            fr = self.bp_r.tick(right[i])
            spd, lk = active_pll.tick(fl, fr)
            # Keep shadow PLL in sync
            if self._using_wide:
                self.pll_narrow.tick(fl, fr)
            else:
                self.pll_wide.tick(fl, fr)
            self.pos += active_pll.freq / self.sr
            ss += spd
            sl += lk
            se += fl * fl + fr * fr

        avg_s = ss / n
        avg_l = sl / n
        rms = np.sqrt(se / n)

        # ── Dual-PLL handoff logic ──
        if self._using_wide:
            # Wide → Narrow: switch when locked and speed is moderate
            if (avg_l > PLL_HANDOFF_LOCK_THRESHOLD
                    and abs(avg_s) < PLL_WIDE_SPEED_THRESHOLD):
                self._handoff_counter += n
                if self._handoff_counter >= PLL_HANDOFF_SAMPLES:
                    self._using_wide = False
                    self._handoff_counter = 0
                    self._fallback_counter = 0
                    # Sync narrow PLL phase from wide
                    self.pll_narrow.phase = self.pll_wide.phase
                    self.pll_narrow.freq = self.pll_wide.freq
            else:
                self._handoff_counter = max(0, self._handoff_counter - n)
        else:
            # Narrow → Wide: fallback if lost lock or high speed
            needs_wide = (
                avg_l < PLL_FALLBACK_LOCK_THRESHOLD
                or abs(avg_s) > PLL_WIDE_SPEED_THRESHOLD
            )
            if needs_wide:
                self._fallback_counter += n
                if self._fallback_counter >= PLL_FALLBACK_SAMPLES:
                    self._using_wide = True
                    self._fallback_counter = 0
                    self._handoff_counter = 0
                    # Sync wide PLL phase from narrow
                    self.pll_wide.phase = self.pll_narrow.phase
                    self.pll_wide.freq = self.pll_narrow.freq
            else:
                self._fallback_counter = max(0, self._fallback_counter - n)

        # Signal-aware: feed 0.0 to mass-spring when no signal
        speed_in = avg_s if rms > 0.01 else 0.0
        return self.ms.tick(speed_in), avg_l, self.pos / self.freq

    def reset(self):
        """Reset all decoder state."""
        self.bp_l.reset()
        self.bp_r.reset()
        self.pll_narrow.reset()
        self.pll_wide.reset()
        self._using_wide = True
        self._handoff_counter = 0
        self._fallback_counter = 0
        self.ms.reset()
        self.pos = 0.0

