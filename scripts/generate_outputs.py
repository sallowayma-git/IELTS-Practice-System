import json
import re
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = REPO_ROOT / "睡着过项目组(9.4)[134篇]" / "3. 所有文章(9.4)[134篇]"
OUTPUT_ROOT = REPO_ROOT / "output"
CHUNK_DIR = OUTPUT_ROOT / "chunks"
REPORT_DIR = OUTPUT_ROOT / "reports"

MIN_CHUNK = 5
MAX_CHUNK = 10
TOTAL_LIMIT = 134
VERSION = 1

def normalise_difficulty(name: str) -> str:
    match = re.search(r"【([^】]+)】", name)
    if match:
        value = match.group(1)
        if value in {"高", "次"}:
            return value
        return value
    return "常规"

def extract_question_type(name: str) -> str:
    match = re.search(r"P(\d)", name)
    return f"P{match.group(1)}" if match else "Unknown"

def clean_title(name: str) -> str:
    title = re.sub(r"^\d+\.\s*", "", name)
    title = re.sub(r"【[^】]+】", "", title)
    title = re.sub(r"^P\d\s*-\s*", "", title)
    return title.strip()

def iter_entries():
    for child in SOURCE_ROOT.iterdir():
        if child.name.startswith('.'):
            continue
        match = re.match(r"^(\d+)\.", child.name)
        if not match:
            continue
        idx = int(match.group(1))
        if idx > TOTAL_LIMIT:
            continue
        difficulty = normalise_difficulty(child.name)
        qtype = extract_question_type(child.name)
        title = clean_title(child.name)
        html_files = sorted(child.glob("*.html"))
        pdf_files = sorted(child.glob("*.pdf"))
        html_path = html_files[0].relative_to(REPO_ROOT).as_posix() if html_files else None
        pdf_path = pdf_files[0].relative_to(REPO_ROOT).as_posix() if pdf_files else None
        yield {
            "id": idx,
            "title": title,
            "difficulty": difficulty,
            "type": qtype,
            "directory": child.relative_to(REPO_ROOT).as_posix(),
            "html": html_path,
            "pdf": pdf_path,
        }

def chunk_group(items):
    chunks = []
    start = 0
    total = len(items)
    while start < total:
        remaining = total - start
        take = min(MAX_CHUNK, remaining)
        while remaining - take not in (0,) and remaining - take < MIN_CHUNK:
            take -= 1
        if take < MIN_CHUNK and remaining <= MAX_CHUNK:
            take = remaining
        if take < MIN_CHUNK and chunks:
            chunks[-1].extend(items[start:])
            return chunks
        chunks.append(items[start:start + take])
        start += take
    return chunks

def ensure_directories():
    CHUNK_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    ensure_directories()
    entries = sorted(iter_entries(), key=lambda item: item["id"])

    difficulty_groups = defaultdict(list)
    type_counter = Counter()
    difficulty_counter = Counter()
    difficulty_type_counter = defaultdict(lambda: Counter())

    for entry in entries:
        difficulty_groups[entry["difficulty"]].append(entry)
        type_counter[entry["type"]] += 1
        difficulty_counter[entry["difficulty"]] += 1
        difficulty_type_counter[entry["type"]][entry["difficulty"]] += 1

    slug_map = {"高": "hard", "次": "medium", "常规": "standard"}
    manifest_chunks = []

    for difficulty, group_items in difficulty_groups.items():
        group_items.sort(key=lambda item: item["id"])
        group_chunks = chunk_group(group_items)
        total_chunks = len(group_chunks)
        for index, chunk in enumerate(group_chunks, start=1):
            slug = slug_map.get(difficulty, difficulty)
            file_name = f"{slug}_{index:02d}.json"
            file_path = CHUNK_DIR / file_name
            payload = {
                "difficulty": difficulty,
                "chunkIndex": index,
                "totalChunks": total_chunks,
                "count": len(chunk),
                "items": chunk,
            }
            with file_path.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
            manifest_chunks.append({
                "difficulty": difficulty,
                "chunkIndex": index,
                "file": file_path.relative_to(REPO_ROOT).as_posix(),
                "startId": chunk[0]["id"],
                "endId": chunk[-1]["id"],
                "count": len(chunk),
            })

    manifest = {
        "version": VERSION,
        "totalExams": TOTAL_LIMIT,
        "offsets": sorted(manifest_chunks, key=lambda item: (item["difficulty"], item["chunkIndex"]))
    }

    with (OUTPUT_ROOT / "manifest.json").open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    statistics = {
        "version": VERSION,
        "total": len(entries),
        "byType": dict(sorted(type_counter.items())),
        "byDifficulty": dict(sorted(difficulty_counter.items())),
        "difficultyByType": {
            qtype: dict(sorted(counter.items())) for qtype, counter in sorted(difficulty_type_counter.items())
        },
        "chunkSummary": {
            difficulty: [len(chunk) for chunk in chunk_group(difficulty_groups[difficulty])] for difficulty in sorted(difficulty_groups)
        }
    }

    with (REPORT_DIR / "statistics.json").open("w", encoding="utf-8") as fh:
        json.dump(statistics, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

if __name__ == "__main__":
    main()
