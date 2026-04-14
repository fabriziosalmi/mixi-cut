/*
 * MIXI-CUT Decoder — Test suite
 * Verifies correctness of the C decoder against known signals.
 *
 * SPDX-License-Identifier: MIT
 */

#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include "mixi_decoder.h"

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#define TAU (2.0f * (float)M_PI)
#define SR 44100.0f
#define CARRIER 3000.0f
#define BLOCK 128
#define ASSERT(cond, msg) do { \
    tests_total++; \
    if (!(cond)) { \
        printf("  FAIL: %s (line %d)\n", msg, __LINE__); \
        tests_failed++; \
    } else { \
        tests_passed++; \
    } \
} while(0)

static int tests_total = 0;
static int tests_passed = 0;
static int tests_failed = 0;

/* Generate clean quadrature signal */
static void gen_quadrature(float *left, float *right, int n,
                           float freq, float sr, float amp, float speed) {
    for (int i = 0; i < n; i++) {
        float t = (float)i / sr;
        float phase = TAU * freq * speed * t;
        left[i] = sinf(phase) * amp;
        right[i] = cosf(phase) * amp;
    }
}

/* ── Test: Bandpass passes carrier ───────────────────────── */
static void test_bandpass_passes_carrier(void) {
    printf("  bandpass_passes_carrier...\n");
    mixi_bandpass_t bp;
    mixi_bandpass_init(&bp, CARRIER, SR, 2.5f);

    int n = (int)(0.1f * SR);
    float rms_sum = 0.0f;
    for (int i = 0; i < n; i++) {
        float t = (float)i / SR;
        float x = sinf(TAU * CARRIER * t) * 0.85f;
        float y = mixi_bandpass_tick(&bp, x);
        if (i > n / 2) rms_sum += y * y;
    }
    float rms = sqrtf(rms_sum / (float)(n / 2));
    ASSERT(rms > 0.1f, "Carrier should pass through bandpass");
}

/* ── Test: Bandpass rejects DC ───────────────────────────── */
static void test_bandpass_rejects_dc(void) {
    printf("  bandpass_rejects_dc...\n");
    mixi_bandpass_t bp;
    mixi_bandpass_init(&bp, CARRIER, SR, 2.5f);

    int n = (int)SR;
    float rms_sum = 0.0f;
    for (int i = 0; i < n; i++) {
        float y = mixi_bandpass_tick(&bp, 0.85f);
        if (i > n / 2) rms_sum += y * y;
    }
    float rms = sqrtf(rms_sum / (float)(n / 2));
    ASSERT(rms < 0.01f, "DC should be rejected");
}

/* ── Test: PLL locks to carrier ─────────────────────────── */
static void test_pll_locks(void) {
    printf("  pll_locks...\n");
    mixi_pll_t pll;
    mixi_pll_init(&pll, CARRIER, SR, 0.08f);

    int n = (int)(0.5f * SR);
    float last_lock = 0.0f;
    for (int i = 0; i < n; i++) {
        float t = (float)i / SR;
        float l = sinf(TAU * CARRIER * t) * 0.85f;
        float r = cosf(TAU * CARRIER * t) * 0.85f;
        float spd, lk;
        mixi_pll_tick(&pll, l, r, &spd, &lk);
        last_lock = lk;
    }
    ASSERT(last_lock > 0.8f, "PLL should lock to clean carrier");
}

/* ── Test: PLL speed tracking ───────────────────────────── */
static void test_pll_speed(void) {
    printf("  pll_speed...\n");
    mixi_pll_t pll;
    mixi_pll_init(&pll, CARRIER, SR, 0.08f);

    int n = (int)(0.5f * SR);
    float speed_sum = 0.0f;
    int count = 0;
    for (int i = 0; i < n; i++) {
        float t = (float)i / SR;
        float l = sinf(TAU * CARRIER * t) * 0.85f;
        float r = cosf(TAU * CARRIER * t) * 0.85f;
        float spd, lk;
        mixi_pll_tick(&pll, l, r, &spd, &lk);
        if (i > 3 * n / 4) { speed_sum += spd; count++; }
    }
    float avg = speed_sum / (float)count;
    ASSERT(fabsf(avg - 1.0f) < 0.02f, "PLL speed should be ~1.0");
}

/* ── Test: Mass-spring smooth tracking ──────────────────── */
static void test_mass_spring_tracking(void) {
    printf("  mass_spring_tracking...\n");
    mixi_mass_spring_t ms;
    mixi_mass_spring_init(&ms, 0.95f);
    for (int i = 0; i < 500; i++) {
        mixi_mass_spring_tick(&ms, 1.0f);
    }
    ASSERT(fabsf(ms.speed - 1.0f) < 0.05f, "Should track constant speed");
}

/* ── Test: Mass-spring dead zone ────────────────────────── */
static void test_mass_spring_dead_zone(void) {
    printf("  mass_spring_dead_zone...\n");
    mixi_mass_spring_t ms;
    mixi_mass_spring_init(&ms, 0.95f);
    mixi_mass_spring_tick(&ms, 0.01f);
    mixi_mass_spring_tick(&ms, 0.01f);
    ASSERT(ms.speed == 0.0f, "Low speed should snap to zero");
}

