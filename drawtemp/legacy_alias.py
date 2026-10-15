"""Deprecated console-script alias: keep the historical engine CLI available."""
import sys


def main(argv=None):
    print("Deprecated: the 'sporebound' command is a compatibility alias; "
          "use 'drawtemp' instead.", file=sys.stderr)
    from sporebound.__main__ import main as run
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
