"""Batch ingestion runner for IELTS Practice System.

This script reads a JSON configuration file describing how to batch
process HTML inputs into JSON outputs.  Tasks are executed in batches of
10-20 items (configured via the `batch_size` field) with concurrent
execution inside each batch.  The runner prints live progress updates,
including percentage and estimated remaining time, and automatically
retries failed files while recording their retry counts.

Configuration file schema (JSON):

```
{
    "input_dir": "睡着过项目组(9.4)[134篇]/3. 所有文章(9.4)[134篇]",
    "glob": "*.html",                 # optional (default: "*.html")
    "command": [                      # shell command template (list or string)
        "python", "scripts/ingest/single_ingest.py",
        "--input", "{input}",
        "--output", "{output}"
    ],
    "output_dir": "output/json",      # optional placeholder target
    "batch_size": 12,                 # required, must be between 10 and 20
    "concurrency": 4,                 # optional, default: batch_size
    "max_retries": 2,                 # optional, default: 1
    "retry_delay_seconds": 2.0        # optional, default: 0
}
```

`command` may contain the placeholders `{input}`, `{output}`, `{stem}`
(the filename without extension) and `{index}` (1-based index in the
full workload).  If `output_dir` is provided, the runner automatically
creates a per-file output path by joining that directory with the input
stem and appending `.json`.  You can also embed custom placeholders by
adding entries in the `extra_placeholders` object, which maps keys to
string values.

Usage:

```
python scripts/ingest/batch_runner.py --config path/to/config.json
```

The script only depends on the Python standard library, making it safe
to run in minimal environments.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shlex
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Task:
    """Represents a single file ingestion task."""

    index: int
    input_path: Path
    output_path: Optional[Path]
    command: Sequence[str]
    attempts: int = 0
    last_error: Optional[str] = None


@dataclass
class RunnerConfig:
    """Deserialized configuration for the batch runner."""

    input_dir: Path
    glob: str
    command_template: Sequence[str]
    output_dir: Optional[Path]
    batch_size: int
    concurrency: int
    max_retries: int
    retry_delay_seconds: float
    extra_placeholders: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any], base_dir: Path) -> "RunnerConfig":
        try:
            input_dir = (base_dir / data["input_dir"]).resolve()
        except KeyError as exc:  # pragma: no cover - defensive guard
            raise ValueError("配置缺少必需字段 input_dir") from exc
        if not input_dir.exists():
            raise ValueError(f"input_dir 路径不存在: {input_dir}")

        glob_pattern = data.get("glob", "*.html")

        command = data.get("command")
        if not command:
            raise ValueError("配置缺少必需字段 command")

        if isinstance(command, str):
            command_template = shlex.split(command)
        elif isinstance(command, Sequence):
            command_template = list(command)
        else:  # pragma: no cover - configuration guard
            raise ValueError("command 字段必须是字符串或字符串数组")

        batch_size = data.get("batch_size")
        if not isinstance(batch_size, int):
            raise ValueError("batch_size 必须是整数")
        if batch_size < 10 or batch_size > 20:
            raise ValueError("batch_size 必须在 10 到 20 之间")

        concurrency = data.get("concurrency", batch_size)
        if not isinstance(concurrency, int) or concurrency <= 0:
            raise ValueError("concurrency 必须是正整数")
        concurrency = min(concurrency, batch_size)

        max_retries = data.get("max_retries", 1)
        if not isinstance(max_retries, int) or max_retries < 0:
            raise ValueError("max_retries 必须是非负整数")

        retry_delay_seconds = float(data.get("retry_delay_seconds", 0.0))
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds 不能为负数")

        output_dir_value = data.get("output_dir")
        output_dir = (base_dir / output_dir_value).resolve() if output_dir_value else None
        extra_placeholders = data.get("extra_placeholders", {})
        if not isinstance(extra_placeholders, Mapping):
            raise ValueError("extra_placeholders 必须是对象")

        return cls(
            input_dir=input_dir,
            glob=glob_pattern,
            command_template=command_template,
            output_dir=output_dir,
            batch_size=batch_size,
            concurrency=concurrency,
            max_retries=max_retries,
            retry_delay_seconds=retry_delay_seconds,
            extra_placeholders=dict(extra_placeholders),
        )


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def load_config(path: Path) -> RunnerConfig:
    base_dir = path.resolve().parent
    with path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, Mapping):
        raise ValueError("配置文件必须是 JSON 对象")
    return RunnerConfig.from_mapping(raw, base_dir)


def build_tasks(config: RunnerConfig) -> List[Task]:
    files = sorted(config.input_dir.glob(config.glob))
    if not files:
        raise FileNotFoundError(f"未在 {config.input_dir} 下找到匹配 {config.glob} 的文件")

    tasks: List[Task] = []
    for idx, file_path in enumerate(files, start=1):
        placeholders = {
            "input": str(file_path.resolve()),
            "stem": file_path.stem,
            "index": str(idx),
            **{k: str(v) for k, v in config.extra_placeholders.items()},
        }

        output_path: Optional[Path] = None
        if config.output_dir:
            output_path = config.output_dir / f"{file_path.stem}.json"
            placeholders["output"] = str(output_path.resolve())
        else:
            placeholders.setdefault("output", "")

        command = [segment.format(**placeholders) for segment in config.command_template]
        tasks.append(Task(index=idx, input_path=file_path, output_path=output_path, command=command))

    return tasks


def chunked(iterable: Iterable[Task], size: int) -> Iterable[List[Task]]:
    batch: List[Task] = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


async def run_command(task: Task) -> Tuple[bool, Optional[str]]:
    """Execute the command associated with a task using asyncio."""

    process = await asyncio.create_subprocess_exec(
        *task.command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_bytes, stderr_bytes = await process.communicate()
    stdout_text = stdout_bytes.decode("utf-8", errors="ignore").strip()
    stderr_text = stderr_bytes.decode("utf-8", errors="ignore").strip()

    if process.returncode == 0:
        return True, stdout_text

    combined_error = stderr_text or stdout_text or f"退出码 {process.returncode}"
    return False, combined_error


def format_eta(start_time: float, completed: int, total: int) -> str:
    if completed == 0:
        return "未知"
    elapsed = time.time() - start_time
    rate = elapsed / completed
    remaining = (total - completed) * rate
    return time.strftime("%H:%M:%S", time.gmtime(max(0, remaining)))


def print_progress(completed: int, total: int, retries: MutableMapping[Path, int], start_time: float) -> None:
    percentage = (completed / total) * 100 if total else 0.0
    eta = format_eta(start_time, completed, total)
    retry_count = sum(retries.values())
    message = f"进度: {completed}/{total} ({percentage:5.1f}%) | 剩余时间估计: {eta} | 重试次数: {retry_count}"
    print(message, flush=True)


async def process_batch(batch_index: int, batch: List[Task], config: RunnerConfig, progress: "ProgressTracker") -> None:
    semaphore = asyncio.Semaphore(config.concurrency)

    async def worker(task: Task) -> None:
        while True:
            async with semaphore:
                task.attempts += 1
                success, error_text = await run_command(task)

            if success:
                progress.mark_success(task)
                return

            task.last_error = error_text
            remaining_retries = config.max_retries - (task.attempts - 1)
            if remaining_retries > 0:
                progress.mark_retry(task, remaining_retries)
                if config.retry_delay_seconds:
                    await asyncio.sleep(config.retry_delay_seconds)
                continue

            progress.mark_failure(task)
            return

    await asyncio.gather(*(worker(task) for task in batch))


# ---------------------------------------------------------------------------
# Progress tracking
# ---------------------------------------------------------------------------


class ProgressTracker:
    def __init__(self, total: int) -> None:
        self.total = total
        self.completed = 0
        self.failures: Dict[Path, str] = {}
        self.retries: Dict[Path, int] = {}
        self.start_time = time.time()

    def mark_success(self, task: Task) -> None:
        self.completed += 1
        print_progress(self.completed, self.total, self.retries, self.start_time)

    def mark_retry(self, task: Task, remaining_retries: int) -> None:
        retries_done = task.attempts - 1
        self.retries[task.input_path] = retries_done
        print(
            f"文件 {task.input_path.name} 失败，准备重试（已重试 {retries_done} 次，剩余 {remaining_retries} 次）"
            f"：{task.last_error}"
        )

    def mark_failure(self, task: Task) -> None:
        self.completed += 1
        retries_done = task.attempts - 1
        if retries_done > 0:
            self.retries[task.input_path] = retries_done
        self.failures[task.input_path] = task.last_error or "未知错误"
        print(f"文件 {task.input_path.name} 最终失败：{self.failures[task.input_path]}")
        print_progress(self.completed, self.total, self.retries, self.start_time)

    def summary(self) -> str:
        lines = [
            "运行完成",
            f"总数: {self.total}",
            f"成功: {self.total - len(self.failures)}",
            f"失败: {len(self.failures)}",
            f"总重试次数: {sum(self.retries.values())}",
        ]
        if self.failures:
            lines.append("失败文件:")
            for path, error in self.failures.items():
                retry_count = self.retries.get(path, 0)
                lines.append(f"  - {path} (重试 {retry_count} 次): {error}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量执行HTML转JSON任务")
    parser.add_argument(
        "--config",
        required=True,
        help="配置文件路径 (JSON)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅打印即将执行的命令，不实际运行",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    config_path = Path(args.config).resolve()
    if not config_path.exists():
        print(f"配置文件不存在: {config_path}", file=sys.stderr)
        return 1

    try:
        config = load_config(config_path)
    except Exception as exc:  # pragma: no cover - top level guard
        print(f"配置解析失败: {exc}", file=sys.stderr)
        return 1

    try:
        tasks = build_tasks(config)
    except Exception as exc:  # pragma: no cover - top level guard
        print(str(exc), file=sys.stderr)
        return 1

    total_tasks = len(tasks)
    tracker = ProgressTracker(total_tasks)

    if args.dry_run:
        for task in tasks:
            print(" ".join(task.command))
        print(f"共 {total_tasks} 个任务（dry-run 模式未执行）")
        return 0

    if config.output_dir:
        config.output_dir.mkdir(parents=True, exist_ok=True)

    batches = list(chunked(tasks, config.batch_size))
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        for batch_index, batch in enumerate(batches, start=1):
            print(f"开始处理第 {batch_index}/{len(batches)} 批，共 {len(batch)} 个文件")
            loop.run_until_complete(process_batch(batch_index, batch, config, tracker))
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()

    print(tracker.summary())
    return 0 if not tracker.failures else 2


if __name__ == "__main__":  # pragma: no cover - script entry
    raise SystemExit(main())
