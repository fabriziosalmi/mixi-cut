# MIXI-CUT DJ Guide

> How to use MIXI-CUT timecode vinyl for DJing.

## What You Need

| Item | Details | Cost |
|------|---------|------|
| MIXI-CUT vinyl | Lathe-cut timecode disc (7" or 12") | ~8 EUR |
| DJ turntable | Any turntable with 33⅓ RPM | varies |
| Audio interface | Stereo line input (or phono + preamp) | varies |
| DJ software | Mixxx (free) or MIXI | free |

## Getting Started

### Step 1: Get the vinyl

**Option A: Cut your own**
```bash
pip install mixi-cut
mixi-cut generate --preset dj-12inch --output side_a.wav
# Send side_a.wav to a lathe cutting service
```

**Option B: Download a pre-made WAV**
Download from [Releases](https://github.com/fabriziosalmi/mixi-cut/releases) and send to a lathe cutting service.

### Step 2: Connect your turntable

```
Turntable → [LINE output] → Audio Interface → Computer → DJ Software
```

> **Important**: Use **LINE** input unless you generated with `--riaa`. If your turntable only has PHONO output, either use a phono preamp or generate with `mixi-cut generate --preset phono`.

### Step 3: Configure your DJ software

In your MIXI-CUT–compatible DJ software:
1. Set the input to MIXI-CUT timecode
2. Select the audio input from your interface
3. Start the turntable

The software should show:
- **Speed**: 1.000x (±0.005)
- **Lock**: green bar (>0.9)
- **Position**: increasing in seconds

## Playing Music

Once the timecode is locked:
1. Load a track in the software
2. The track plays in sync with the vinyl
3. Whatever you do to the vinyl (scratch, stop, pitch) affects the track

## DJ Techniques

### Scratching
The decoder responds within **0.33 ms** (one carrier cycle). Forward and backward scratches are detected instantly via the stereo quadrature encoding.

### Beat matching
1. Start both tracks
2. Use the pitch fader on the turntable
3. The decoder tracks pitch changes of ±8% smoothly
4. Fine-tune by ear as usual

### Cueing
1. Move the needle to any position on the vinyl
2. The decoder reads the position within 1 second
3. The track jumps to the corresponding position

### Vinyl brake
When you press the stop button:
- The decoder tracks the deceleration
- The track slows down and stops naturally
- Settle time: <500 ms

### Backspin
Pull the record backward:
- Speed goes negative immediately
- The track plays in reverse
- Release and the track resumes forward

## Troubleshooting

| Problem | Possible Cause | Solution |
|---------|---------------|----------|
| No lock (speed=0) | Wrong input mode | Check LINE vs PHONO |
| Speed shows ~0.978 instead of 1.0 | Turntable at 45 RPM | Switch to 33⅓ |
| Intermittent dropouts | Dirty stylus or vinyl | Clean both |
| Only works in one direction | Cartridge wired backwards | Check L/R channels |
| Lock but no sound | Software routing issue | Check DJ software output |
| Speed jitters | Rumble or vibration | Isolate turntable from subs |

## FAQ

### Can I scratch like with Serato?
Yes. The decoder latency is 0.33 ms — faster than Serato's estimated ~1 ms. The stereo quadrature encoding gives instant direction detection.

### How long does the vinyl last?
Lathe-cut vinyl typically lasts 100-200 plays with good stylus hygiene. This is less than pressed vinyl but the cost (~8 EUR) makes replacement easy.

### Can I use any turntable?
Yes. Any turntable that plays at 33⅓ RPM works. A Technics SL-1200 is ideal but not required.

### Can I use my Serato/Traktor interface?
Yes, as long as the audio interface provides stereo line input. The interface hardware is universal — only the software decoding differs.

### What about PHONO vs LINE?
- **LINE input**: Use the standard WAV (no `--riaa`). This is the recommended setup.
- **PHONO input**: Use `mixi-cut generate --preset phono` which adds RIAA pre-emphasis. The turntable's phono preamp will flatten the signal back.

### Why 3 kHz carrier?
It's above most music content and rumble, while being well below the 15 kHz high-frequency limit of lathe-cut vinyl. This gives excellent noise rejection without sacrificing resolution.
