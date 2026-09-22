"""민감정보 마스킹 및 diff 전송량 제한 (--safe-mode)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# (A) 민감정보로 의심되는 패턴을 마스킹한다.
# 패턴은 실무에서 자주 보이는 형태를 기준으로 하며, 필요에 따라 확장 가능하다.
MASK_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("OpenAI-style key", re.compile(r"sk-[A-Za-z0-9_-]{20,}")),
    ("Anthropic key", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Slack token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("Generic bearer token", re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]{15,}")),
    ("Email address", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("Generic long secret", re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-/.+]{8,}['\"]?")),
]


def mask_sensitive(text: str) -> tuple[str, int]:
    """텍스트에서 민감정보로 의심되는 패턴을 [MASKED:<종류>]로 치환한다.

    Returns: (마스킹된 텍스트, 마스킹된 총 횟수)
    """
    masked_count = 0

    def _sub(label: str):
        def repl(match: re.Match[str]) -> str:
            nonlocal masked_count
            masked_count += 1
            return f"[MASKED:{label}]"

        return repl

    for label, pattern in MASK_PATTERNS:
        text = pattern.sub(_sub(label), text)

    return text, masked_count


@dataclass
class DiffLimitResult:
    diff_text: str
    included_files: int
    total_files: int
    truncated: bool
    dropped_lines: int = 0


def _split_by_file(diff_text: str) -> list[str]:
    """`diff --git a/... b/...` 기준으로 파일 단위 청크를 나눈다."""
    if not diff_text.strip():
        return []
    chunks = re.split(r"(?=^diff --git )", diff_text, flags=re.MULTILINE)
    return [chunk for chunk in chunks if chunk.strip()]


def limit_diff(diff_text: str, max_files: int = 10, max_lines: int = 200) -> DiffLimitResult:
    """(B) diff를 파일 수/총 줄 수 기준으로 제한한다."""
    file_chunks = _split_by_file(diff_text)
    total_files = len(file_chunks)

    included_chunks: list[str] = []
    used_lines = 0
    truncated = False

    for chunk in file_chunks[:max_files]:
        chunk_lines = chunk.splitlines()
        remaining = max_lines - used_lines
        if remaining <= 0:
            truncated = True
            break
        if len(chunk_lines) > remaining:
            included_chunks.append("\n".join(chunk_lines[:remaining]))
            included_chunks.append(f"... (이하 {len(chunk_lines) - remaining}줄 생략됨)")
            used_lines = max_lines
            truncated = True
            break
        included_chunks.append(chunk)
        used_lines += len(chunk_lines)

    if total_files > max_files:
        truncated = True

    result_text = "\n".join(included_chunks)
    dropped_lines = max(0, sum(len(c.splitlines()) for c in file_chunks) - used_lines)

    if truncated:
        result_text += (
            f"\n\n[SAFE-MODE] diff 일부만 전송됨 "
            f"(파일 {min(len(file_chunks), max_files)}/{total_files}, 최대 {max_lines}줄 제한)"
        )

    return DiffLimitResult(
        diff_text=result_text,
        included_files=min(len(file_chunks), max_files),
        total_files=total_files,
        truncated=truncated,
        dropped_lines=dropped_lines,
    )


@dataclass
class SafeModeReport:
    enabled: bool
    masked_count: int = 0
    diff_limit: DiffLimitResult | None = None


def apply_safe_mode(diff_text: str, max_files: int = 10, max_lines: int = 200) -> tuple[str, SafeModeReport]:
    masked_text, masked_count = mask_sensitive(diff_text)
    limit_result = limit_diff(masked_text, max_files=max_files, max_lines=max_lines)
    report = SafeModeReport(enabled=True, masked_count=masked_count, diff_limit=limit_result)
    return limit_result.diff_text, report
