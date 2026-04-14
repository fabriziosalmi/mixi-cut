//! MIXI-CUT Decoder — Rust implementation
//!
//! Three-stage audio pipeline: Bandpass → PLL → Mass-Spring-Damper
//! Designed for real-time vinyl timecode demodulation.
//!
//! # Usage
//! ```
//! use mixi_decoder::{Decoder, DecoderConfig};
//!
//! let mut dec = Decoder::new(DecoderConfig::default());
//! let left = vec![0.0f32; 128];
//! let right = vec![0.0f32; 128];
//! let result = dec.process(&left, &right);
//! println!("Speed: {:.2}x, Lock: {:.3}", result.speed, result.lock);
//! ```

use std::f32::consts::PI;

const TAU: f32 = 2.0 * PI;

// ── Configuration ────────────────────────────────────────────

/// Decoder configuration parameters
#[derive(Clone, Debug)]
pub struct DecoderConfig {
    pub carrier_freq: f32,
    pub sample_rate: f32,
    pub pll_bw_pct: f32,
    pub pll_q: f32,
    pub inertia: f32,
}

impl Default for DecoderConfig {
    fn default() -> Self {
        Self {
            carrier_freq: 3000.0,
            sample_rate: 44100.0,
            pll_bw_pct: 0.08,
            pll_q: 2.5,
            inertia: 0.95,
        }
    }
}

/// Decoder output for one processed block
#[derive(Clone, Debug, Default)]
pub struct DecoderResult {
    pub speed: f32,
    pub lock: f32,
    pub position: f64,
}

// ── Bandpass Filter ──────────────────────────────────────────

/// Biquad bandpass filter centered at carrier frequency
#[derive(Clone, Debug)]
pub struct Bandpass {
    b0: f32,
    b2: f32,
    a1: f32,
    a2: f32,
    z1: f32,
    z2: f32,
}

impl Bandpass {
    pub fn new(freq: f32, sr: f32, q: f32) -> Self {
        let w0 = TAU * freq.min(sr * 0.45) / sr;
        let alpha = w0.sin() / (2.0 * q.max(0.1));
        let a0 = 1.0 + alpha;
        Self {
            b0: alpha / a0,
            b2: -alpha / a0,
            a1: -2.0 * w0.cos() / a0,
            a2: (1.0 - alpha) / a0,
            z1: 0.0,
            z2: 0.0,
        }
    }

    #[inline]
    pub fn tick(&mut self, x: f32) -> f32 {
        let y = self.b0 * x + self.z1;
        self.z1 = -self.a1 * y + self.z2;
        self.z2 = self.b2 * x - self.a2 * y;
        y
    }

    pub fn reset(&mut self) {
        self.z1 = 0.0;
        self.z2 = 0.0;
    }
}

// ── Phase-Locked Loop ────────────────────────────────────────

/// PLL demodulator with DJ resilience features
#[derive(Clone, Debug)]
pub struct Pll {
    center: f32,
    sr: f32,
    phase: f32,
    freq: f32,
    integral: f32,
    lock: f32,
    kp: f32,
    ki: f32,
}

impl Pll {
    pub fn new(freq: f32, sr: f32, bw_pct: f32) -> Self {
        let bw = freq * bw_pct;
        let omega = TAU * bw / sr;
        Self {
            center: freq,
            sr,
            phase: 0.0,
            freq,
            integral: 0.0,
            lock: 0.0,
            kp: 2.0 * omega,
            ki: omega * omega,
        }
    }

    #[inline]
    pub fn tick(&mut self, l: f32, r: f32) -> (f32, f32) {
        let amp = (l * l + r * r).sqrt();

        // Amplitude gate
        if amp < 0.005 {
            let a = 1.0 / (self.sr * 0.05);
            self.lock *= 1.0 - a;
            self.phase += TAU * self.freq / self.sr;
            if self.phase >= TAU {
                self.phase -= TAU;
            }
            return (self.freq / self.center, self.lock);
        }

        let mut err = l.atan2(r) - self.phase;
        if err > PI {
            err -= TAU;
        } else if err < -PI {
            err += TAU;
        }

        // Integral drain when unlocked
        let drain = if self.lock < 0.3 { 0.98 } else { 1.0 };
        self.integral = (self.integral * drain + err * self.ki)
            .clamp(-self.center * 0.5, self.center * 0.5);
        self.freq = (self.center + err * self.kp * self.sr + self.integral)
            .clamp(-self.center * 2.0, self.center * 3.0);

        self.phase += TAU * self.freq / self.sr;
        if self.phase >= TAU {
            self.phase -= TAU;
        } else if self.phase < 0.0 {
            self.phase += TAU;
        }

        let a = 1.0 / (self.sr * 0.05);
        self.lock = self.lock * (1.0 - a) + err.cos() * a;
        (self.freq / self.center, self.lock.clamp(0.0, 1.0))
    }

    pub fn reset(&mut self) {
        self.phase = 0.0;
        self.freq = self.center;
        self.integral = 0.0;
        self.lock = 0.0;
    }
}

