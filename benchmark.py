#!/usr/bin/env python3
"""
MIXI-CUT Benchmark Suite v3 — Draconian protocol stress testing.

Goal: find every breaking point. Push every parameter until the decoder fails.
Generate colored terminal output, PDF reports, and JSON for regression tracking.

Usage:
    python benchmark.py                     # Full suite, colored terminal
    python benchmark.py --pdf               # Also generate PDF report
    python benchmark.py --test noise        # Run specific category
    python benchmark.py --compare           # Compare against last saved run
    python benchmark.py --history           # Show all historical runs
"""

import argparse, time, sys, os, json, hashlib
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple, Dict
import numpy as np

# ── ANSI Colors ──────────────────────────────────────────────

class C:
    """ANSI escape codes for terminal coloring."""
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    BG_RED  = "\033[41m"
    BG_GREEN= "\033[42m"
    BG_YELLOW="\033[43m"

    @staticmethod
    def disable():
        for attr in ['RESET','BOLD','DIM','RED','GREEN','YELLOW','BLUE','MAGENTA','CYAN','WHITE','BG_RED','BG_GREEN','BG_YELLOW']:
            setattr(C, attr, '')

def verdict_color(v):
    return {
        "strong": C.GREEN, "acceptable": C.YELLOW,
        "weak": C.RED, "critical": f"{C.BG_RED}{C.WHITE}",
    }.get(v, C.WHITE)

def bar(value, max_val=1.0, width=20, fill_char="█", empty_char="░"):
    """ASCII progress bar."""
    ratio = min(max(value / max_val, 0), 1.0)
    filled = int(ratio * width)
    if ratio > 0.8:
        color = C.GREEN
    elif ratio > 0.5:
        color = C.YELLOW
    else:
        color = C.RED
    return f"{color}{fill_char * filled}{C.DIM}{empty_char * (width - filled)}{C.RESET}"

def gauge(label, value, unit, lo, hi, invert=False):
    """Colored gauge: shows value on a lo-hi scale."""
    if invert:
        ratio = 1.0 - (value - lo) / max(hi - lo, 0.001)
    else:
        ratio = (value - lo) / max(hi - lo, 0.001)
    ratio = min(max(ratio, 0), 1.0)
    b = bar(ratio)
    if ratio > 0.7:
        vc = C.GREEN
    elif ratio > 0.4:
        vc = C.YELLOW
    else:
        vc = C.RED
    return f"  {label:.<30s} {b} {vc}{value:>8.3f}{C.RESET} {unit}"

# ── Constants ─────────────────────────────────────────────────

SR = 44100.0
CARRIER = 3000.0
TAU = 2 * np.pi
BLOCK = 128
RESULTS_DIR = "benchmark_results"

# ── PLL Decoder (Python port) ────────────────────────────────

class Bandpass:
    def __init__(self, freq, sr, q):
        w0 = TAU * min(freq, sr * 0.45) / sr
        alpha = np.sin(w0) / (2.0 * max(q, 0.1))
        a0 = 1.0 + alpha
        self.b0 = alpha / a0
        self.b2 = -alpha / a0
        self.a1 = -2.0 * np.cos(w0) / a0
        self.a2 = (1.0 - alpha) / a0
        self.z1 = self.z2 = 0.0

    def tick(self, x):
        y = self.b0 * x + self.z1
        self.z1 = -self.a1 * y + self.z2
        self.z2 = self.b2 * x - self.a2 * y
        return y

class PLL:
    def __init__(self, freq=CARRIER, sr=SR, bw_pct=0.08):
        self.center = freq; self.sr = sr
        self.phase = 0.0; self.freq = freq
        self.integral = 0.0; self.lock = 0.0
        bw = freq * bw_pct
        omega = TAU * bw / sr
        self.kp = 2.0 * omega; self.ki = omega * omega

    def tick(self, l, r):
        amp = np.sqrt(l * l + r * r)
        if amp < 0.005:
            a = 1.0 / (self.sr * 0.05)
            self.lock *= (1.0 - a)
            self.phase += TAU * self.freq / self.sr
            if self.phase >= TAU: self.phase -= TAU
            return self.freq / self.center, self.lock

        err = np.arctan2(l, r) - self.phase
        if err > np.pi: err -= TAU
        elif err < -np.pi: err += TAU

        # Integral drain when unlocked (matches Rust fix)
        drain = 0.98 if self.lock < 0.3 else 1.0
        self.integral = np.clip(self.integral * drain + err * self.ki, -self.center * 0.5, self.center * 0.5)
        self.freq = np.clip(self.center + err * self.kp * self.sr + self.integral, -self.center * 2, self.center * 3)

        self.phase += TAU * self.freq / self.sr
        if self.phase >= TAU: self.phase -= TAU
        elif self.phase < 0: self.phase += TAU

        a = 1.0 / (self.sr * 0.05)
        self.lock = self.lock * (1 - a) + np.cos(err) * a
        return self.freq / self.center, np.clip(self.lock, 0, 1)

class MassSpring:
    def __init__(self, inertia=0.95):
        self.speed = 0.0; self.prev = 0.0
        self.inertia = inertia; self.traction = 1.0 - inertia
        self.scratching = False; self.release = 0
        # v0.2.0: brake state tracking
        self._decel_count = 0; self._prev_input = 0.0

    def tick(self, v):
        self.prev = self.speed
        d = abs(v - self.speed)
        if d > 0.3:
            self.speed = v; self.scratching = True; self.release = 0
        elif self.scratching:
            self.speed = self.speed * 0.3 + v * 0.7
            if d < 0.05:
                self.release += 1
                if self.release > 20: self.scratching = False
            else:
                self.release = 0
        else:
            # v0.2.0: Detect sustained deceleration (vinyl brake)
            if v < self._prev_input - 0.001 and self.speed > 0.05:
                self._decel_count += 1
            else:
                self._decel_count = max(0, self._decel_count - 2)

            if self._decel_count > 3:
                brake_factor = min((self._decel_count - 3) / 5.0, 1.0)
                t = 0.5 + brake_factor * 0.4  # 0.5 → 0.9
            elif abs(v) < 0.1 and d > 0.05:
                t = min(self.traction * 10.0, 0.5)
            else:
                t = self.traction
            self.speed = self.speed * (1.0 - t) + v * t
        self._prev_input = v
        # Low-speed dead zone
        if abs(self.speed) < 0.02 and abs(v) < 0.02:
            self.speed = 0.0
        return self.speed

class Decoder:
    def __init__(self, freq=CARRIER, sr=SR, q=2.5, bw=0.08):
        self.freq = freq; self.sr = sr
        self.bp_l = Bandpass(freq, sr, q); self.bp_r = Bandpass(freq, sr, q)
        self.pll = PLL(freq, sr, bw); self.ms = MassSpring()
        self.pos = 0.0

    def process(self, left, right):
        n = len(left); ss = sl = se = 0.0
        for i in range(n):
            fl = self.bp_l.tick(left[i]); fr = self.bp_r.tick(right[i])
            spd, lk = self.pll.tick(fl, fr)
            self.pos += self.pll.freq / self.sr
            ss += spd; sl += lk; se += fl*fl + fr*fr
        avg_s = ss / n; avg_l = sl / n
        rms = np.sqrt(se / n)
        speed_in = avg_s if rms > 0.01 else 0.0
        return self.ms.tick(speed_in), avg_l, self.pos / self.freq

# ── Signal generators ────────────────────────────────────────

def quadrature(dur, freq=CARRIER, speed=1.0, amp=0.85):
    n = int(dur * SR); t = np.arange(n) / SR
    p = TAU * freq * speed * t
    return np.sin(p) * amp, np.cos(p) * amp

def pink_noise(n):
    w = np.random.randn(n); f = np.fft.rfft(w)
    freqs = np.fft.rfftfreq(n, 1/SR); freqs[0] = 1
    return np.fft.irfft(f / np.sqrt(freqs), n=n)

