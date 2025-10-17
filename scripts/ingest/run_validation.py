"""Command line entry point for running ingest validation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, List

import sys

if __package__ in (None, ""):
    current_dir = Path(__file__).resolve().parent
    if str(current_dir) not in sys.path:
        sys.path.append(str(current_dir))
    from validators import validate_payload, write_report
else:
    from .validators import validate_payload, write_report


def _iter_input_files(targets: Iterable[str]) -> List[Path]:
    files: List[Path] = []
    for target in targets:
        path = Path(target)
        if path.is_dir():
            for candidate in sorted(path.rglob("*.json")):
                if candidate.is_file():
                    files.append(candidate)
        elif path.is_file() and path.suffix.lower() == ".json":
            files.append(path)
        else:
            raise FileNotFoundError(f"未找到可读取的JSON文件: {target}")
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate IELTS question JSON payloads")
    parser.add_argument("inputs", nargs="+", help="待校验的JSON文件或目录")
    parser.add_argument(
        "--report-dir",
        default=Path("output/reports"),
        type=Path,
        help="校验报告输出目录（默认: output/reports）",
    )
    args = parser.parse_args()

    files = _iter_input_files(args.inputs)
    if not files:
        raise SystemExit("未发现任何JSON文件")

    errors_dir = args.report_dir / "errors"
    success_log = args.report_dir / "success.log"

    for file_path in files:
        with file_path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        report = validate_payload(file_path, payload)
        write_report(report, success_log=success_log, errors_dir=errors_dir)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
