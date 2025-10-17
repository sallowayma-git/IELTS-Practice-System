"""File discovery utility for IELTS practice corpus."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, List, Dict, Any


REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET_DIR = REPO_ROOT / "睡着过项目组(9.4)[134篇]" / "3. 所有文章(9.4)[134篇]"
ARTICLE_ID_PATTERN = re.compile(r"e\d+", re.IGNORECASE)


def iter_html_files(base_dir: Path) -> Iterable[Path]:
    """Yield all HTML files under *base_dir* recursively."""
    for path in base_dir.rglob("*.html"):
        if path.is_file() and path.suffix.lower() == ".html":
            yield path


def extract_article_id(path: Path) -> str | None:
    """Extract the first article identifier that matches ``e\\d+`` from *path*."""
    match = ARTICLE_ID_PATTERN.search(str(path))
    return match.group(0).lower() if match else None


def build_file_inventory() -> List[Dict[str, Any]]:
    """Construct the JSON-serialisable file inventory."""
    records: List[Dict[str, Any]] = []
    for file_path in sorted(iter_html_files(TARGET_DIR)):
        relative_path = file_path.relative_to(REPO_ROOT).as_posix()
        records.append(
            {
                "relativePath": relative_path,
                "articleId": extract_article_id(file_path),
            }
        )
    return records


def main() -> None:
    inventory = build_file_inventory()
    json_output = json.dumps(inventory, ensure_ascii=False, indent=2)
    print(json_output)


if __name__ == "__main__":
    main()