// ── Mass-Spring-Damper ───────────────────────────────────────

/// Platter physics simulator with brake detection
#[derive(Clone, Debug)]
#[allow(dead_code)]
pub struct MassSpring {
    speed: f32,
    prev: f32,
    inertia: f32,
    traction: f32,
    scratching: bool,
    release: i32,
    decel_count: i32,
    prev_input: f32,
}

impl MassSpring {
    pub fn new(inertia: f32) -> Self {
        Self {
            speed: 0.0,
            prev: 0.0,
            inertia,
            traction: 1.0 - inertia,
            scratching: false,
            release: 0,
            decel_count: 0,
            prev_input: 0.0,
        }
    }

    #[inline]
    pub fn tick(&mut self, v: f32) -> f32 {
        self.prev = self.speed;
        let d = (v - self.speed).abs();

        if d > 0.3 {
            // Scratch: instant snap
            self.speed = v;
            self.scratching = true;
            self.release = 0;
        } else if self.scratching {
            self.speed = self.speed * 0.3 + v * 0.7;
            if d < 0.05 {
                self.release += 1;
                if self.release > 20 {
                    self.scratching = false;
                }
            } else {
                self.release = 0;
            }
        } else {
            // Brake detection
            if v < self.prev_input - 0.001 && self.speed > 0.05 {
                self.decel_count += 1;
            } else {
                self.decel_count = (self.decel_count - 2).max(0);
            }

            let t = if self.decel_count > 3 {
                let bf = ((self.decel_count - 3) as f32 / 5.0).min(1.0);
                0.5 + bf * 0.4 // 0.5 → 0.9
            } else if v.abs() < 0.1 && d > 0.05 {
                (self.traction * 10.0).min(0.5)
            } else {
                self.traction
            };

            self.speed = self.speed * (1.0 - t) + v * t;
        }

        self.prev_input = v;

        // Dead zone
        if self.speed.abs() < 0.02 && v.abs() < 0.02 {
            self.speed = 0.0;
        }

        self.speed
    }

    pub fn reset(&mut self) {
        self.speed = 0.0;
        self.prev = 0.0;
        self.scratching = false;
        self.release = 0;
        self.decel_count = 0;
        self.prev_input = 0.0;
    }

    pub fn get_speed(&self) -> f32 {
        self.speed
    }
}

// ── Full Decoder ─────────────────────────────────────────────

/// Complete MIXI-CUT decoder: Bandpass → PLL → Mass-Spring
pub struct Decoder {
    freq: f32,
    sr: f32,
    bp_l: Bandpass,
    bp_r: Bandpass,
    pll: Pll,
    ms: MassSpring,
    pos: f64,
}

impl Decoder {
    pub fn new(cfg: DecoderConfig) -> Self {
        Self {
            freq: cfg.carrier_freq,
            sr: cfg.sample_rate,
            bp_l: Bandpass::new(cfg.carrier_freq, cfg.sample_rate, cfg.pll_q),
            bp_r: Bandpass::new(cfg.carrier_freq, cfg.sample_rate, cfg.pll_q),
            pll: Pll::new(cfg.carrier_freq, cfg.sample_rate, cfg.pll_bw_pct),
            ms: MassSpring::new(cfg.inertia),
            pos: 0.0,
        }
    }

    /// Process a block of stereo audio samples
    pub fn process(&mut self, left: &[f32], right: &[f32]) -> DecoderResult {
        let n = left.len().min(right.len());
        let mut ss = 0.0_f32;
        let mut sl = 0.0_f32;
        let mut se = 0.0_f32;

        for i in 0..n {
            let fl = self.bp_l.tick(left[i]);
            let fr = self.bp_r.tick(right[i]);
            let (spd, lk) = self.pll.tick(fl, fr);
            self.pos += self.pll.freq as f64 / self.sr as f64;
            ss += spd;
            sl += lk;
            se += fl * fl + fr * fr;
        }

        let n_f = n as f32;
        let avg_s = ss / n_f;
        let avg_l = sl / n_f;
        let rms = (se / n_f).sqrt();

        let speed_in = if rms > 0.01 { avg_s } else { 0.0 };

        DecoderResult {
            speed: self.ms.tick(speed_in),
            lock: avg_l,
            position: self.pos / self.freq as f64,
        }
    }

    pub fn reset(&mut self) {
        self.bp_l.reset();
        self.bp_r.reset();
        self.pll.reset();
        self.ms.reset();
        self.pos = 0.0;
    }

    pub fn get_speed(&self) -> f32 {
        self.ms.get_speed()
    }
}

// ── Wasm bindings ────────────────────────────────────────────

#[cfg(feature = "wasm")]
use wasm_bindgen::prelude::*;

#[cfg(feature = "wasm")]
#[wasm_bindgen]
pub struct WasmDecoder {
    inner: Decoder,
}

