"""Execute a profile source file once or whenever it changes."""

import argparse
import runpy
import sys
import traceback
from pathlib import Path
from time import sleep

from .profile import Profile
from .report import format_profile


def load_profile(path: Path) -> Profile:
    namespace = runpy.run_path(str(path))
    profile = namespace.get("profile")
    if not isinstance(profile, Profile):
        raise ValueError(f"{path} must define 'profile = Profile(...)'")
    return profile


def _revision(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return stat.st_mtime_ns, stat.st_size


def _report(path: Path, *, clear: bool) -> bool:
    if clear:
        print("\033[2J\033[H", end="", flush=True)
    try:
        print(format_profile(load_profile(path)), flush=True)
    except Exception:
        print(f"Failed to evaluate {path}; no current report.", file=sys.stderr, flush=True)
        traceback.print_exc()
        return False
    return True


def watch(path: Path) -> None:
    """Reexecute from scratch after each change; never display stale geometry."""
    revision = _revision(path)
    _report(path, clear=sys.stdout.isatty())
    while True:
        sleep(0.25)
        current = _revision(path)
        if current != revision:
            revision = current
            _report(path, clear=sys.stdout.isatty())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Python file defining a 'profile' variable")
    parser.add_argument(
        "--watch", action="store_true", help="refresh whenever the source file changes"
    )
    args = parser.parse_args()
    path = Path(args.source).resolve()
    if args.watch:
        try:
            watch(path)
        except KeyboardInterrupt:
            return
    elif not _report(path, clear=False):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
