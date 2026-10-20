"""R67 isolated simulation-only experiment. Example: python scripts/r67_network_spike.py."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from drawtemp.sdk.r67_network_feasibility import run_spike  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="R67 experimental deterministic LAN impairment simulation")
    parser.add_argument("--seed", type=int, default=67)
    parser.add_argument("--ticks", type=int, default=240)
    parser.add_argument("--loss-percent", type=int, default=8)
    parser.add_argument("--latency-ticks", type=int, default=2)
    parser.add_argument("--jitter-ticks", type=int, default=2)
    parser.add_argument("--input-lead", type=int, default=5)
    parser.add_argument("--snapshot-interval", type=int, default=4)
    args = parser.parse_args()
    report = run_spike(**vars(args).copy())
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
