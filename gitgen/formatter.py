"""AI 응답을 실무 규칙(길이/템플릿)에 맞게 검증하고 다듬는다."""

from __future__ import annotations

import re
from dataclasses import dataclass

COMMIT_TITLE_SOFT_LIMIT = 50
COMMIT_TITLE_HARD_LIMIT = 72
PR_TITLE_HARD_LIMIT = 80

REQUIRED_PR_SECTIONS = ["## Why", "## What", "## How to Test"]


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


@dataclass
class CommitMessage:
    title: str
    body: str

    def render(self) -> str:
        if self.body.strip():
            return f"{self.title}\n\n{self.body.strip()}"
        return self.title


def parse_commit_message(raw_text: str) -> CommitMessage:
    lines = [line for line in raw_text.strip().splitlines()]
    lines = [line for line in lines if line.strip()] or [""]

    title = lines[0].strip().strip("`")
    body_lines = raw_text.strip().splitlines()[1:]
    body = "\n".join(body_lines).strip()

    if len(title) > COMMIT_TITLE_HARD_LIMIT:
        title = _truncate(title, COMMIT_TITLE_HARD_LIMIT)

    # 최소 품질 기준: 본문이 있는데 파일 언급도, 불릿 요약도 없다면 안내 문구를 덧붙인다.
    if body and not re.search(r"^-", body, flags=re.MULTILINE) and not re.search(r"[\w./-]+\.\w+", body):
        body = f"- {body.splitlines()[0]}"

    return CommitMessage(title=title, body=body)


@dataclass
class PullRequest:
    title: str
    body: str
    warnings: list[str]

    def render(self) -> str:
        return self.body


def parse_pr_draft(raw_text: str) -> PullRequest:
    warnings: list[str] = []

    title_match = re.search(r"PR_TITLE:\s*(.+)", raw_text)
    body_match = re.search(r"PR_BODY:\s*(.*)", raw_text, flags=re.DOTALL)

    if title_match:
        title = title_match.group(1).strip()
    else:
        # 형식을 못 지켰을 경우, 첫 줄을 제목으로 대체 사용한다.
        title = raw_text.strip().splitlines()[0].strip()
        warnings.append("PR_TITLE 형식을 찾지 못해 첫 줄을 제목으로 사용했습니다.")

    if body_match:
        body = body_match.group(1).strip()
    else:
        body = raw_text.strip()
        warnings.append("PR_BODY 형식을 찾지 못해 전체 응답을 본문으로 사용했습니다.")

    if len(title) > PR_TITLE_HARD_LIMIT:
        title = _truncate(title, PR_TITLE_HARD_LIMIT)
        warnings.append(f"PR 제목이 {PR_TITLE_HARD_LIMIT}자를 초과해 잘랐습니다.")

    body = _ensure_pr_sections(body, warnings)

    return PullRequest(title=title, body=body, warnings=warnings)


def _ensure_pr_sections(body: str, warnings: list[str]) -> str:
    """필수 섹션 헤더와 최소 1개 불릿을 보장한다(누락 시 후처리로 보완)."""
    for section in REQUIRED_PR_SECTIONS:
        pattern = re.compile(rf"^{re.escape(section)}\s*$", flags=re.MULTILINE)
        if not pattern.search(body):
            warnings.append(f"'{section}' 섹션이 없어 기본 섹션을 추가했습니다.")
            body += f"\n\n{section}\n- (자동 생성됨) 세부 내용을 검토 후 보완해주세요."
            continue

        # 섹션 헤더는 있으나 불릿이 없는 경우 보완한다.
        section_body = _extract_section_body(body, section)
        if not re.search(r"^-", section_body, flags=re.MULTILINE):
            insertion_point = pattern.search(body).end()
            warnings.append(f"'{section}' 섹션에 불릿이 없어 기본 항목을 추가했습니다.")
            body = (
                body[:insertion_point]
                + "\n- (자동 생성됨) 세부 내용을 검토 후 보완해주세요."
                + body[insertion_point:]
            )

    return body.strip()


def _extract_section_body(body: str, section: str) -> str:
    sections = REQUIRED_PR_SECTIONS + ["## "]
    pattern = re.compile(rf"^{re.escape(section)}\s*$(.*?)(?=^## |\Z)", flags=re.MULTILINE | re.DOTALL)
    match = pattern.search(body)
    return match.group(1) if match else ""


def render_commit_output(commit: CommitMessage) -> str:
    lines = [
        "--- Commit Message ---",
        commit.render(),
        "-" * 22,
    ]
    return "\n".join(lines)


def render_pr_output(pr: PullRequest) -> str:
    lines = [
        "--- PR Title ---",
        pr.title,
        "",
        "--- PR Body ---",
        pr.body,
        "-" * 16,
    ]
    if pr.warnings:
        lines.append("")
        lines.append("[WARN] 형식 보정 내역:")
        lines.extend(f"  - {w}" for w in pr.warnings)
    return "\n".join(lines)
