"""MIXI-CUT CLI — Unified command-line interface.

Usage:
    mixi-cut generate [--duration N] [--preset NAME] [--riaa] [--loop] [--output FILE]
    mixi-cut verify FILE [--strict]
    mixi-cut bench [--test CATEGORY] [--pdf] [--compare] [--history] [--ci]
    mixi-cut decode FILE
    mixi-cut info
"""

import argparse
import sys

from mixi_cut import __protocol_version__, __version__
from mixi_cut.protocol import CARRIER_FREQ, PRESETS, SAMPLE_RATE


def cmd_generate(args):
    """Generate a timecode WAV file."""
    from mixi_cut.generator import generate_timecode, write_wav

    duration = args.duration
    riaa = args.riaa
    loop = args.loop
    output = args.output

    # Apply preset if specified
    if args.preset:
        if args.preset not in PRESETS:
            print(f"Unknown preset: {args.preset}")
            print(f"Available: {', '.join(PRESETS.keys())}")
            sys.exit(1)
        preset = PRESETS[args.preset]
        duration = duration or preset["duration"]
        riaa = riaa or preset["riaa"]
        loop = loop or preset["loop"]
        print(f"Preset: {args.preset} — {preset['description']}")

    if duration is None:
        duration = 900  # 15 min default

    if output is None:
        suffix = f"_{duration}s" if duration != 900 else ""
        riaa_suffix = "_riaa" if riaa else ""
        output = f"mixi_timecode_v2{suffix}{riaa_suffix}.wav"

    left, right, meta = generate_timecode(
        duration=duration,
        freq=args.freq or CARRIER_FREQ,
        sr=SAMPLE_RATE,
        amplitude=0.85,
        apply_riaa=riaa,
        loop=loop,
    )

    write_wav(left, right, output)


def cmd_verify(args):
    """Verify a timecode WAV file."""
    from mixi_cut.verifier import verify_timecode

    passed, results = verify_timecode(args.file, strict=args.strict)
    sys.exit(0 if passed else 1)


def cmd_bench(args):
    """Run benchmark suite."""
    # Import the benchmark module from the project root
    import importlib.util
    import os

    # Try to find benchmark.py in common locations
    for path in ["benchmark.py", "benchmarks/suite.py"]:
        full_path = os.path.join(os.getcwd(), path)
        if os.path.exists(full_path):
            spec = importlib.util.spec_from_file_location("benchmark", full_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            # Build argv for the benchmark
            bench_args = []
            if args.test:
                bench_args.extend(["--test", args.test])
            if args.pdf:
                bench_args.append("--pdf")
            if args.compare:
                bench_args.append("--compare")
            if args.history:
                bench_args.append("--history")
            if args.ci:
                bench_args.append("--no-color")

            sys.argv = ["benchmark"] + bench_args
            mod.main()
            return

    print("benchmark.py not found. Run from the project root directory.")
    sys.exit(1)


def cmd_decode(args):
    """Decode a timecode WAV file (reference decoder)."""
    import soundfile as sf

    from mixi_cut.decoder import Decoder

    data, sr = sf.read(args.file)
    if data.ndim != 2:
        print("Error: expected stereo WAV")
        sys.exit(1)

    left = data[:, 0]
    right = data[:, 1]
    block = 128
    dec = Decoder(sr=sr)

    print(f"Decoding: {args.file}")
    print(f"  Duration: {len(left)/sr:.1f}s")
    print(f"  Sample rate: {sr} Hz")
    print()

    positions = []
    for i in range(0, len(left), block):
        j = min(i + block, len(left))
        speed, lock, pos = dec.process(left[i:j], right[i:j])
        t = (i + block // 2) / sr
        if i % (sr * 1) < block:  # print every ~1 second
            lock_bar = "█" * int(lock * 20) + "░" * (20 - int(lock * 20))
            print(f"  t={t:6.1f}s  speed={speed:+.3f}x  lock=[{lock_bar}] {lock:.3f}  pos={pos:.2f}s")
        positions.append((t, speed, lock, pos))

    print(f"\n  Decoded {len(positions)} blocks.")


def cmd_info(args):
    """Show version and protocol information."""
    print(f"MIXI-CUT v{__version__}")
    print(f"Protocol: v{__protocol_version__}")
    print(f"Carrier: {CARRIER_FREQ} Hz stereo quadrature")
    print(f"Sample rate: {SAMPLE_RATE} Hz")
    print("\nPresets:")
    for name, p in PRESETS.items():
        print(f"  {name:20s} {p['description']}")


def main():
    parser = argparse.ArgumentParser(
        prog="mixi-cut",
        description="MIXI-CUT — Open-source DVS timecode generator for vinyl lathe cutting",
    )
    parser.add_argument("--version", action="version", version=f"mixi-cut {__version__}")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # generate
    gen = subparsers.add_parser("generate", help="Generate timecode WAV file",
                                aliases=["gen", "g"])
    gen.add_argument("--duration", type=int, help="Signal duration in seconds")
    gen.add_argument("--preset", choices=list(PRESETS.keys()), help="Use a preset configuration")
    gen.add_argument("--freq", type=int, help=f"Carrier frequency (default: {CARRIER_FREQ})")
    gen.add_argument("--output", "-o", type=str, help="Output WAV filename")
    gen.add_argument("--riaa", action="store_true", help="RIAA pre-emphasis (PHONO input)")
    gen.add_argument("--loop", action="store_true", help="Phase-continuous locked groove")
    gen.set_defaults(func=cmd_generate)

    # verify
    ver = subparsers.add_parser("verify", help="Verify timecode WAV file",
                                aliases=["v"])
    ver.add_argument("file", help="WAV file to verify")
    ver.add_argument("--strict", action="store_true", help="Fail on any warning")
    ver.set_defaults(func=cmd_verify)

    # bench
    bench = subparsers.add_parser("bench", help="Run benchmark suite",
                                  aliases=["b"])
    bench.add_argument("--test", "--category", dest="test", help="Run specific category")
    bench.add_argument("--pdf", action="store_true", help="Generate PDF report")
    bench.add_argument("--compare", action="store_true", help="Compare with last run")
    bench.add_argument("--history", action="store_true", help="Show history")
    bench.add_argument("--ci", action="store_true", help="CI mode (no color, JSON output)")
    bench.set_defaults(func=cmd_bench)

    # decode
    dec = subparsers.add_parser("decode", help="Decode timecode WAV (reference decoder)",
                                aliases=["d"])
    dec.add_argument("file", help="WAV file to decode")
    dec.set_defaults(func=cmd_decode)

    # info
    info = subparsers.add_parser("info", help="Show version and protocol info",
                                 aliases=["i"])
    info.set_defaults(func=cmd_info)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
