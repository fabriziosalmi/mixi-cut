/*
 * MIXI-CUT Decoder — C implementation
 *
 * Faithful port of the Python reference decoder.
 * Zero heap allocations, C99 compliant, no external dependencies.
 *
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Fabrizio Salmi
 */

#include "mixi_decoder.h"
#include <math.h>
#include <string.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#define TAU (2.0f * (float)M_PI)

/* Clamp float to [lo, hi] */
static inline float clampf(float x, float lo, float hi) {
    if (x < lo) return lo;
    if (x > hi) return hi;
    return x;
}

static inline float fabsf_safe(float x) {
    return x < 0.0f ? -x : x;
}

/* ── Bandpass ─────────────────────────────────────────────── */

void mixi_bandpass_init(mixi_bandpass_t *bp, float freq, float sr, float q) {
    float w0 = TAU * fminf(freq, sr * 0.45f) / sr;
    float alpha = sinf(w0) / (2.0f * fmaxf(q, 0.1f));
    float a0 = 1.0f + alpha;
    bp->b0 = alpha / a0;
    bp->b2 = -alpha / a0;
    bp->a1 = -2.0f * cosf(w0) / a0;
    bp->a2 = (1.0f - alpha) / a0;
    bp->z1 = 0.0f;
    bp->z2 = 0.0f;
}

float mixi_bandpass_tick(mixi_bandpass_t *bp, float x) {
    float y = bp->b0 * x + bp->z1;
    bp->z1 = -bp->a1 * y + bp->z2;
    bp->z2 = bp->b2 * x - bp->a2 * y;
    return y;
}

void mixi_bandpass_reset(mixi_bandpass_t *bp) {
    bp->z1 = 0.0f;
    bp->z2 = 0.0f;
}

/* ── PLL ──────────────────────────────────────────────────── */

void mixi_pll_init(mixi_pll_t *pll, float freq, float sr, float bw_pct) {
    pll->center = freq;
    pll->sr = sr;
    pll->phase = 0.0f;
    pll->freq = freq;
    pll->integral = 0.0f;
    pll->lock = 0.0f;

    float bw = freq * bw_pct;
    float omega = TAU * bw / sr;
    pll->kp = 2.0f * omega;
    pll->ki = omega * omega;
}

void mixi_pll_tick(mixi_pll_t *pll, float l, float r,
                   float *out_speed, float *out_lock) {
    float amp = sqrtf(l * l + r * r);

    /* Amplitude gate: coast on silence */
    if (amp < 0.005f) {
        float a = 1.0f / (pll->sr * 0.05f);
        pll->lock *= (1.0f - a);
        pll->phase += TAU * pll->freq / pll->sr;
        if (pll->phase >= TAU) pll->phase -= TAU;
        *out_speed = pll->freq / pll->center;
        *out_lock = pll->lock;
        return;
    }

    float err = atan2f(l, r) - pll->phase;
    if (err > (float)M_PI) err -= TAU;
    else if (err < -(float)M_PI) err += TAU;

    /* Integral drain when unlocked */
    float drain = (pll->lock < 0.3f) ? 0.98f : 1.0f;
    pll->integral = clampf(
        pll->integral * drain + err * pll->ki,
        -pll->center * 0.5f,
        pll->center * 0.5f
    );
    pll->freq = clampf(
        pll->center + err * pll->kp * pll->sr + pll->integral,
        -pll->center * 2.0f,
        pll->center * 3.0f
    );

    pll->phase += TAU * pll->freq / pll->sr;
    if (pll->phase >= TAU) pll->phase -= TAU;
    else if (pll->phase < 0.0f) pll->phase += TAU;

    float a = 1.0f / (pll->sr * 0.05f);
    pll->lock = pll->lock * (1.0f - a) + cosf(err) * a;

    *out_speed = pll->freq / pll->center;
    *out_lock = clampf(pll->lock, 0.0f, 1.0f);
}

void mixi_pll_reset(mixi_pll_t *pll) {
    pll->phase = 0.0f;
    pll->freq = pll->center;
    pll->integral = 0.0f;
    pll->lock = 0.0f;
}

/* ── Mass-Spring ──────────────────────────────────────────── */

void mixi_mass_spring_init(mixi_mass_spring_t *ms, float inertia) {
    ms->speed = 0.0f;
    ms->prev = 0.0f;
    ms->inertia = inertia;
    ms->traction = 1.0f - inertia;
    ms->scratching = 0;
    ms->release = 0;
    ms->decel_count = 0;
    ms->prev_input = 0.0f;
}

