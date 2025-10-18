"""批量将HTML转换为JSON并执行审计。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Tuple

if __package__ in {None, ""}:  # 允许直接python执行
    package_root = Path(__file__).resolve().parents[2]
    sys.path.append(str(package_root))
    from scripts.ingest.audit_conversion import audit_exam_pair  # noqa: E402
    from scripts.ingest.html_exam_parser import convert_html_to_json  # noqa: E402
else:  # pragma: no cover - 包内调用
    from .audit_conversion import audit_exam_pair
    from .html_exam_parser import convert_html_to_json


def _collect_html_files(root: Path) -> List[Path]:
    if root.is_file():
        return [root]
    return sorted(root.rglob("*.html"))


def main() -> None:
    parser = argparse.ArgumentParser(description="批量转换HTML并执行审计")
    parser.add_argument("html_root", type=Path, help="HTML根目录或单个文件")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/json"),
        help="JSON输出目录（默认output/json）",
    )
    args = parser.parse_args()

    html_files = _collect_html_files(args.html_root)
    if not html_files:
        raise SystemExit("未找到任何HTML文件")

    failures: List[Tuple[Path, Exception]] = []

    for html_path in html_files:
        try:
            json_path = convert_html_to_json(html_path, args.output_dir)
            audit_exam_pair(html_path, json_path)
            exam_id = json_path.stem
            print(f"[OK] {exam_id} -> {json_path}")
        except Exception as exc:  # noqa: BLE001 - 需要捕获所有异常用于统计
            failures.append((html_path, exc))
            print(f"[FAIL] {html_path}: {exc}")

    if failures:
        print("\n转换或审计失败的文件:")
        for path, error in failures:
            print(f" - {path}: {error}")
        raise SystemExit(1)


if __name__ == "__main__":  # pragma: no cover
    main()

