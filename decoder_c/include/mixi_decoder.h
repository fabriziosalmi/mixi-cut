/*
 * MIXI-CUT Decoder — Zero-allocation embeddable C implementation
 *
 * Three-stage pipeline: Bandpass → PLL → Mass-Spring-Damper
 * Designed for: STM32F4, ESP32-S3, Raspberry Pi, or any C99 target
 *
 * Memory: ~200 bytes per decoder instance (stack-allocated)
 * CPU:    <1% on Cortex-M4 @ 168 MHz
 * Latency: 128 samples = 2.9 ms @ 44100 Hz
 *
 * Usage:
 *   mixi_decoder_t dec;
 *   mixi_decoder_init(&dec, 3000.0f, 44100.0f);
 *
 *   mixi_result_t result;
 *   mixi_decoder_process(&dec, left, right, 128, &result);
 *   printf("Speed: %.2f, Lock: %.3f\n", result.speed, result.lock);
 *
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Fabrizio Salmi
 */

#ifndef MIXI_DECODER_H
#define MIXI_DECODER_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ── Configuration defaults ─────────────────────────────────── */

#ifndef MIXI_CARRIER_FREQ
#define MIXI_CARRIER_FREQ   3000.0f
#endif

#ifndef MIXI_SAMPLE_RATE
#define MIXI_SAMPLE_RATE    44100.0f
#endif

#ifndef MIXI_PLL_BW_PCT
#define MIXI_PLL_BW_PCT     0.08f
#endif

#ifndef MIXI_PLL_Q
#define MIXI_PLL_Q          2.5f
#endif

/* ── Data structures ────────────────────────────────────────── */

/** Biquad bandpass filter state */
typedef struct {
    float b0, b2, a1, a2;
    float z1, z2;
} mixi_bandpass_t;

/** Phase-Locked Loop state */
typedef struct {
    float center;
    float sr;
    float phase;
    float freq;
    float integral;
    float lock;
    float kp, ki;
} mixi_pll_t;

/** Mass-spring-damper platter simulator */
typedef struct {
    float speed;
    float prev;
    float inertia;
    float traction;
    int   scratching;
    int   release;
    int   decel_count;
    float prev_input;
} mixi_mass_spring_t;

/** Complete decoder instance */
typedef struct {
    float freq;
    float sr;
    mixi_bandpass_t    bp_l;
    mixi_bandpass_t    bp_r;
    mixi_pll_t         pll;
    mixi_mass_spring_t ms;
    double             pos;   /* cumulative position in carrier cycles */
} mixi_decoder_t;

/** Decoder output for one block */
typedef struct {
    float  speed;      /* playback speed ratio (1.0 = normal) */
    float  lock;       /* PLL lock quality (0.0–1.0) */
    double position;   /* estimated position in seconds */
} mixi_result_t;

/* ── Public API ─────────────────────────────────────────────── */

/**
 * Initialize a decoder instance.
 *
 * @param dec   Pointer to decoder struct (caller-allocated)
 * @param freq  Carrier frequency in Hz (default: 3000)
 * @param sr    Sample rate in Hz (default: 44100)
 */
void mixi_decoder_init(mixi_decoder_t *dec, float freq, float sr);

/**
 * Initialize with default parameters (3000 Hz, 44100 Hz).
 */
void mixi_decoder_init_default(mixi_decoder_t *dec);

/**
 * Process a block of stereo audio samples.
 *
 * @param dec     Decoder instance
 * @param left    Left channel samples (sin component)
 * @param right   Right channel samples (cos component)
 * @param n       Number of samples in each channel
 * @param result  Output: speed, lock, position
 */
void mixi_decoder_process(mixi_decoder_t *dec,
                          const float *left, const float *right,
                          size_t n, mixi_result_t *result);

/**
 * Reset decoder to initial state.
 */
void mixi_decoder_reset(mixi_decoder_t *dec);

/**
 * Get the decoder's current speed estimate without processing.
 */
float mixi_decoder_get_speed(const mixi_decoder_t *dec);

/**
 * Get the decoder's current lock quality without processing.
 */
float mixi_decoder_get_lock(const mixi_decoder_t *dec);

/* ── Component-level API (for testing/advanced use) ─────────── */

void mixi_bandpass_init(mixi_bandpass_t *bp, float freq, float sr, float q);
float mixi_bandpass_tick(mixi_bandpass_t *bp, float x);
void mixi_bandpass_reset(mixi_bandpass_t *bp);

void mixi_pll_init(mixi_pll_t *pll, float freq, float sr, float bw_pct);
void mixi_pll_tick(mixi_pll_t *pll, float l, float r,
                   float *out_speed, float *out_lock);
void mixi_pll_reset(mixi_pll_t *pll);

void mixi_mass_spring_init(mixi_mass_spring_t *ms, float inertia);
float mixi_mass_spring_tick(mixi_mass_spring_t *ms, float v);
void mixi_mass_spring_reset(mixi_mass_spring_t *ms);

#ifdef __cplusplus
}
#endif

#endif /* MIXI_DECODER_H */
