"""Git 명령 실행 및 변경 사항 수집 유틸리티."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass


class GitError(RuntimeError):
    """Git 명령 실행 중 발생한 오류."""


def _run(args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise GitError("git 실행 파일을 찾을 수 없습니다. Git이 설치되어 있는지 확인하세요.") from exc

    if result.returncode != 0:
        raise GitError(result.stderr.strip() or f"git {' '.join(args)} 실행에 실패했습니다.")
    return result.stdout


def ensure_git_repo() -> None:
    """현재 디렉토리가 Git 저장소인지 확인한다."""
    try:
        output = _run(["rev-parse", "--is-inside-work-tree"])
    except GitError as exc:
        raise GitError("현재 디렉토리는 Git 저장소가 아닙니다. Git이 초기화된 프로젝트 루트에서 실행하세요.") from exc

    if output.strip() != "true":
        raise GitError("현재 디렉토리는 Git 저장소가 아닙니다. Git이 초기화된 프로젝트 루트에서 실행하세요.")


def get_status() -> str:
    """`git status --porcelain` 결과를 반환한다."""
    return _run(["status", "--porcelain"])


def get_diff() -> str:
    """작업 트리(unstaged) + 스테이징(staged) 변경 사항을 모두 합쳐 반환한다."""
    unstaged = _run(["diff"])
    staged = _run(["diff", "--cached"])
    parts = [part for part in (staged, unstaged) if part.strip()]
    return "\n".join(parts)


def get_current_branch() -> str:
    return _run(["rev-parse", "--abbrev-ref", "HEAD"]).strip()


@dataclass
class ChangeSummary:
    status_text: str
    diff_text: str
    changed_files: int
    diff_lines: int

    @property
    def has_changes(self) -> bool:
        return bool(self.status_text.strip())


def collect_changes() -> ChangeSummary:
    """git status/diff를 수집해 요약 정보를 반환한다."""
    status_text = get_status()
    changed_files = len([line for line in status_text.splitlines() if line.strip()])
    diff_text = get_diff() if changed_files else ""
    diff_lines = len(diff_text.splitlines())
    return ChangeSummary(
        status_text=status_text,
        diff_text=diff_text,
        changed_files=changed_files,
        diff_lines=diff_lines,
    )