#[cfg(feature = "wasm")]
#[wasm_bindgen]
impl WasmDecoder {
    #[wasm_bindgen(constructor)]
    pub fn new(freq: f32, sr: f32) -> Self {
        Self {
            inner: Decoder::new(DecoderConfig {
                carrier_freq: freq,
                sample_rate: sr,
                ..Default::default()
            }),
        }
    }

    pub fn process(&mut self, left: &[f32], right: &[f32]) -> Vec<f32> {
        let r = self.inner.process(left, right);
        vec![r.speed, r.lock, r.position as f32]
    }

    pub fn reset(&mut self) {
        self.inner.reset();
    }
}

// ── Tests ────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn gen_signal(dur: f32, speed: f32) -> (Vec<f32>, Vec<f32>) {
        let n = (dur * 44100.0) as usize;
        let mut left = vec![0.0f32; n];
        let mut right = vec![0.0f32; n];
        for i in 0..n {
            let t = i as f32 / 44100.0;
            let phase = TAU * 3000.0 * speed * t;
            left[i] = phase.sin() * 0.85;
            right[i] = phase.cos() * 0.85;
        }
        (left, right)
    }

    #[test]
    fn test_bandpass_passes_carrier() {
        let mut bp = Bandpass::new(3000.0, 44100.0, 2.5);
        let (left, _) = gen_signal(0.1, 1.0);
        let n = left.len();
        let mut rms_sum = 0.0_f32;
        for (i, &x) in left.iter().enumerate() {
            let y = bp.tick(x);
            if i > n / 2 {
                rms_sum += y * y;
            }
        }
        let rms = (rms_sum / (n / 2) as f32).sqrt();
        assert!(rms > 0.1, "Carrier should pass, got rms={rms}");
    }

    #[test]
    fn test_pll_locks() {
        let mut pll = Pll::new(3000.0, 44100.0, 0.08);
        let (left, right) = gen_signal(0.5, 1.0);
        let mut last_lock = 0.0;
        for i in 0..left.len() {
            let (_, lk) = pll.tick(left[i], right[i]);
            last_lock = lk;
        }
        assert!(last_lock > 0.8, "PLL should lock, got {last_lock}");
    }

    #[test]
    fn test_pll_speed() {
        let mut pll = Pll::new(3000.0, 44100.0, 0.08);
        let (left, right) = gen_signal(0.5, 1.0);
        let n = left.len();
        let mut sum = 0.0;
        let mut count = 0;
        for i in 0..n {
            let (spd, _) = pll.tick(left[i], right[i]);
            if i > 3 * n / 4 {
                sum += spd;
                count += 1;
            }
        }
        let avg = sum / count as f32;
        assert!((avg - 1.0).abs() < 0.02, "Speed should be ~1.0, got {avg}");
    }

    #[test]
    fn test_mass_spring_tracking() {
        let mut ms = MassSpring::new(0.95);
        for _ in 0..500 {
            ms.tick(1.0);
        }
        assert!(
            (ms.speed - 1.0).abs() < 0.05,
            "Should track, got {}",
            ms.speed
        );
    }

    #[test]
    fn test_mass_spring_dead_zone() {
        let mut ms = MassSpring::new(0.95);
        ms.tick(0.01);
        ms.tick(0.01);
        assert_eq!(ms.speed, 0.0, "Should snap to zero");
    }

    #[test]
    fn test_decoder_clean_signal() {
        let mut dec = Decoder::new(DecoderConfig::default());
        let (left, right) = gen_signal(2.0, 1.0);
        let block = 128;
        let total = left.len() / block;
        let mut speed_sum = 0.0;
        let mut lock_sum = 0.0;
        let mut count = 0;

        for i in 0..total {
            let start = i * block;
            let end = start + block;
            let r = dec.process(&left[start..end], &right[start..end]);
            if i > total * 3 / 4 {
                speed_sum += r.speed;
                lock_sum += r.lock;
                count += 1;
            }
        }

        let avg_speed = speed_sum / count as f32;
        let avg_lock = lock_sum / count as f32;
        assert!(
            (avg_speed - 1.0).abs() < 0.05,
            "Speed ~1.0, got {avg_speed}"
        );
        assert!(avg_lock > 0.7, "Lock > 0.7, got {avg_lock}");
    }

    #[test]
    fn test_position_increases() {
        let mut dec = Decoder::new(DecoderConfig::default());
        let (left, right) = gen_signal(1.0, 1.0);
        let block = 128;

        let mut first_pos = None;
        let mut last_pos = 0.0;
        for i in (0..left.len()).step_by(block) {
            let end = (i + block).min(left.len());
            let r = dec.process(&left[i..end], &right[i..end]);
            if first_pos.is_none() {
                first_pos = Some(r.position);
            }
            last_pos = r.position;
        }
        assert!(last_pos > first_pos.unwrap());
    }

    #[test]
    fn test_reset() {
        let mut dec = Decoder::new(DecoderConfig::default());
        let (left, right) = gen_signal(0.5, 1.0);
        dec.process(&left, &right);
        dec.reset();
        assert_eq!(dec.pos, 0.0);
    }
}
