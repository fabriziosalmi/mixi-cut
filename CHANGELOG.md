# Changelog

All notable changes to MIXI-CUT will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

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