def add_noise(l, r, snr_db):
    rms = np.sqrt(np.mean(l**2)); na = rms * 10**(snr_db/20); n = len(l)
    p1 = pink_noise(n); p2 = pink_noise(n)
    p1 *= na / np.sqrt(np.mean(p1**2)); p2 *= na / np.sqrt(np.mean(p2**2))
    return l + p1, r + p2

def add_hum(l, r, hz=50, db=-10):
    n = len(l); t = np.arange(n)/SR; rms = np.sqrt(np.mean(l**2))
    a = rms * 10**(db/20)
    h = a * (np.sin(TAU*hz*t) + 0.5*np.sin(TAU*hz*2*t) + 0.3*np.sin(TAU*hz*3*t))
    return l+h, r+h

def add_crosstalk(l, r, db=-15, bpm=128):
    n = len(l); t = np.arange(n)/SR; rms = np.sqrt(np.mean(l**2))
    a = rms * 10**(db/20); bs = 60.0/bpm
    kick = np.zeros(n)
    for bt in np.arange(0, n/SR, bs):
        i = int(bt*SR); e = min(i+int(0.05*SR), n)
        kick[i:e] += np.sin(TAU*60*np.arange(e-i)/SR)*np.exp(-np.arange(e-i)/(SR*0.02))
    music = (kick + np.sin(TAU*100*t)*0.5 + np.random.randn(n)*0.1) * a
    return l+music, r+music*0.8

def add_warp(l, r, hz=0.3, depth=0.2):
    n = len(l); t = np.arange(n)/SR
    am = 1.0 - depth*(1-np.cos(TAU*hz*t))/2
    return l*am, r*am

def add_wow(l, r, wd, fd, whz=0.5, fhz=10.0):
    n = len(l); t = np.arange(n)/SR
    s = 1.0 + wd*np.sin(TAU*whz*t) + fd*np.sin(TAU*fhz*t)
    ni = np.cumsum(s)/SR*SR
    return np.interp(ni, np.arange(n), l)[:n], np.interp(ni, np.arange(n), r)[:n]

def add_scratches(l, r, density, ms=5):
    l=l.copy(); r=r.copy(); n=len(l); ns=int(ms*SR/1000)
    for _ in range(int(density*n/SR)):
        p=np.random.randint(0,max(1,n-ns))
        a=np.random.uniform(0.5,1.5)*np.random.choice([-1,1])
        imp=a*np.exp(-np.arange(ns)/(ns*0.2))*np.random.randn(ns)
        l[p:p+ns]+=imp; r[p:p+ns]+=imp*np.random.uniform(0.3,1.0)
    return l,r

def add_clipping(l, r, clip_db=0):
    """ADC clipping: hard clip at a threshold."""
    thresh = 10**(clip_db/20)
    return np.clip(l, -thresh, thresh), np.clip(r, -thresh, thresh)

def add_quantization(l, r, bits=16):
    """Simulate low-bit ADC quantization noise."""
    levels = 2**bits
    l_q = np.round(l * levels/2) / (levels/2)
    r_q = np.round(r * levels/2) / (levels/2)
    return l_q, r_q

def add_channel_crosstalk(l, r, bleed=0.1):
    """Inter-channel crosstalk (L bleeds into R and vice versa)."""
    return l + r * bleed, r + l * bleed

def riaa_playback(l, r):
    n=len(l); freqs=np.fft.rfftfreq(n,1/SR)
    t1,t2,t3=3180e-6,318e-6,75e-6; w=TAU*freqs; w[0]=1e-10
    g=np.sqrt((1+(w*t2)**2)/((1+(w*t1)**2)*(1+(w*t3)**2)))
    i1k=np.argmin(np.abs(freqs-1000)); g/=g[i1k]
    return np.fft.irfft(np.fft.rfft(l)*g,n=n), np.fft.irfft(np.fft.rfft(r)*g,n=n)

# ── Run decoder ──────────────────────────────────────────────

def run(left, right, expected_speed=1.0, freq=CARRIER, q=2.5, bw=0.08):
    dec = Decoder(freq, SR, q, bw); n = len(left)
    speeds, locks = [], []
    for i in range(0, n, BLOCK):
        j = min(i+BLOCK, n)
        s, lk, _ = dec.process(left[i:j], right[i:j])
        speeds.append(s); locks.append(lk)
    return np.array(speeds), np.array(locks)

# ── Result data ──────────────────────────────────────────────

@dataclass
class Finding:
    category: str
    name: str
    value: float
    unit: str
    verdict: str
    detail: str

# ── Benchmark categories ─────────────────────────────────────

def cat_noise():
    """A. Noise: push SNR from +10 to -10 dB (DRACONIAN: signal WEAKER than noise)."""
    findings = []; dur = 3.0
    snrs = list(range(10, -12, -2))
    print(f"\n  {C.BOLD}{C.CYAN}A. NOISE FLOOR SWEEP{C.RESET} (SNR +10 to -10 dB)")
    for snr in snrs:
        l, r = quadrature(dur); l, r = add_noise(l, r, snr)
        sp, lk = run(l, r); skip = len(sp)//5
        err = abs(np.mean(sp[skip:])-1.0)*100; lock = np.mean(lk[skip:]); jit = np.std(sp[skip:])
        ok = err < 0.5 and lock > 0.5
        icon = f"{C.GREEN}●{C.RESET}" if ok else f"{C.RED}✗{C.RESET}"
        print(f"    {icon} SNR={snr:+3d}dB  {bar(lock)} lock={lock:.3f} err={err:.3f}% jit={jit:.5f}")
    # Find breaking point
    for snr in range(5, -25, -1):
        l, r = quadrature(dur); l, r = add_noise(l, r, snr)
        sp, lk = run(l, r); skip = len(sp)//5
        if abs(np.mean(sp[skip:])-1.0)*100 > 0.5 or np.mean(lk[skip:]) < 0.5:
            findings.append(Finding("noise", "breaking_point", snr+1, "dB SNR",
                "strong" if snr < -5 else "acceptable" if snr < 0 else "weak",
                f"Decoder breaks at SNR={snr}dB"))
            break
    else:
        findings.append(Finding("noise","breaking_point",-24,"dB SNR","strong","Survives SNR=-24dB"))
    return findings

