from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import requests

DATASET_KEY = "238"
BASE_URL = "https://api.aihub.or.kr"
INFO_URL = f"{BASE_URL}/info/{DATASET_KEY}.do"
DOWNLOAD_URL = f"{BASE_URL}/down/0.6/{DATASET_KEY}.do"

KNOWN_FILES = {
    "train_current": {"filekey": "44889", "size": "21 GB", "name": "Training current.zip"},
    "train_vibration": {"filekey": "44890", "size": "78 GB", "name": "Training vibration.zip"},
    "valid_current": {"filekey": "44891", "size": "3 GB", "name": "Validation current.zip"},
    "valid_vibration": {"filekey": "44815", "size": "10 GB", "name": "Validation vibration.zip"},
}


def main() -> None:
    parser = argparse.ArgumentParser(description="AI-Hub dataset 238 helper for Windows/Python.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="Fetch and save dataset 238 file tree.")
    list_parser.add_argument("--out", default="data/aihub238/file_tree_238.txt")

    download_parser = subparsers.add_parser("download", help="Download selected filekey(s).")
    download_parser.add_argument(
        "--preset",
        choices=sorted(KNOWN_FILES),
        default="valid_current",
        help="Default is the smallest useful bundle: Validation current.zip, 3GB.",
    )
    download_parser.add_argument("--filekey", default="", help="Override filekey. Comma-separated multi download is allowed.")
    download_parser.add_argument("--out-dir", default="data/aihub238/downloads")
    download_parser.add_argument("--api-key", default="", help="Prefer env AIHUB_API_KEY/AIHUB_APIKEY instead of passing this.")
    download_parser.add_argument("--keep-tar", action="store_true")

    args = parser.parse_args()
    if args.command == "list":
        fetch_file_tree(Path(args.out))
        return
    if args.command == "download":
        filekey = args.filekey or KNOWN_FILES[args.preset]["filekey"]
        api_key = args.api_key or os.getenv("AIHUB_API_KEY") or os.getenv("AIHUB_APIKEY")
        if not api_key:
            print("AIHUB_API_KEY is not set. Set it locally, then run this command again.", file=sys.stderr)
            print('PowerShell example: $env:AIHUB_API_KEY="YOUR_KEY"', file=sys.stderr)
            raise SystemExit(2)
        download_filekeys(filekey, api_key, Path(args.out_dir), keep_tar=args.keep_tar)


def fetch_file_tree(output_path: Path) -> str:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(INFO_URL, timeout=60)
    response.encoding = "utf-8"
    text = response.text
    output_path.write_text(text, encoding="utf-8")
    print(text)
    print(f"\nSaved file tree: {output_path}")
    print("\nKnown useful filekeys:")
    for preset, info in KNOWN_FILES.items():
        print(f"- {preset}: filekey={info['filekey']} size={info['size']} name={info['name']}")
    return text


def download_filekeys(filekeys: str, api_key: str, out_dir: Path, keep_tar: bool = False) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    tar_path = out_dir / f"aihub238_{filekeys.replace(',', '_')}.tar"
    print(f"Downloading filekey(s) {filekeys} to {tar_path}")
    print("This may take a long time. The smallest useful bundle is still about 3GB.")
    with requests.get(
        DOWNLOAD_URL,
        params={"fileSn": filekeys},
        headers={"apikey": api_key},
        stream=True,
        timeout=(30, 300),
    ) as response:
        if response.status_code != 200:
            body = response.text[:2000]
            raise RuntimeError(f"AI-Hub download failed: HTTP {response.status_code}\n{body}")
        with tar_path.open("wb") as handle:
            downloaded = 0
            next_report = 256 * 1024 * 1024
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                handle.write(chunk)
                downloaded += len(chunk)
                if downloaded >= next_report:
                    print(f"downloaded={downloaded / (1024 ** 3):.2f}GB", flush=True)
                    next_report += 256 * 1024 * 1024
    extract_tar(tar_path, out_dir)
    merge_part_files(out_dir)
    if not keep_tar:
        tar_path.unlink(missing_ok=True)
    print(f"Done. Output directory: {out_dir}")


def extract_tar(tar_path: Path, out_dir: Path) -> None:
    print(f"Extracting {tar_path.name}")
    with tarfile.open(tar_path) as archive:
        archive.extractall(out_dir)


def merge_part_files(root: Path) -> None:
    print("Merging .part files when present")
    for directory, _, files in os.walk(root):
        dir_path = Path(directory)
        prefixes = sorted({name.rsplit(".part", 1)[0] for name in files if ".part" in name})
        for prefix in prefixes:
            parts = sorted(dir_path.glob(f"{prefix}.part*"), key=_part_sort_key)
            output = dir_path / prefix
            print(f"Merging {len(parts)} parts -> {output}")
            with output.open("wb") as merged:
                for part in parts:
                    with part.open("rb") as handle:
                        shutil.copyfileobj(handle, merged)
            for part in parts:
                part.unlink()


def _part_sort_key(path: Path) -> int:
    suffix = path.name.rsplit(".part", 1)[-1]
    try:
        return int(suffix)
    except ValueError:
        return 0


if __name__ == "__main__":
    main()
