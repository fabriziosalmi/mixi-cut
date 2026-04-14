"""CLI integration tests — exercise main entry points via subprocess.

Tests the full CLI pipeline to cover cli.py (previously 0%).
"""

import os
import subprocess
import sys


def run_cli(*args):
    """Run mixi-cut CLI and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, "-m", "mixi_cut.cli"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return result.returncode, result.stdout, result.stderr


class TestCLIGenerate:
    """CLI generate subcommand."""

    def test_generate_default(self, tmp_path):
        output = str(tmp_path / "test.wav")
        rc, out, err = run_cli("generate", "--duration", "3", "-o", output)
        assert rc == 0
        assert os.path.exists(output)
        assert "MIXI-CUT v0.3.0" in out

    def test_generate_preset(self, tmp_path):
        output = str(tmp_path / "preset.wav")
        rc, out, err = run_cli("generate", "--preset", "test-cut", "-o", output)
        assert rc == 0
        assert os.path.exists(output)
        assert "test-cut" in out

    def test_generate_loop(self, tmp_path):
        output = str(tmp_path / "loop.wav")
        rc, out, err = run_cli("generate", "--duration", "2", "--loop", "-o", output)
        assert rc == 0
        assert "Loop mode:" in out or "phase-continuous" in out

    def test_generate_riaa(self, tmp_path):
        output = str(tmp_path / "riaa.wav")
        rc, out, err = run_cli("generate", "--duration", "2", "--riaa", "-o", output)
        assert rc == 0
        assert "RIAA" in out


class TestCLIVerify:
    """CLI verify subcommand."""

    def test_verify_valid(self, tmp_path):
        wav = str(tmp_path / "v.wav")
        run_cli("generate", "--duration", "3", "-o", wav)
        rc, out, err = run_cli("verify", wav)
        assert rc == 0
        assert "Score:" in out

    def test_verify_strict(self, tmp_path):
        wav = str(tmp_path / "vs.wav")
        run_cli("generate", "--duration", "3", "-o", wav)
        rc, out, err = run_cli("verify", wav, "--strict")
        assert rc == 0
        assert "READY TO CUT" in out


class TestCLIDecode:
    """CLI decode subcommand."""

    def test_decode_runs(self, tmp_path):
        wav = str(tmp_path / "d.wav")
        run_cli("generate", "--duration", "3", "-o", wav)
        rc, out, err = run_cli("decode", wav)
        assert rc == 0
        assert "speed=" in out


class TestCLIInfo:
    """CLI info subcommand."""

    def test_info_shows_version(self):
        rc, out, err = run_cli("info")
        assert rc == 0
        assert "0.3.0" in out
        assert "3000" in out  # carrier freq


class TestCLIBench:
    """CLI bench subcommand."""

    def test_bench_help(self):
        rc, out, err = run_cli("bench", "--help")
        assert rc == 0
        assert "--test" in out


class TestCLIHelp:
    """CLI help and error handling."""

    def test_no_args_shows_usage(self):
        rc, out, err = run_cli()
        # No subcommand → exits with 1 and prints usage
        assert rc in (1, 2)
        assert "usage" in out.lower() or "usage" in err.lower()

    def test_help_flag(self):
        rc, out, err = run_cli("--help")
        assert rc == 0
        assert "mixi-cut" in out.lower() or "usage" in out.lower()
