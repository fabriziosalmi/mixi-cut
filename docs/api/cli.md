# CLI Commands

## `mixi-cut generate`

Generate a timecode WAV file.

```bash
mixi-cut generate [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--preset` | --- | Use a named preset |
| `--duration` | 900 | Signal duration in seconds |
| `--output`, `-o` | `mixi_timecode_v2.wav` | Output file path |
| `--loop` | false | Phase-continuous loop mode |
| `--riaa` | false | Apply RIAA pre-emphasis |

## `mixi-cut verify`

Verify a timecode WAV before cutting.

```bash
mixi-cut verify FILE [--strict]
```

Runs 6 checks: DC offset, quadrature phase, carrier frequency, position encoding, channel balance, and lead-in silence.

## `mixi-cut decode`

Decode a timecode WAV using the reference decoder.

```bash
mixi-cut decode FILE
```

Outputs speed, lock quality, and position for each block.

## `mixi-cut bench`

Run the benchmark suite.

```bash
mixi-cut bench [--test CATEGORY] [--pdf] [--compare]
```

14 categories with 1000 Monte Carlo simulations each.

## `mixi-cut info`

Show version and protocol information.

```bash
mixi-cut info
```
