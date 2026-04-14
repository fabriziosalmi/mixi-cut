# Contributing to MIXI-CUT

Thank you for your interest in MIXI-CUT! This project aims to create the best open-source DVS timecode protocol for vinyl lathe cutting.

## How to Contribute

### Reporting Bugs

- Open an issue with a clear description
- Include your Python version, OS, and `mixi-cut --version`
- If it's a signal/audio issue, include the WAV file or benchmark output

### Feature Requests

- Open an issue describing the feature
- Explain the use case (DJ workflow, lathe cutting, hardware integration)
- Reference relevant sections of `PROTOCOL.md` if applicable

### Code Contributions

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Install dev dependencies: `make dev`
4. Make your changes
5. Run tests: `make test`
6. Run lint: `make lint`
7. Run benchmark (if protocol-affecting): `make bench`
8. Submit a PR with a clear description

### Code Style

- Python 3.10+
- Ruff for linting
- Type hints for all public functions
- Docstrings for all modules, classes, and public functions
- Constants in `protocol.py` — never hardcode protocol values

### Protocol Changes

Changes to the protocol (carrier frequency, frame format, encoding scheme) require:

1. Discussion in an issue first
2. Update to `PROTOCOL.md`
3. Full benchmark suite passing
4. No regression in benchmark health score

### Testing

- All new code must have tests
- Target: ≥90% coverage
- Run `make test-all` to check all 3 languages (Python + C + Rust)
- Run `make coverage` for Python coverage report

### What We Need Help With

- **Hardware testing**: Real lathe-cut vinyl testing with different turntables and styli
- **DJ software integration**: Mixxx plugin, VirtualDJ plugin
- **Embedded systems**: STM32/ESP32 decoder firmware
- **Documentation**: Cutting guides, decoder guides, translations
- **New decoder languages**: Go, Swift, or other languages

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
