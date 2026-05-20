from __future__ import annotations

import argparse
import subprocess
import sys


def run(command: list[str]) -> None:
    print(f"\n$ {' '.join(command)}", flush=True)
    subprocess.run(command, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run both dataset smoke tests.")
    parser.add_argument("--aihub-annotation-path", default="")
    parser.add_argument("--cmapss-subset", default="FD001")
    args = parser.parse_args()

    run([sys.executable, "backend/scripts/smoke_cmapss.py", "--subset", args.cmapss_subset])
    aihub_command = [sys.executable, "backend/scripts/smoke_aihub.py"]
    if args.aihub_annotation_path:
        aihub_command.extend(["--annotation-path", args.aihub_annotation_path])
    run(aihub_command)


if __name__ == "__main__":
    main()