/* ── Test: Full decoder on clean signal ─────────────────── */
static void test_decoder_clean(void) {
    printf("  decoder_clean...\n");
    mixi_decoder_t dec;
    mixi_decoder_init_default(&dec);

    int dur = (int)(2.0f * SR);
    float *left = (float *)malloc(dur * sizeof(float));
    float *right = (float *)malloc(dur * sizeof(float));
    gen_quadrature(left, right, dur, CARRIER, SR, 0.85f, 1.0f);

    float speed_sum = 0.0f, lock_sum = 0.0f;
    int blocks = 0, total_blocks = 0;
    for (int i = 0; i < dur; i += BLOCK) {
        int n = (i + BLOCK <= dur) ? BLOCK : (dur - i);
        mixi_result_t res;
        mixi_decoder_process(&dec, left + i, right + i, n, &res);
        total_blocks++;
        if (total_blocks > (dur / BLOCK) * 3 / 4) {
            speed_sum += res.speed;
            lock_sum += res.lock;
            blocks++;
        }
    }

    float avg_speed = speed_sum / (float)blocks;
    float avg_lock = lock_sum / (float)blocks;

    ASSERT(fabsf(avg_speed - 1.0f) < 0.05f, "Decoder speed ~1.0 on clean signal");
    ASSERT(avg_lock > 0.7f, "Decoder lock > 0.7 on clean signal");

    free(left);
    free(right);
}

/* ── Test: Decoder reports zero on silence ──────────────── */
static void test_decoder_silence(void) {
    printf("  decoder_silence...\n");
    mixi_decoder_t dec;
    mixi_decoder_init_default(&dec);

    /* Feed signal first */
    int sig_n = (int)(0.5f * SR);
    float *left = (float *)calloc(sig_n, sizeof(float));
    float *right = (float *)calloc(sig_n, sizeof(float));
    gen_quadrature(left, right, sig_n, CARRIER, SR, 0.85f, 1.0f);
    for (int i = 0; i < sig_n; i += BLOCK) {
        int n = (i + BLOCK <= sig_n) ? BLOCK : (sig_n - i);
        mixi_result_t res;
        mixi_decoder_process(&dec, left + i, right + i, n, &res);
    }
    free(left);
    free(right);

    /* Now feed silence */
    int sil_n = (int)(0.5f * SR);
    float *sil = (float *)calloc(sil_n, sizeof(float));
    mixi_result_t last_res;
    for (int i = 0; i < sil_n; i += BLOCK) {
        int n = (i + BLOCK <= sil_n) ? BLOCK : (sil_n - i);
        mixi_decoder_process(&dec, sil, sil, n, &last_res);
    }
    free(sil);

    ASSERT(fabsf(last_res.speed) < 0.1f, "Speed should decay on silence");
}

/* ── Test: Position increases ───────────────────────────── */
static void test_position_increases(void) {
    printf("  position_increases...\n");
    mixi_decoder_t dec;
    mixi_decoder_init_default(&dec);

    int n = (int)(1.0f * SR);
    float *left = (float *)malloc(n * sizeof(float));
    float *right = (float *)malloc(n * sizeof(float));
    gen_quadrature(left, right, n, CARRIER, SR, 0.85f, 1.0f);

    double first_pos = 0.0, last_pos = 0.0;
    int first = 1;
    for (int i = 0; i < n; i += BLOCK) {
        int blk = (i + BLOCK <= n) ? BLOCK : (n - i);
        mixi_result_t res;
        mixi_decoder_process(&dec, left + i, right + i, blk, &res);
        if (first) { first_pos = res.position; first = 0; }
        last_pos = res.position;
    }

    ASSERT(last_pos > first_pos, "Position should increase");
    free(left);
    free(right);
}

/* ── Test: Reset clears state ───────────────────────────── */
static void test_reset(void) {
    printf("  reset...\n");
    mixi_decoder_t dec;
    mixi_decoder_init_default(&dec);

    int n = (int)(0.5f * SR);
    float *left = (float *)malloc(n * sizeof(float));
    float *right = (float *)malloc(n * sizeof(float));
    gen_quadrature(left, right, n, CARRIER, SR, 0.85f, 1.0f);
    mixi_result_t res;
    mixi_decoder_process(&dec, left, right, n, &res);

    mixi_decoder_reset(&dec);
    ASSERT(dec.pos == 0.0, "Position should be zero after reset");
    ASSERT(dec.pll.lock == 0.0f, "Lock should be zero after reset");
    ASSERT(dec.ms.speed == 0.0f, "Speed should be zero after reset");

    free(left);
    free(right);
}

/* ── Main ─────────────────────────────────────────────────── */
int main(void) {
    printf("MIXI-CUT C Decoder Tests\n");
    printf("========================\n\n");

    test_bandpass_passes_carrier();
    test_bandpass_rejects_dc();
    test_pll_locks();
    test_pll_speed();
    test_mass_spring_tracking();
    test_mass_spring_dead_zone();
    test_decoder_clean();
    test_decoder_silence();
    test_position_increases();
    test_reset();

    printf("\n========================\n");
    printf("Results: %d/%d passed", tests_passed, tests_total);
    if (tests_failed > 0) {
        printf(" (%d FAILED)", tests_failed);
    }
    printf("\n");

    return tests_failed > 0 ? 1 : 0;
}