float mixi_mass_spring_tick(mixi_mass_spring_t *ms, float v) {
    ms->prev = ms->speed;
    float d = fabsf_safe(v - ms->speed);

    if (d > 0.3f) {
        /* Scratch: instant snap */
        ms->speed = v;
        ms->scratching = 1;
        ms->release = 0;
    } else if (ms->scratching) {
        ms->speed = ms->speed * 0.3f + v * 0.7f;
        if (d < 0.05f) {
            ms->release++;
            if (ms->release > 20) ms->scratching = 0;
        } else {
            ms->release = 0;
        }
    } else {
        /* Brake detection */
        if (v < ms->prev_input - 0.001f && ms->speed > 0.05f) {
            ms->decel_count++;
        } else {
            ms->decel_count -= 2;
            if (ms->decel_count < 0) ms->decel_count = 0;
        }

        float t;
        if (ms->decel_count > 3) {
            float bf = (float)(ms->decel_count - 3) / 5.0f;
            if (bf > 1.0f) bf = 1.0f;
            t = 0.5f + bf * 0.4f;  /* 0.5 → 0.9 */
        } else if (fabsf_safe(v) < 0.1f && d > 0.05f) {
            t = fminf(ms->traction * 10.0f, 0.5f);
        } else {
            t = ms->traction;
        }
        ms->speed = ms->speed * (1.0f - t) + v * t;
    }

    ms->prev_input = v;

    /* Dead zone */
    if (fabsf_safe(ms->speed) < 0.02f && fabsf_safe(v) < 0.02f) {
        ms->speed = 0.0f;
    }
    return ms->speed;
}

void mixi_mass_spring_reset(mixi_mass_spring_t *ms) {
    ms->speed = 0.0f;
    ms->prev = 0.0f;
    ms->scratching = 0;
    ms->release = 0;
    ms->decel_count = 0;
    ms->prev_input = 0.0f;
}

/* ── Full Decoder ─────────────────────────────────────────── */

void mixi_decoder_init(mixi_decoder_t *dec, float freq, float sr) {
    dec->freq = freq;
    dec->sr = sr;
    mixi_bandpass_init(&dec->bp_l, freq, sr, MIXI_PLL_Q);
    mixi_bandpass_init(&dec->bp_r, freq, sr, MIXI_PLL_Q);
    mixi_pll_init(&dec->pll, freq, sr, MIXI_PLL_BW_PCT);
    mixi_mass_spring_init(&dec->ms, 0.95f);
    dec->pos = 0.0;
}

void mixi_decoder_init_default(mixi_decoder_t *dec) {
    mixi_decoder_init(dec, MIXI_CARRIER_FREQ, MIXI_SAMPLE_RATE);
}

void mixi_decoder_process(mixi_decoder_t *dec,
                          const float *left, const float *right,
                          size_t n, mixi_result_t *result) {
    float ss = 0.0f, sl = 0.0f, se = 0.0f;

    for (size_t i = 0; i < n; i++) {
        float fl = mixi_bandpass_tick(&dec->bp_l, left[i]);
        float fr = mixi_bandpass_tick(&dec->bp_r, right[i]);

        float spd, lk;
        mixi_pll_tick(&dec->pll, fl, fr, &spd, &lk);

        dec->pos += (double)dec->pll.freq / (double)dec->sr;

        ss += spd;
        sl += lk;
        se += fl * fl + fr * fr;
    }

    float avg_s = ss / (float)n;
    float avg_l = sl / (float)n;
    float rms = sqrtf(se / (float)n);

    /* Signal-aware: feed 0 to mass-spring when no signal */
    float speed_in = (rms > 0.01f) ? avg_s : 0.0f;

    result->speed = mixi_mass_spring_tick(&dec->ms, speed_in);
    result->lock = avg_l;
    result->position = dec->pos / (double)dec->freq;
}

void mixi_decoder_reset(mixi_decoder_t *dec) {
    mixi_bandpass_reset(&dec->bp_l);
    mixi_bandpass_reset(&dec->bp_r);
    mixi_pll_reset(&dec->pll);
    mixi_mass_spring_reset(&dec->ms);
    dec->pos = 0.0;
}

float mixi_decoder_get_speed(const mixi_decoder_t *dec) {
    return dec->ms.speed;
}

float mixi_decoder_get_lock(const mixi_decoder_t *dec) {
    return dec->pll.lock;
}
