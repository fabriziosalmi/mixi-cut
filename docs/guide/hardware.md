# MIXI-CUT Hardware Decoder Guide

> Build a standalone MIXI-CUT decoder that converts vinyl timecode to MIDI.

## Architecture

```
[Turntable] → [Phono Preamp] → [ADC] → [MCU] → [USB MIDI]
                                         │
                                    MIXI-CUT C Decoder
                                         │
                              Speed → MIDI CC #1
                              Position → MIDI Note
                              Beat → MIDI Clock
```

## Bill of Materials

| Component | Part | Cost |
|-----------|------|------|
| MCU | STM32F446RE (Cortex-M4, 180 MHz, FPU) | ~8 EUR |
| ADC | PCM1808 (stereo, 96 kHz, 24-bit) | ~5 EUR |
| Phono preamp | Custom or TI OPA2134 | ~3 EUR |
| USB connector | Micro-USB or USB-C | ~0.50 EUR |
| PCB | 2-layer, 50x30mm | ~2 EUR |
| Passives | Capacitors, resistors | ~1 EUR |
| **Total** | | **~20 EUR** |

### Alternative: ESP32-S3

| Component | Part | Cost |
|-----------|------|------|
| MCU | ESP32-S3-WROOM-1 (with I2S ADC) | ~4 EUR |
| ADC | INMP441 MEMS or external I2S ADC | ~3 EUR |
| **Total** | | **~10 EUR** |

## Firmware Overview

The firmware runs the C decoder from `decoder_c/`:

```c
#include "mixi_decoder.h"

// DMA buffer: double-buffered, 128 stereo samples
#define BLOCK_SIZE 128
static float dma_left[BLOCK_SIZE];
static float dma_right[BLOCK_SIZE];

static mixi_decoder_t decoder;

void audio_callback(void) {
    mixi_result_t result;
    mixi_decoder_process(&decoder, dma_left, dma_right,
                         BLOCK_SIZE, &result);

    // Map speed to MIDI CC
    uint8_t cc_speed = (uint8_t)((result.speed + 2.0f) / 4.0f * 127.0f);
    midi_send_cc(1, cc_speed);

    // Map position to MIDI note (one per beat)
    static float last_beat = 0;
    float beat = result.position * (bpm / 60.0f);
    if ((int)beat > (int)last_beat) {
        midi_send_note(60, 127);  // Middle C
    }
    last_beat = beat;
}

int main(void) {
    mixi_decoder_init_default(&decoder);
    adc_start_dma(dma_left, dma_right, BLOCK_SIZE, audio_callback);
    while (1) { __WFI(); }  // Sleep between interrupts
}
```

## MIDI Mapping

| MIDI Message | Parameter | Range |
|-------------|-----------|-------|
| CC #1 (Mod Wheel) | Speed | 0=−2x, 64=0x, 127=+2x |
| CC #2 | Lock quality | 0=unlocked, 127=locked |
| Note C4 (60) | Beat pulse | Velocity=127 |
| Clock | Tempo sync | 24 PPQN from vinyl speed |
| Start/Stop | Play state | When speed crosses ±0.1 |

## Performance Requirements

| Metric | Requirement | Achieved |
|--------|-------------|----------|
| CPU usage | <5% @ 44.1 kHz | <1% (Cortex-M4 @ 180 MHz) |
| Latency | <5 ms | 2.9 ms (128 samples) |
| Memory | <1 KB | ~200 bytes (decoder state) |
| Power | <100 mA @ 3.3V | ~50 mA (typical) |

## PCB Design

> Full KiCad files will be published in the `hardware/` directory.

### Pin assignment (STM32F446RE)

| Pin | Function |
|-----|----------|
| PA4 | I2S WS (word select) |
| PA5 | I2S SCK (bit clock) |
| PA7 | I2S SD (serial data) |
| PA11 | USB D- |
| PA12 | USB D+ |
| PB6 | Status LED |

### Power supply

- USB-powered (5V → 3.3V LDO)
- Separate analog/digital ground planes
- Ferrite bead on USB VBUS

## Testing

1. Generate a test WAV: `mixi-cut generate --preset test-cut --output test.wav`
2. Play through speakers or line output
3. Connect hardware decoder's audio input
4. Monitor MIDI output with a MIDI monitor tool
5. Verify speed tracks 1.000x ±0.01

## Open Hardware

This project will release:
- KiCad schematic and PCB layout
- Gerber files for direct manufacturing
- BOM with LCSC/Mouser part numbers
- 3D-printable enclosure (STL)
