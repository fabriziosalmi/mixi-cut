# Changelog

All notable changes to MIXI-CUT will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.3.2] - 2026-04-23

### Fixed
- **Multi-rate encoder off-grid**: inner-groove frame interval (>300s) was
  `cycles_per_frame // 2 = 2125`, not a multiple of the 50-cycle bit
  lattice, so inner-groove bits landed 25 cycles out of phase with the
  outer-groove grid. Now snapped to the lattice (2100 cycles). Guarantees
  every bit sits on the same 50-cycle grid regardless of which frame
  wrote it — prerequisite for any future audio-side frame decoder.
- **Version strings synchronized across packages**: `src/mixi_cut`,
  `pyproject.toml`, `decoder_rust/Cargo.toml` all at 0.3.2; the Rust
  crate was stuck at 0.2.0.
- **Hardcoded "v0.3.0" removed from generator**: `generator.py` now
  prints the `__version__` value. Tests read the version from the
  package instead of asserting a literal.

### Documentation
- `docs/DECODER_GUIDE.md` and `docs/guide/decoder.md` Position Decoding
  section rewritten: now documents the v0.3 85-bit frame (Barker-13 +
  24-bit position + CRC-16 + RS(4)) instead of the stale v0.2 56-bit
  layout. Added an explicit status note that the current reference
  decoders expose `position = ∫freq/freq` (a cumulative timer), not
  audio-side frame acquisition.
- `gf256.crc16` docstring no longer claims "CRC-16/ARC (USB)" — the
  MIXI-CUT configuration (poly=0x8005, init=0xFFFF, non-reflected)
  shares ARC's polynomial but is a project-specific CRC, not a named
  standard variant. Interop goal is encoder↔decoder only.
- `docs/.../decoder.md` brake-detection section flagged as describing
  the v0.2 linear ramp still used by the C and Rust ports; v0.3.1
  3-regime state machine is Python-only.

### Known limitations (unchanged, documented more honestly)
- C and Rust decoders remain at v0.2 feature level: single PLL (no
  dual-PLL handoff), linear brake ramp (no 3-regime state machine).
- No shipping decoder performs Barker/CRC/RS frame acquisition from
  audio; position is always the cumulative PLL frequency integral.
  Bit-level round-trip is covered by `decode_position_bits` and its
  tests. Audio-side frame decoding is a future (minor-release) item.

## [0.3.1] - 2026-04-15

### Fixed
- **Vinyl brake settle**: 488 ms --> <100 ms via 3-regime adaptive brake (DECEL/SNAP/RELEASE)
- **Speed range**: 2.0x --> 3.0x via dual-PLL with adaptive bandwidth handoff

### Added
- **Dual-PLL decoder**: wide (20%) for acquisition + high-speed, narrow (8%) for precision
- **3-regime brake state machine**: exponential traction, near-zero snap bypass, gradual release
- **VitePress documentation**: 20-page Apple-style docs site for GitHub Pages
- **GitHub Pages deploy**: `.github/workflows/docs.yml` with VitePress build
- **Coverage tests**: 10 new coverage tests (generator, verifier, decoder edge cases)
- **CLI integration tests**: 11 tests covering all 5 subcommands
- **Brake tests**: 4 tests for regime transitions, snap-to-zero, settle timing
- **Speed tests**: 6 tests for 2x/3x/-2x tracking, dual-PLL handoff/fallback

### Changed
- Protocol constants: 6 new PLL constants, 3 new brake constants
- Test count: 97 --> 133 (+36 tests)
- Core coverage: 78% --> 82% (99.7% excluding CLI)

## [0.3.0] - 2026-04-15

### Added
- **CRC-16 fast-reject**: 16-bit CRC parallel to Reed-Solomon for O(1) frame rejection
- **Barker-13 sync word**: 13-bit autocorrelation preamble for frame acquisition (<500ms lock)
- **Multi-rate encoding**: 2x frame density on inner groove (>300s) for better SNR
- **Velocity subcarrier**: 500 Hz AM-modulated channel for instantaneous speed (bypasses mass-spring latency)
- **DJ Guide**: complete setup, techniques, and troubleshooting guide (`docs/DJ_GUIDE.md`)
- **CRC-16 test suite**: 7 new tests for CRC compute/check/roundtrip
- **Sync word tests**: Barker-13 autocorrelation, sequence, frame prefix
- **Velocity subcarrier tests**: modulation at various speeds, 500 Hz spectral check
- **Multi-rate test**: inner groove density verification
- **v0.2 backward compatibility**: decoder accepts both 56-bit (v0.2) and 85-bit (v0.3) frames

### Changed
- Protocol version: 0.2.0 → 0.3.0
- Frame format: 56 bits → 85 bits (13 sync + 24 pos + 16 CRC + 32 RS)
- Frame period: 0.933s → 1.417s (normal) / 0.708s (inner groove dense mode)
- Version strings normalized: all "v3" references → "v0.2" (now v0.3)

### Fixed
- 28 ruff lint errors resolved (unused imports, variable names, formatting)
- CLI `--category` alias for `--test` in bench command
- `.gitignore` updated: BENCHMARK_REPORT.pdf, Cargo.lock

## [0.2.0] - 2026-04-14

### Added
- **Python package**: installable via `pip install mixi-cut`
- **Unified CLI**: `mixi-cut generate|verify|bench|decode|info`
- **Preset system**: `--preset dj-12inch|dj-7inch|test-cut|phono|locked-groove`
- **Reference decoder**: standalone Python decoder module (`mixi_cut.decoder`)
- **C decoder**: zero-alloc, C99, embeddable (~200 bytes per instance)
- **Rust decoder**: standalone crate with wasm feature flag (`mixi-decoder`)
- **JavaScript decoder**: pure JS port for Web Audio API
- **Web demo**: drag-and-drop WAV decoder (`docs/demo/`)
- **Position decoding**: `decode_position_bits()` for roundtrip verification
- **RS validation**: `rs_check()` for syndrome-based codeword validation
- **Test suite**: 99 tests across Python (77), C (13), Rust (9)
- **CI/CD**: GitHub Actions with Python 3.10-3.13 + C + Rust jobs
- **Release pipeline**: automated WAV generation + PyPI publish
- **Documentation**: Cutting Guide, Decoder Guide, Hardware Guide, Comparison
- **Community**: CODE_OF_CONDUCT, SECURITY, issue/PR templates
- **Makefile**: `make test|test-c|test-rust|test-all|bench|release-wavs`
- **Centralized protocol constants**: `mixi_cut.protocol` — single source of truth

### Fixed
- **Vinyl brake settle time**: 488ms → 476ms (24ms tracking lag on 500ms ramp)
- **MassSpring brake detection**: aggressive traction ramp 0.5→0.9 with decel counter
- **Tonearm findings persistence**: MC results now included in benchmark JSON output

### Changed
- Protocol version: 0.1.0 → 0.2.0
- Package structure: monolithic scripts → `src/mixi_cut/` package
- Backward compatible: `python generate.py` still works

## [0.1.0] - 2026-04-09

### Added
- Initial release
- 3 kHz stereo quadrature carrier
- 24-bit position encoding + Reed-Solomon RS(4)
- RIAA pre-emphasis (IIR, O(1) memory)
- Loop mode (phase-continuous locked groove)
- Benchmark suite with 14 categories + 1000 MC tonearm bounce
- PDF report generation
- v3 DJ resilience: PLL integral drain, adaptive stop, vinyl brake detection, dead zone
