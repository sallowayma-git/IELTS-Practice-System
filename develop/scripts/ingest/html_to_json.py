"""命令行工具：单篇HTML转换为JSON。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:  # 允许直接python执行
    package_root = Path(__file__).resolve().parents[2]
    sys.path.append(str(package_root))
    from scripts.ingest.html_exam_parser import convert_html_to_json
else:  # pragma: no cover - 包内调用
    from .html_exam_parser import convert_html_to_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert IELTS reading HTML to JSON")
    parser.add_argument("html", type=Path, help="HTML文件路径")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/json"),
        help="JSON输出目录（默认output/json）",
    )
    args = parser.parse_args()

    output_path = convert_html_to_json(args.html, args.output_dir)
    print(f"已生成: {output_path}")


if __name__ == "__main__":  # pragma: no cover
    main()