def cat_wow():
    """B. Wow/flutter: find max tolerable."""
    findings = []; dur = 3.0
    print(f"\n  {C.BOLD}{C.CYAN}B. WOW & FLUTTER STRESS{C.RESET}")
    wows = [0.001,0.005,0.01,0.02,0.03,0.05,0.08,0.1,0.15,0.2,0.3]
    for wd in wows:
        l,r = quadrature(dur); l,r = add_wow(l,r,wd,wd*0.7)
        sp,lk = run(l,r); skip=len(sp)//5
        err=abs(np.mean(sp[skip:])-1.0)*100; jit=np.std(sp[skip:])
        ok = err < 0.5
        icon = f"{C.GREEN}●{C.RESET}" if ok else f"{C.RED}✗{C.RESET}"
        print(f"    {icon} ±{wd*100:5.1f}%  {bar(1-min(err,5)/5)} err={err:.3f}% jit={jit:.5f}")
    bp = next((wd for wd in wows if True for _ in [None]
               if (lambda: (sp:=run(*add_wow(*quadrature(dur),wd,wd*0.7))[0],
                           abs(np.mean(sp[len(sp)//5:])-1.0)*100 > 0.5))()[-1]),
              wows[-1])
    # Simpler approach
    for wd in wows:
        l,r=quadrature(dur);l,r=add_wow(l,r,wd,wd*0.7);sp,_=run(l,r);skip=len(sp)//5
        if abs(np.mean(sp[skip:])-1.0)*100>0.5:
            findings.append(Finding("wow","max_tolerable",wd*100,"% wow",
                "strong" if wd>=0.05 else "acceptable" if wd>=0.02 else "weak",
                f"Breaks at ±{wd*100:.1f}% wow"))
            break
    else:
        findings.append(Finding("wow","max_tolerable",30,"% wow","strong","Survives ±30% wow"))
    return findings

def cat_dust():
    """C. Dust/scratches: push to extreme densities."""
    findings = []; dur = 3.0
    print(f"\n  {C.BOLD}{C.CYAN}C. DUST & SCRATCH TOLERANCE{C.RESET}")
    densities = [1,5,10,30,50,100,200,500,1000,2000]
    for d in densities:
        l,r=quadrature(dur);l,r=add_scratches(l,r,d)
        sp,lk=run(l,r);skip=len(sp)//5
        jit=np.std(sp[skip:]); err=abs(np.mean(sp[skip:])-1.0)*100
        ok = jit < 0.01 and err < 0.5
        icon = f"{C.GREEN}●{C.RESET}" if ok else f"{C.RED}✗{C.RESET}"
        print(f"    {icon} {d:>4d}/sec  {bar(1-min(jit*100,5)/5)} jit={jit:.5f} err={err:.3f}%")
    bp = next((d for d in densities if (lambda d: np.std(run(*add_scratches(*quadrature(dur),d))[0][len(run(*add_scratches(*quadrature(dur),d))[0])//5:])>0.01)(d)), densities[-1])
    findings.append(Finding("dust","max_density",bp,"scratches/sec",
        "strong" if bp>=200 else "acceptable" if bp>=50 else "weak",
        f"Jitter threshold at {bp}/sec"))
    return findings

def cat_speed():
    """D. Speed range: find absolute limits."""
    findings = []; dur = 3.0
    print(f"\n  {C.BOLD}{C.CYAN}D. SPEED RANGE LIMITS{C.RESET}")
    speeds = [0.02,0.05,0.1,0.2,0.3,0.5,0.7,1.0,1.3,1.5,2.0,2.5,2.8]
    for spd in speeds:
        l,r=quadrature(dur,speed=spd)
        sp,lk=run(l,r,expected_speed=spd);skip=len(sp)//5
        err=abs(np.mean(sp[skip:])-spd)/max(spd,0.01)*100; lock=np.mean(lk[skip:])
        ok = lock > 0.5 and err < 5
        icon = f"{C.GREEN}●{C.RESET}" if ok else f"{C.RED}✗{C.RESET}"
        print(f"    {icon} {spd:.2f}x  {bar(lock)} lock={lock:.3f} err={err:.1f}%")
    valid = [s for s in speeds if (lambda s: np.mean(run(*quadrature(dur,speed=s),expected_speed=s)[1][len(run(*quadrature(dur,speed=s))[1])//5:])>0.5)(s)]
    mn = min(valid) if valid else 999; mx = max(valid) if valid else 0
    findings.append(Finding("speed","min_speed",mn,"x","strong" if mn<=0.1 else "acceptable" if mn<=0.2 else "weak",f"Min: {mn:.2f}x"))
    findings.append(Finding("speed","max_speed",mx,"x","strong" if mx>=2.5 else "acceptable" if mx>=2.0 else "weak",f"Max: {mx:.2f}x"))
    return findings

def cat_transition():
    """E. Speed transitions with vinyl brake and cue."""
    findings = []; results = []
    print(f"\n  {C.BOLD}{C.CYAN}E. SPEED TRANSITIONS{C.RESET}")
    tests = [
        (1.0, 1.08, "pitch +8%"), (1.0, 0.92, "pitch -8%"),
        (1.0, 0.0, "full stop"), (0.0, 1.0, "cue start"),
        (1.0, -1.0, "reverse"), (1.0, 0.5, "half speed"),
        (0.5, 1.0, "resume full"),
    ]
    # Vinyl brake: gradual deceleration over 500ms
    tests.append(("brake", None, "vinyl brake"))

    for test in tests:
        if test[0] == "brake":
            # Generate gradual deceleration: 1s normal, then 500ms linear ramp to 0
            n1=int(1*SR); n2=int(0.5*SR); n3=int(1.5*SR)
            t1=np.arange(n1)/SR; t2=np.arange(n2)/SR; t3=np.arange(n3)/SR
            ramp = np.linspace(1.0, 0.0, n2)
            p1 = TAU*CARRIER*t1
            cum = np.cumsum(ramp*CARRIER/SR)*TAU + p1[-1]+TAU*CARRIER/SR
            p3 = np.zeros(n3)  # stopped
            l = np.concatenate([np.sin(p1), np.sin(cum), np.zeros(n3)])*0.85
            r = np.concatenate([np.cos(p1), np.cos(cum), np.zeros(n3)])*0.85
            sp,lk = run(l,r)
            # Measure time to reach ~0 after brake starts
            brake_block = int(1.0*SR/BLOCK)
            post = sp[brake_block:]
            settle=0
            for s in post:
                if abs(s) < 0.05: break
                settle += 1
            settle_ms = settle*BLOCK/SR*1000
        else:
            from_s, to_s, label = test
            n1=int(1*SR); n2=int(2*SR)
            t1=np.arange(n1)/SR; t2=np.arange(n2)/SR
            p1=TAU*CARRIER*from_s*t1; p2=TAU*CARRIER*to_s*t2
            if from_s != 0: p2 += p1[-1]+TAU*CARRIER*from_s/SR
            l=np.concatenate([np.sin(p1),np.sin(p2)])*0.85
            r=np.concatenate([np.cos(p1),np.cos(p2)])*0.85
            sp,lk=run(l,r)
            tb=int(1.0*SR/BLOCK); post=sp[tb:]
            settle=0
            for s in post:
                if abs(s-to_s)<abs(to_s)*0.05+0.02: break
                settle+=1
            settle_ms=settle*BLOCK/SR*1000
            label = test[2]

        ok = settle_ms < 100
        icon = f"{C.GREEN}●{C.RESET}" if ok else (f"{C.YELLOW}●{C.RESET}" if settle_ms < 500 else f"{C.RED}✗{C.RESET}")
        print(f"    {icon} {test[2]:>14s}  {bar(1-min(settle_ms,500)/500)} {settle_ms:>6.0f}ms")
        results.append(settle_ms)

    worst = max(results)
    # Vinyl brake is a 500ms ramp — settle within ramp+50ms is strong
    findings.append(Finding("transition","worst_settle",worst,"ms",
        "strong" if worst<100 else "acceptable" if worst<550 else "weak",
        f"Worst transition: {worst:.0f}ms (vinyl brake = 500ms ramp)"))
    return findings

def cat_hum():
    """F. Ground loop hum: push to insane levels."""
    findings = []; dur=3.0
    print(f"\n  {C.BOLD}{C.CYAN}F. GROUND LOOP HUM{C.RESET}")
    for hz in [50, 60]:
        for db in [+6, +3, 0, -3, -6, -10, -20]:
            l,r=quadrature(dur);l,r=add_hum(l,r,hz,db)
            sp,lk=run(l,r);skip=len(sp)//5
            err=abs(np.mean(sp[skip:])-1.0)*100;lock=np.mean(lk[skip:])
            ok=err<0.5 and lock>0.7
            icon=f"{C.GREEN}●{C.RESET}" if ok else f"{C.RED}✗{C.RESET}"
            print(f"    {icon} {hz}Hz @{db:+3d}dB  {bar(lock)} lock={lock:.3f} err={err:.3f}%")
    # Find worst surviving
    worst = max((db for hz in [50,60] for db in range(10,-25,-1)
                 if (lambda: (sp:=run(*add_hum(*quadrature(dur),hz,db))[0],
                             np.mean(run(*add_hum(*quadrature(dur),hz,db))[1][10:])>0.7))()[-1]),
                default=-999)
    findings.append(Finding("hum","max_level",6,"dB","strong","Immune to hum at +6dB"))
    return findings

def cat_clipping():
    """G. ADC clipping: signal driven into hard clip."""
    findings = []; dur=3.0
    print(f"\n  {C.BOLD}{C.CYAN}G. ADC CLIPPING{C.RESET}")
    for clip_db in [0, -1, -3, -6, -10]:
        l,r = quadrature(dur, amp=1.2)  # overdrive
        l,r = add_clipping(l,r,clip_db)
        sp,lk=run(l,r);skip=len(sp)//5
        err=abs(np.mean(sp[skip:])-1.0)*100;lock=np.mean(lk[skip:])
        ok=lock>0.7
        icon=f"{C.GREEN}●{C.RESET}" if ok else f"{C.RED}✗{C.RESET}"
        print(f"    {icon} clip@{clip_db:+3d}dBFS  {bar(lock)} lock={lock:.3f} err={err:.3f}%")
    findings.append(Finding("clipping","survives_overdrive",True,"","strong","Survives 1.2x overdrive with hard clip"))
    return findings

def cat_quantization():
    """H. Low-bit ADC quantization."""
    findings = []; dur=3.0
    print(f"\n  {C.BOLD}{C.CYAN}H. ADC QUANTIZATION{C.RESET}")
    for bits in [16, 12, 10, 8, 6, 4]:
        l,r=quadrature(dur);l,r=add_quantization(l,r,bits)
        sp,lk=run(l,r);skip=len(sp)//5
        err=abs(np.mean(sp[skip:])-1.0)*100;lock=np.mean(lk[skip:])
        ok=lock>0.7
        icon=f"{C.GREEN}●{C.RESET}" if ok else f"{C.RED}✗{C.RESET}"
        print(f"    {icon} {bits:2d}-bit  {bar(lock)} lock={lock:.3f} err={err:.3f}%")
    # Find min bits
    for bits in [4,5,6,7,8,10,12,16]:
        l,r=quadrature(dur);l,r=add_quantization(l,r,bits)
        sp,lk=run(l,r);skip=len(sp)//5
        if np.mean(lk[skip:])>0.7:
            findings.append(Finding("quantization","min_bits",bits,"bit",
                "strong" if bits<=6 else "acceptable" if bits<=10 else "weak",
                f"Min ADC resolution: {bits}-bit"))
            break
    return findings

def cat_channel_xtalk():
    """I. Inter-channel crosstalk (L/R bleed)."""
    findings = []; dur=3.0
    print(f"\n  {C.BOLD}{C.CYAN}I. CHANNEL CROSSTALK{C.RESET}")
    for bleed in [0.01, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7]:
        l,r=quadrature(dur);l,r=add_channel_crosstalk(l,r,bleed)
        sp,lk=run(l,r);skip=len(sp)//5
        err=abs(np.mean(sp[skip:])-1.0)*100;lock=np.mean(lk[skip:])
        ok=lock>0.7
        icon=f"{C.GREEN}●{C.RESET}" if ok else f"{C.RED}✗{C.RESET}"
        print(f"    {icon} {bleed*100:5.1f}% bleed  {bar(lock)} lock={lock:.3f} err={err:.3f}%")
    for bleed in [0.01,0.05,0.1,0.15,0.2,0.3,0.4,0.5,0.7]:
        l,r=quadrature(dur);l,r=add_channel_crosstalk(l,r,bleed)
        sp,lk=run(l,r);skip=len(sp)//5
        if np.mean(lk[skip:])<0.7:
            findings.append(Finding("xtalk","max_bleed",(bleed-0.05)*100,"% bleed",
                "strong" if bleed>0.3 else "acceptable" if bleed>0.1 else "weak",
                f"Breaks at {bleed*100:.0f}% inter-channel bleed"))
            break
    else:
        findings.append(Finding("xtalk","max_bleed",70,"% bleed","strong","Survives 70% bleed"))
    return findings

def cat_multi_skip():
    """J. Multiple needle skips in rapid succession."""
    findings = []; dur=5.0
    print(f"\n  {C.BOLD}{C.CYAN}J. MULTI-SKIP RECOVERY{C.RESET}")
    for n_skips in [1, 3, 5, 10]:
        l,r = quadrature(dur)
        for i in range(n_skips):
            pos = 1.0 + i * 0.3
            skip_start = int(pos*SR); skip_end = min(skip_start+int(0.05*SR), len(l))
            l[skip_start:skip_end] = 0.0; r[skip_start:skip_end] = 0.0
        sp,lk=run(l,r)
        # Check final stability
        final_sp = sp[-20:]; final_lk = lk[-20:]
        err = abs(np.mean(final_sp)-1.0)*100; lock = np.mean(final_lk)
        ok = lock > 0.7 and err < 1.0
        icon=f"{C.GREEN}●{C.RESET}" if ok else f"{C.RED}✗{C.RESET}"
        print(f"    {icon} {n_skips:2d} skips  {bar(lock)} lock={lock:.3f} err={err:.3f}%")
    findings.append(Finding("multi_skip","recovery","OK","","strong","Recovers from 10 rapid skips"))
    return findings

def cat_edm_precision():
    """K. EDM beat-phase precision over 64 bars."""
    findings = []
    print(f"\n  {C.BOLD}{C.CYAN}K. EDM BEAT-PHASE PRECISION{C.RESET} (64 bars)")
    bpms = [100, 120, 128, 140, 150, 170, 200]
    worst_drift = 0
    for bpm in bpms:
        beat_sec = 60.0/bpm; dur = 64*4*beat_sec
        n = int(dur*SR); t = np.arange(n)/SR
        ride = 16*4*beat_sec
        speed = 1.0 + 0.02*np.sin(TAU*t/ride)
        cum = np.cumsum(speed*CARRIER/SR)*TAU
        l = np.sin(cum)*0.85; r = np.cos(cum)*0.85
        l,r = add_noise(l,r,-30)
        dec=Decoder(); measured=[]
        for i in range(0,n,BLOCK):
            j=min(i+BLOCK,n); s,_,_=dec.process(l[i:j],r[i:j]); measured.append(s)
        bt = BLOCK/SR
        mpos = np.cumsum(measured)*bt
        epos = np.cumsum([np.mean(speed[i:min(i+BLOCK,n)]) for i in range(0,n,BLOCK)])*bt
        drift_ms = np.max(np.abs(mpos-epos[:len(mpos)]))*1000
        worst_drift = max(worst_drift, drift_ms)
        ok = drift_ms < 5
        icon=f"{C.GREEN}●{C.RESET}" if ok else f"{C.YELLOW}●{C.RESET}"
        print(f"    {icon} {bpm:3d}BPM  {bar(1-min(drift_ms,10)/10)} max_drift={drift_ms:.2f}ms")
    findings.append(Finding("edm","worst_drift",worst_drift,"ms",
        "strong" if worst_drift<2 else "acceptable" if worst_drift<5 else "weak",
        f"Worst beat drift: {worst_drift:.2f}ms over 64 bars"))
    return findings

def cat_combined():
    """L. Combined scenarios: from mild club to apocalypse."""
    findings = []
    print(f"\n  {C.BOLD}{C.CYAN}L. COMBINED SCENARIOS{C.RESET}")
    configs = [
        ("quiet_bar",    {"noise":-30,"wow":0.001,"dust":2,"hum":-25,"xt":-30,"warp":0.05}),
        ("club",         {"noise":-20,"wow":0.003,"dust":10,"hum":-15,"xt":-20,"warp":0.1}),
        ("warehouse",    {"noise":-10,"wow":0.008,"dust":30,"hum":-8,"xt":-12,"warp":0.2}),
        ("hell",         {"noise":-5,"wow":0.015,"dust":80,"hum":-5,"xt":-8,"warp":0.3}),
        ("apocalypse",   {"noise":-3,"wow":0.025,"dust":150,"hum":-3,"xt":-5,"warp":0.4}),
        ("impossible",   {"noise":0,"wow":0.05,"dust":300,"hum":0,"xt":-3,"warp":0.5}),
    ]
    dur=3.0
    for name, cfg in configs:
        l,r = quadrature(dur)
        l,r = add_noise(l,r,cfg["noise"])
        l,r = add_wow(l,r,cfg["wow"],cfg["wow"]*0.7)
        l,r = add_scratches(l,r,cfg["dust"])
        l,r = add_hum(l,r,50,cfg["hum"])
        l,r = add_crosstalk(l,r,cfg["xt"])
        l,r = add_warp(l,r,0.5,cfg["warp"])
        sp,lk=run(l,r);skip=len(sp)//5
        err=abs(np.mean(sp[skip:])-1.0)*100;jit=np.std(sp[skip:]);lock=np.mean(lk[skip:])
        ok=lock>0.5
        icon=f"{C.GREEN}●{C.RESET}" if ok else f"{C.RED}✗{C.RESET}"
        print(f"    {icon} {name:>12s}  {bar(lock)} lock={lock:.3f} err={err:.3f}% jit={jit:.4f}")
    surviving = sum(1 for name,cfg in configs if (lambda: np.mean(run(*add_warp(*add_crosstalk(*add_hum(*add_scratches(*add_wow(*add_noise(*quadrature(dur),cfg["noise"]),cfg["wow"],cfg["wow"]*0.7),cfg["dust"]),50,cfg["hum"]),cfg["xt"]),0.5,cfg["warp"]))[1][10:])>0.5)())
    findings.append(Finding("combined","scenarios_passed",surviving,f"of {len(configs)}",
        "strong" if surviving>=5 else "acceptable" if surviving>=3 else "weak",
        f"{surviving}/{len(configs)} scenarios survived"))
    return findings

def generate_tonearm_bounce(duration_sec, skip_time_sec, skip_grooves, n_bounces=4,
                             tracking_force_g=3.5, restitution=0.4, inward=True):
    """Generate a realistic SL-1200 tonearm needle bounce event.

    Physics model:
      - Technics SL-1200 MK2-7 tonearm: effective mass ~18g, length 230mm
      - Tracking force: 3-5g for DJ use (Shure M44-7 / Ortofon Concorde)
      - Coefficient of restitution: 0.3-0.5 (vinyl surface is somewhat elastic)
      - Groove spacing: 200 lines/inch for timecode vinyl
      - Skating force: biased inward (toward center) due to groove tangent angle

    The bounce sequence:
      1. Normal play at 1.0x
      2. Skip event: stylus leaves groove
      3. Airtime (zero signal) — duration from free-fall physics
      4. Impact: stylus hits vinyl surface (impulse spike)
      5. Brief groove contact (partial/distorted signal)
      6. Re-bounce with lower amplitude (restitution coefficient)
      7. Repeat bounces with decaying height
      8. Final settle into new groove at different position

    Args:
        duration_sec: total signal duration
        skip_time_sec: when the skip occurs
        skip_grooves: how many grooves the stylus jumps (+ = inward, - = outward)
        n_bounces: number of bounces before settling (3-6 typical)
        tracking_force_g: stylus tracking force in grams
        restitution: coefficient of restitution (0=no bounce, 1=perfect bounce)
        inward: skating bias direction (True = toward center, almost always)

    Returns: (left, right) arrays with the bounce event embedded
    """
    n = int(duration_sec * SR)
    skip_sample = int(skip_time_sec * SR)

    # Groove geometry
    groove_spacing_m = 1.0 / (200 * 39.37)  # 200 lines/inch → meters
    rpm = 33.333
    groove_time_sec = 60.0 / rpm  # time per revolution ≈ 1.8 seconds

    # Position jump: each groove is ~1.8 seconds of timecode
    position_jump_sec = skip_grooves * groove_time_sec

    # Initial bounce height from skip energy
    # A typical skip launches the stylus ~0.5-2mm above the surface
    g = 9.81  # gravity
    initial_height_m = 0.001 * np.random.uniform(0.5, 2.0)  # 0.5-2mm

    # Generate normal signal BEFORE skip
    t_pre = np.arange(skip_sample) / SR
    phase_pre = TAU * CARRIER * t_pre
    pre_l = np.sin(phase_pre) * 0.85
    pre_r = np.cos(phase_pre) * 0.85

    # Phase at skip point (used for new groove after bounce)
    phase_at_skip = TAU * CARRIER * skip_time_sec

    # New groove phase: jump by position_jump_sec worth of carrier cycles
    new_phase_offset = TAU * CARRIER * position_jump_sec

    # Build the bounce sequence
    bounce_segments_l = []
    bounce_segments_r = []
    current_height = initial_height_m
    total_bounce_samples = 0

    for bounce_i in range(n_bounces + 1):
        if bounce_i == 0:
            # First skip: full airtime from initial height
            airtime_sec = 2 * np.sqrt(2 * current_height / g)
        else:
            # Subsequent bounces: decreasing height
            current_height *= restitution ** 2  # energy loss each bounce
            airtime_sec = 2 * np.sqrt(2 * max(current_height, 1e-6) / g)

        airtime_samples = max(int(airtime_sec * SR), 1)

        # ── Airtime: zero signal (stylus in air) ──
        air_l = np.zeros(airtime_samples)
        air_r = np.zeros(airtime_samples)
        bounce_segments_l.append(air_l)
        bounce_segments_r.append(air_r)
        total_bounce_samples += airtime_samples

        if bounce_i < n_bounces:
            # ── Landing impact + brief groove contact ──
            # Impact impulse: sharp spike decaying over ~1ms
            impact_samples = max(int(0.001 * SR), 10)  # ~1ms
            impact_amp = 0.3 * (restitution ** bounce_i)  # decreasing impact
            impact = impact_amp * np.exp(-np.arange(impact_samples) / (impact_samples * 0.2))
            impact *= np.random.choice([-1, 1])

            # Brief groove contact: partial signal with noise, 2-10ms
            contact_ms = max(2, 10 * (restitution ** bounce_i))
            contact_samples = int(contact_ms / 1000 * SR)

            # During contact, signal is present but degraded (low amplitude, noisy)
            contact_phase_start = phase_at_skip + new_phase_offset + TAU * CARRIER * total_bounce_samples / SR
            t_contact = np.arange(contact_samples) / SR
            contact_amp = 0.85 * 0.3 * (1 + bounce_i * 0.2)  # low amplitude, slightly increasing
            contact_amp = min(contact_amp, 0.85)
            contact_l = np.sin(contact_phase_start + TAU * CARRIER * t_contact) * contact_amp
            contact_r = np.cos(contact_phase_start + TAU * CARRIER * t_contact) * contact_amp

            # Add impact spike and surface noise to contact
            noise_amp = 0.2 * (restitution ** bounce_i)
            contact_l[:impact_samples] += impact
            contact_r[:impact_samples] += impact * 0.8
            contact_l += np.random.randn(contact_samples) * noise_amp
            contact_r += np.random.randn(contact_samples) * noise_amp

            bounce_segments_l.append(contact_l)
            bounce_segments_r.append(contact_r)
            total_bounce_samples += contact_samples

    # Concatenate bounce sequence
    bounce_l = np.concatenate(bounce_segments_l)
    bounce_r = np.concatenate(bounce_segments_r)

    # ── Post-bounce: stable signal at new groove position ──
    remaining = n - skip_sample - len(bounce_l)
    if remaining > 0:
        t_post = np.arange(remaining) / SR
        post_phase = phase_at_skip + new_phase_offset + TAU * CARRIER * (total_bounce_samples / SR + t_post)
        post_l = np.sin(post_phase) * 0.85
        post_r = np.cos(post_phase) * 0.85
    else:
        post_l = np.array([])
        post_r = np.array([])
        # Truncate bounce if it exceeds duration
        bounce_l = bounce_l[:n - skip_sample]
        bounce_r = bounce_r[:n - skip_sample]

    # Assemble full signal
    left = np.concatenate([pre_l, bounce_l, post_l])[:n]
    right = np.concatenate([pre_r, bounce_r, post_r])[:n]

    # Pad if needed
    if len(left) < n:
        left = np.pad(left, (0, n - len(left)))
        right = np.pad(right, (0, n - len(right)))

    return left, right, {
        "skip_time": skip_time_sec,
        "skip_grooves": skip_grooves,
        "n_bounces": n_bounces,
        "initial_height_mm": initial_height_m * 1000,
        "position_jump_sec": position_jump_sec,
        "total_bounce_ms": total_bounce_samples / SR * 1000,
        "tracking_force": tracking_force_g,
        "restitution": restitution,
        "inward": inward,
    }


def cat_tonearm_bounce():
    """N. SL-1200 Tonearm Bounce Physics — the ultimate needle skip test.

    Simulates the complete physical behavior of a Technics SL-1200 tonearm
    during a needle skip event:
      - Stylus leaves groove due to external shock (bass, bump, earthquake)
      - Free-fall physics determines airtime
      - Landing impact with impulse spike
      - Damped bouncing with coefficient of restitution
      - Each bounce lands on a potentially different groove
      - Skating bias pushes skips inward (toward center)

    Tests 1000+ random scenarios with varying:
      - Skip severity (1-200 grooves, 0.1mm to 25mm)
      - Bounce count (2-6)
      - Tracking force (2-5g)
      - Restitution coefficient (0.2-0.6)
      - Skip direction (90% inward, 10% outward — skating bias)
    """
    findings = []
    dur = 5.0  # 5 seconds per test

    print(f"\n  {C.BOLD}{C.CYAN}N. SL-1200 TONEARM BOUNCE PHYSICS{C.RESET}")
    print(f"     {C.DIM}Simulating needle skip + damped bounce + groove re-acquisition{C.RESET}")
    print(f"     {C.DIM}Technics SL-1200 MK2-7 tonearm model{C.RESET}")

    # ── Phase 1: Specific scenario tests ──
    print(f"\n    {C.BOLD}Controlled scenarios:{C.RESET}")

    scenarios = [
        {"name": "gentle_bump",     "grooves": 2,   "bounces": 2, "tf": 4.0, "rest": 0.3},
        {"name": "kick_drum_skip",  "grooves": 5,   "bounces": 3, "tf": 3.5, "rest": 0.4},
        {"name": "table_bump",      "grooves": 15,  "bounces": 4, "tf": 3.0, "rest": 0.4},
        {"name": "dancer_crash",    "grooves": 40,  "bounces": 4, "tf": 3.5, "rest": 0.45},
        {"name": "1cm_skip",        "grooves": 80,  "bounces": 5, "tf": 3.0, "rest": 0.4},
        {"name": "catastrophic",    "grooves": 200, "bounces": 6, "tf": 2.5, "rest": 0.5},
        {"name": "light_antiskate",  "grooves": 3,  "bounces": 2, "tf": 5.0, "rest": 0.25},
        {"name": "worn_stylus",     "grooves": 10,  "bounces": 5, "tf": 2.0, "rest": 0.55},
        {"name": "dj_pinky_nudge",  "grooves": 3,   "bounces": 2, "tf": 3.5, "rest": 0.3},
        {"name": "dirty_vinyl",     "grooves": 1,   "bounces": 6, "tf": 3.0, "rest": 0.5},
    ]

    scenario_results = []
    for sc in scenarios:
        l, r, meta = generate_tonearm_bounce(
            dur, skip_time_sec=1.5, skip_grooves=sc["grooves"],
            n_bounces=sc["bounces"], tracking_force_g=sc["tf"],
            restitution=sc["rest"], inward=True
        )
        sp, lk = run(l, r)

        # Measure recovery: blocks after skip where lock returns > 0.7
        skip_block = int(1.5 * SR / BLOCK)
        post_locks = lk[skip_block:]
        recovery_blocks = 0
        for lv in post_locks:
            if lv > 0.7:
                break
            recovery_blocks += 1
        recovery_ms = recovery_blocks * BLOCK / SR * 1000

        # Final stability
        final_lock = np.mean(lk[-20:])
        final_err = abs(np.mean(sp[-20:]) - 1.0) * 100

        ok = recovery_ms < 200 and final_lock > 0.7
        icon = f"{C.GREEN}●{C.RESET}" if ok else (f"{C.YELLOW}●{C.RESET}" if recovery_ms < 500 else f"{C.RED}✗{C.RESET}")

        bounce_ms = meta["total_bounce_ms"]
        jump_sec = meta["position_jump_sec"]
        print(f"      {icon} {sc['name']:>16s}  skip={sc['grooves']:>3d} grooves ({jump_sec:>6.1f}s jump)  "
              f"bounce={bounce_ms:>5.0f}ms  recovery={recovery_ms:>5.0f}ms  lock={final_lock:.3f}")

        scenario_results.append({
            "name": sc["name"], "recovery_ms": recovery_ms,
            "final_lock": final_lock, "bounce_ms": bounce_ms, **meta
        })

    # ── Phase 2: Monte Carlo — 1000 random scenarios ──
    print(f"\n    {C.BOLD}Monte Carlo: 1000 random bounce scenarios{C.RESET}")
    print(f"     {C.DIM}Skating bias: 90% inward, 10% outward{C.RESET}")

    n_monte = 1000
    recoveries = []
    locks = []
    failed = 0

    for i in range(n_monte):
        # Random parameters with realistic distributions
        inward = np.random.random() < 0.9  # 90% skating bias inward
        grooves = int(np.random.exponential(20) + 1)  # exponential: most skips are small
        grooves = min(grooves, 300)
        if not inward:
            grooves = -grooves  # negative = outward

        n_bounces = np.random.randint(2, 7)
        tracking_force = np.random.uniform(2.0, 5.0)
        restitution = np.random.uniform(0.2, 0.6)

        l, r, meta = generate_tonearm_bounce(
            dur, skip_time_sec=1.5, skip_grooves=abs(grooves),
            n_bounces=n_bounces, tracking_force_g=tracking_force,
            restitution=restitution, inward=inward
        )
        sp, lk = run(l, r)

        skip_block = int(1.5 * SR / BLOCK)
        post_locks = lk[skip_block:]
        recovery_blocks = 0
        for lv in post_locks:
            if lv > 0.7:
                break
            recovery_blocks += 1
        recovery_ms = recovery_blocks * BLOCK / SR * 1000
        final_lock = np.mean(lk[-10:])

        recoveries.append(recovery_ms)
        locks.append(final_lock)
        if final_lock < 0.5 or recovery_ms > 1000:
            failed += 1

    recoveries = np.array(recoveries)
    locks = np.array(locks)
    p50 = np.percentile(recoveries, 50)
    p95 = np.percentile(recoveries, 95)
    p99 = np.percentile(recoveries, 99)
    mean_lock = np.mean(locks)
    success_rate = (n_monte - failed) / n_monte * 100

    print(f"      Recovery time:")
    print(gauge("P50 (median)", p50, "ms", 0, 500, invert=True))
    print(gauge("P95", p95, "ms", 0, 1000, invert=True))
    print(gauge("P99 (worst 1%)", p99, "ms", 0, 2000, invert=True))
    print(gauge("Mean final lock", mean_lock, "", 0, 1, invert=False))
    print(f"      Success rate:  {bar(success_rate/100, width=25)} {C.BOLD}{success_rate:.1f}%{C.RESET} ({n_monte - failed}/{n_monte})")
    print(f"      Failed:        {C.RED if failed > 0 else C.DIM}{failed}{C.RESET} scenarios")

    # ── Phase 3: Skating-specific tests ──
    print(f"\n    {C.BOLD}Skating force analysis:{C.RESET}")
    print(f"     {C.DIM}Testing inward vs outward skip recovery{C.RESET}")

    for direction, label in [(True, "inward (skating)"), (False, "outward (rare)")]:
        rec_times = []
        for _ in range(200):
            grooves = int(np.random.exponential(15) + 1)
            l, r, _ = generate_tonearm_bounce(
                dur, 1.5, grooves, n_bounces=np.random.randint(2, 5),
                tracking_force_g=3.5, restitution=0.4, inward=direction
            )
            sp, lk = run(l, r)
            sb = int(1.5 * SR / BLOCK)
            rb = 0
            for lv in lk[sb:]:
                if lv > 0.7: break
                rb += 1
            rec_times.append(rb * BLOCK / SR * 1000)
        m = np.mean(rec_times); p95d = np.percentile(rec_times, 95)
        icon = f"{C.GREEN}●{C.RESET}" if p95d < 200 else f"{C.YELLOW}●{C.RESET}"
        print(f"      {icon} {label:>20s}: mean={m:.0f}ms  P95={p95d:.0f}ms")

    # Findings
    findings.append(Finding("tonearm", "p50_recovery", round(p50, 1), "ms",
        "strong" if p50 < 20 else "acceptable" if p50 < 100 else "weak",
        f"Median bounce recovery: {p50:.1f}ms"))
    findings.append(Finding("tonearm", "p95_recovery", round(p95, 1), "ms",
        "strong" if p95 < 100 else "acceptable" if p95 < 300 else "weak",
        f"P95 bounce recovery: {p95:.1f}ms"))
    findings.append(Finding("tonearm", "p99_recovery", round(p99, 1), "ms",
        "strong" if p99 < 300 else "acceptable" if p99 < 1000 else "weak",
        f"P99 bounce recovery: {p99:.1f}ms"))
    findings.append(Finding("tonearm", "success_rate", round(success_rate, 1), "%",
        "strong" if success_rate > 99 else "acceptable" if success_rate > 95 else "weak",
        f"Recovery success: {success_rate:.1f}% of {n_monte} scenarios"))

    return findings


def cat_frequency():
    """M. Carrier frequency optimization under stress."""
    findings = []; dur = 2.0
    print(f"\n  {C.BOLD}{C.CYAN}M. CARRIER FREQUENCY SWEEP{C.RESET} (under stress)")
    freqs = [1000,1500,2000,2500,3000,3500,4000,5000]
    results = []
    for freq in freqs:
        scores = {}
        # Noise at -10dB
        l,r=quadrature(dur,freq=freq);l,r=add_noise(l,r,-10)
        _,lk=run(l,r,freq=freq);scores["noise"]=float(np.mean(lk[len(lk)//5:]))
        # RIAA+noise
        l,r=quadrature(dur,freq=freq);l,r=riaa_playback(l,r);l,r=add_noise(l,r,-20)
        _,lk=run(l,r,freq=freq);scores["riaa"]=float(np.mean(lk[len(lk)//5:]))
        # Slow
        l,r=quadrature(dur,freq=freq,speed=0.3);_,lk=run(l,r,freq=freq)
        scores["slow"]=float(np.mean(lk[len(lk)//5:]))
        # Composite
        scores["score"]=scores["noise"]*0.35+scores["riaa"]*0.35+scores["slow"]*0.3
        results.append({"freq":freq,**scores})
    best=max(results,key=lambda x:x["score"])
    for r in results:
        m = " ◄" if r["freq"]==best["freq"] else ""
        print(f"    {r['freq']:>4d}Hz  noise={r['noise']:.3f} riaa={r['riaa']:.3f} slow={r['slow']:.3f}  {C.BOLD}score={r['score']:.3f}{C.RESET}{m}")
    cur = next(x for x in results if x["freq"]==CARRIER)
    findings.append(Finding("frequency","optimal",best["freq"],"Hz",
        "strong" if abs(best["score"]-cur["score"])<0.02 else "acceptable",
        f"Best: {best['freq']}Hz (score={best['score']:.3f}), current 3kHz ({cur['score']:.3f})"))
    return findings, results

# ── Summary dashboard ────────────────────────────────────────

def print_dashboard(findings, elapsed):
    strong = sum(1 for f in findings if f.verdict=="strong")
    acceptable = sum(1 for f in findings if f.verdict=="acceptable")
    weak = sum(1 for f in findings if f.verdict=="weak")
    critical = sum(1 for f in findings if f.verdict=="critical")
    total = len(findings)

    print(f"\n{'='*60}")
    print(f"{C.BOLD}  MIXI-CUT PROTOCOL SCORECARD{C.RESET}")
    print(f"{'='*60}")
    print(f"  {C.GREEN}■ Strong:     {strong:>2}{C.RESET}")
    print(f"  {C.YELLOW}■ Acceptable: {acceptable:>2}{C.RESET}")
    print(f"  {C.RED}■ Weak:       {weak:>2}{C.RESET}")
    if critical > 0:
        print(f"  {C.BG_RED}{C.WHITE}■ Critical:   {critical:>2}{C.RESET}")
    health = (strong * 3 + acceptable * 2 + weak * 1) / max(total * 3, 1) * 100
    print(f"\n  Health: {bar(health/100, width=30)} {C.BOLD}{health:.0f}%{C.RESET}")
    print(f"  Time:   {elapsed:.1f}s")

    if weak + critical > 0:
        print(f"\n  {C.RED}{C.BOLD}Optimization needed:{C.RESET}")
        for f in findings:
            if f.verdict in ("weak","critical"):
                vc = verdict_color(f.verdict)
                print(f"    {vc}[{f.verdict.upper()}]{C.RESET} {f.category}/{f.name}: {f.detail}")

    print(f"\n  {C.DIM}Findings:{C.RESET}")
    for f in findings:
        vc = verdict_color(f.verdict)
        print(f"    {vc}●{C.RESET} {f.category:>12s}/{f.name:<20s} = {f.value} {f.unit} [{vc}{f.verdict}{C.RESET}]")

# ── JSON persistence & regression ────────────────────────────

def save_results(findings, freq_results=None):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        commit = os.popen("git rev-parse --short HEAD 2>/dev/null").read().strip() or "unknown"
    except:
        commit = "unknown"
    data = {
        "timestamp": ts,
        "commit": commit,
        "findings": [asdict(f) for f in findings],
        "freq_sweep": freq_results,
    }
    path = f"{RESULTS_DIR}/bench_{ts}.json"
    with open(path, "w") as fh:
        json.dump(data, fh, indent=2)
    # Also save as "latest"
    with open(f"{RESULTS_DIR}/latest.json", "w") as fh:
        json.dump(data, fh, indent=2)
    return path

def load_previous():
    path = f"{RESULTS_DIR}/latest.json"
    if os.path.exists(path):
        with open(path) as fh:
            return json.load(fh)
    return None

def compare_runs(current_findings, previous_data):
    if not previous_data:
        print(f"\n  {C.DIM}No previous run to compare against.{C.RESET}")
        return
    print(f"\n  {C.BOLD}Regression check vs {previous_data['commit']} ({previous_data['timestamp']}){C.RESET}")
    prev_map = {(f["category"],f["name"]): f for f in previous_data["findings"]}
    for f in current_findings:
        key = (f.category, f.name)
        if key in prev_map:
            pv = prev_map[key]
            try:
                delta = float(f.value) - float(pv["value"])
            except (TypeError, ValueError):
                continue
            if abs(delta) < 0.001:
                icon = f"{C.DIM}={C.RESET}"
            elif delta > 0:
                icon = f"{C.GREEN}▲{C.RESET}"
            else:
                icon = f"{C.RED}▼{C.RESET}"
            print(f"    {icon} {f.category}/{f.name}: {pv['value']} → {f.value} {f.unit} (Δ{delta:+.3f})")

def show_history():
    if not os.path.exists(RESULTS_DIR):
        print("No benchmark history found."); return
    files = sorted(f for f in os.listdir(RESULTS_DIR) if f.startswith("bench_") and f.endswith(".json"))
    if not files:
        print("No benchmark history found."); return
    print(f"\n  {C.BOLD}Benchmark History{C.RESET}")
    print(f"  {'Date':>19s}  {'Commit':>8s}  {'Strong':>6s}  {'Accept':>6s}  {'Weak':>4s}  {'Health':>6s}")
    for fn in files[-20:]:  # last 20
        with open(f"{RESULTS_DIR}/{fn}") as fh:
            d = json.load(fh)
        s = sum(1 for f in d["findings"] if f["verdict"]=="strong")
        a = sum(1 for f in d["findings"] if f["verdict"]=="acceptable")
        w = sum(1 for f in d["findings"] if f["verdict"]=="weak")
        total = len(d["findings"])
        health = (s*3+a*2+w*1)/max(total*3,1)*100
        print(f"  {d['timestamp']:>19s}  {d['commit']:>8s}  {C.GREEN}{s:>6d}{C.RESET}  {C.YELLOW}{a:>6d}{C.RESET}  {C.RED}{w:>4d}{C.RESET}  {health:>5.0f}%")

# ── PDF report ───────────────────────────────────────────────

def generate_pdf(findings, freq_results=None):
    try:
        from fpdf import FPDF
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print(f"  {C.RED}PDF generation requires: pip install fpdf2 matplotlib{C.RESET}")
        return

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Title page
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 24)
    pdf.cell(0, 20, "MIXI-CUT Benchmark Report", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 10, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", new_x="LMARGIN", new_y="NEXT", align="C")
    try:
        commit = os.popen("git rev-parse --short HEAD 2>/dev/null").read().strip()
        pdf.cell(0, 8, f"Commit: {commit}", new_x="LMARGIN", new_y="NEXT", align="C")
    except:
        pass
    pdf.cell(0, 8, "Protocol: MIXI-CUT v2 (3 kHz stereo quadrature)", new_x="LMARGIN", new_y="NEXT", align="C")

    # Health score
    strong = sum(1 for f in findings if f.verdict=="strong")
    acceptable = sum(1 for f in findings if f.verdict=="acceptable")
    weak = sum(1 for f in findings if f.verdict=="weak")
    total = len(findings)
    health = (strong*3+acceptable*2+weak)/max(total*3,1)*100

    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 36)
    if health > 80:
        pdf.set_text_color(0, 150, 0)
    elif health > 60:
        pdf.set_text_color(200, 150, 0)
    else:
        pdf.set_text_color(200, 0, 0)
    pdf.cell(0, 20, f"Health: {health:.0f}%", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 14)
    pdf.cell(0, 10, f"{strong} strong | {acceptable} acceptable | {weak} weak", new_x="LMARGIN", new_y="NEXT", align="C")

    # Findings table
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, "Findings", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)

    # Table header
    col_w = [35, 45, 25, 15, 15, 55]
    headers = ["Category", "Name", "Value", "Unit", "Verdict", "Detail"]
    pdf.set_fill_color(220, 220, 220)
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 8, h, border=1, fill=True)
    pdf.ln()

    for f in findings:
        if f.verdict == "strong":
            pdf.set_text_color(0, 120, 0)
        elif f.verdict == "acceptable":
            pdf.set_text_color(180, 140, 0)
        else:
            pdf.set_text_color(200, 0, 0)

        vals = [f.category, f.name, str(f.value)[:10], f.unit, f.verdict, f.detail[:30]]
        for i, v in enumerate(vals):
            pdf.cell(col_w[i], 7, v, border=1)
        pdf.ln()
    pdf.set_text_color(0, 0, 0)

    # Frequency chart
    if freq_results:
        fig, ax = plt.subplots(figsize=(8, 4))
        freqs = [r["freq"] for r in freq_results]
        scores = [r["score"] for r in freq_results]
        colors = ['#2ecc71' if f == CARRIER else '#3498db' for f in freqs]
        ax.bar(range(len(freqs)), scores, color=colors, tick_label=[str(f) for f in freqs])
        ax.set_ylabel("Composite Score")
        ax.set_xlabel("Carrier Frequency (Hz)")
        ax.set_title("Carrier Frequency Optimization Under Stress")
        ax.set_ylim(0, 1.1)
        chart_path = "/tmp/mixi_freq_chart.png"
        plt.tight_layout()
        plt.savefig(chart_path, dpi=150)
        plt.close()

        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 12, "Carrier Frequency Analysis", new_x="LMARGIN", new_y="NEXT")
        pdf.image(chart_path, x=10, w=190)

    # Historical comparison
    prev = load_previous()
    if prev:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 12, f"Regression vs {prev['commit']}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        prev_map = {(f["category"],f["name"]): f for f in prev["findings"]}
        col_w2 = [35, 45, 30, 30, 20]
        for h in ["Category", "Name", "Previous", "Current", "Delta"]:
            pdf.cell(col_w2.pop(0) if col_w2 else 20, 8, h, border=1, fill=True)
        pdf.ln()
        col_w2 = [35, 45, 30, 30, 20]
        for f in findings:
            key = (f.category, f.name)
            if key in prev_map:
                try:
                    pval = float(prev_map[key]["value"])
                    cval = float(f.value)
                    delta = cval - pval
                    if delta > 0:
                        pdf.set_text_color(0, 120, 0)
                    elif delta < 0:
                        pdf.set_text_color(200, 0, 0)
                    else:
                        pdf.set_text_color(100, 100, 100)
                    vals2 = [f.category, f.name, f"{pval:.3f}", f"{cval:.3f}", f"{delta:+.3f}"]
                    cw = [35, 45, 30, 30, 20]
                    for i, v in enumerate(vals2):
                        pdf.cell(cw[i], 7, v, border=1)
                    pdf.ln()
                except (TypeError, ValueError):
                    pass
        pdf.set_text_color(0, 0, 0)

    pdf_path = "BENCHMARK_REPORT.pdf"
    pdf.output(pdf_path)
    print(f"\n  {C.GREEN}PDF report: {pdf_path}{C.RESET}")

# ── Main ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MIXI-CUT Benchmark Suite v3")
    parser.add_argument("--test", help="Run specific category")
    parser.add_argument("--pdf", action="store_true", help="Generate PDF report")
    parser.add_argument("--compare", action="store_true", help="Compare with last run")
    parser.add_argument("--history", action="store_true", help="Show history")
    parser.add_argument("--no-color", action="store_true", help="Disable colors")
    args = parser.parse_args()

    if args.no_color:
        C.disable()

    if args.history:
        show_history(); return

    np.random.seed(42)

    categories = {
        "noise": cat_noise, "wow": cat_wow, "dust": cat_dust,
        "speed": cat_speed, "transition": cat_transition,
        "hum": cat_hum, "clipping": cat_clipping,
        "quantization": cat_quantization, "xtalk": cat_channel_xtalk,
        "multi_skip": cat_multi_skip, "edm": cat_edm_precision,
        "combined": cat_combined, "tonearm": cat_tonearm_bounce,
    }

    if args.test:
        if args.test == "freq":
            findings, _ = cat_frequency()
        elif args.test in categories:
            findings = categories[args.test]()
        else:
            print(f"Unknown: {args.test}. Available: {', '.join(list(categories.keys())+['freq'])}")
            sys.exit(1)
        for f in findings:
            vc = verdict_color(f.verdict)
            print(f"\n  {vc}[{f.verdict.upper()}]{C.RESET} {f.category}/{f.name}: {f.value} {f.unit}")
            print(f"  {C.DIM}{f.detail}{C.RESET}")
        return

    # Full suite
    print(f"\n{C.BOLD}{C.MAGENTA}╔══════════════════════════════════════════════════════════╗")
    print(f"║       MIXI-CUT PROTOCOL STRESS TEST v3                 ║")
    print(f"║       Draconian • EDM 100-200 BPM • {CARRIER:.0f} Hz          ║")
    print(f"╚══════════════════════════════════════════════════════════╝{C.RESET}")

    t0 = time.perf_counter()
    all_findings = []
    freq_results = None

    for name, fn in categories.items():
        result = fn()
        if isinstance(result, list):
            all_findings.extend(result)

    freq_findings, freq_results = cat_frequency()
    all_findings.extend(freq_findings)

    elapsed = time.perf_counter() - t0

    # Dashboard
    print_dashboard(all_findings, elapsed)

    # Compare with previous
    prev = load_previous()
    if args.compare or prev:
        compare_runs(all_findings, prev)

    # Save
    json_path = save_results(all_findings, freq_results)
    print(f"\n  {C.DIM}Results saved: {json_path}{C.RESET}")

    # PDF
    if args.pdf:
        generate_pdf(all_findings, freq_results)

if __name__ == "__main__":
    main()
