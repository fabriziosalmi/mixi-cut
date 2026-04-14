.PHONY: install dev test test-c test-rust test-all lint bench bench-pdf generate verify clean

# ── Install ──────────────────────────────────────────────────
install:
	pip install -e .

dev:
	pip install -e ".[all]"

# ── Test ─────────────────────────────────────────────────────
test:
	python3 -m pytest tests/ -v --tb=short

test-c:
	cd decoder_c && cc -std=c99 -O2 -Wall -Wextra -Iinclude -o build_test \
		test/test_decoder.c src/mixi_decoder.c -lm && ./build_test && rm -f build_test

test-rust:
	cd decoder_rust && cargo test --release

test-all: test test-c test-rust
	@echo "\n✅ All test suites passed"

coverage:
	python3 -m pytest tests/ -v --cov=mixi_cut --cov-report=term-missing --cov-report=html

# ── Lint ─────────────────────────────────────────────────────
lint:
	ruff check src/ tests/

fix:
	ruff check --fix src/ tests/

# ── Benchmark ────────────────────────────────────────────────
bench:
	python benchmark.py

bench-pdf:
	python benchmark.py --pdf

bench-compare:
	python benchmark.py --compare

# ── Generate & Verify ────────────────────────────────────────
generate:
	mixi-cut generate --preset dj-12inch --output mixi_timecode_v2_15min.wav
	mixi-cut generate --preset test-cut --output mixi_timecode_v2_test60s.wav

verify:
	@if [ -z "$(FILE)" ]; then echo "Usage: make verify FILE=path.wav"; exit 1; fi
	mixi-cut verify $(FILE) --strict

# ── Release ──────────────────────────────────────────────────
release-wavs:
	@for dur in 60 240 480 600 900; do \
		mixi-cut generate --duration $$dur --loop \
			--output mixi_timecode_v2_$${dur}s.wav; \
		echo "✅ Generated $${dur}s WAV"; \
	done
	mixi-cut generate --duration 600 --riaa --loop \
		--output mixi_timecode_v2_600s_riaa.wav
	@echo "\n✅ All release WAVs generated"

build:
	python -m build

# ── Clean ────────────────────────────────────────────────────
clean:
	rm -rf dist/ build/ *.egg-info/ .pytest_cache/ htmlcov/ .coverage
	rm -rf decoder_c/build/ decoder_c/build_test
	rm -rf decoder_rust/target/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -f /tmp/mixi_*.wav
