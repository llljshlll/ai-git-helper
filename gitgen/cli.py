"""CLI 진입점: 커밋 메시지 / PR 초안 자동 생성."""

from __future__ import annotations

import argparse
import sys

from . import ai_client, formatter, git_utils, safe_mode, templates


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Git 변경 사항을 기반으로 AI가 커밋 메시지 / PR 초안을 생성합니다.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common_options(sub: argparse.ArgumentParser) -> None:
        sub.add_argument(
            "-model", "--model",
            dest="model",
            default="claude-sonnet-5",
            help="사용할 AI 모델 (기본값: claude-sonnet-5)",
        )
        sub.add_argument(
            "-temperature", "--temperature",
            dest="temperature",
            type=float,
            default=0.3,
            help="생성 다양성 조절 파라미터 (기본값: 0.3)",
        )
        sub.add_argument(
            "-max-tokens", "--max-tokens",
            dest="max_tokens",
            type=int,
            default=1024,
            help="응답 최대 토큰 수 (기본값: 1024)",
        )
        sub.add_argument(
            "-safe-mode", "--safe-mode",
            dest="safe_mode",
            action="store_true",
            help="민감정보 마스킹 및 diff 전송량 제한을 적용합니다.",
        )
        sub.add_argument(
            "-max-files", "--max-files",
            dest="max_files",
            type=int,
            default=10,
            help="[safe-mode] 전송할 최대 파일 수 (기본값: 10)",
        )
        sub.add_argument(
            "-max-lines", "--max-lines",
            dest="max_lines",
            type=int,
            default=200,
            help="[safe-mode] 전송할 최대 diff 줄 수 (기본값: 200)",
        )

    commit_parser = subparsers.add_parser("commit", help="커밋 메시지를 생성합니다.")
    add_common_options(commit_parser)

    pr_parser = subparsers.add_parser("pr", help="PR 제목/본문 초안을 생성합니다.")
    add_common_options(pr_parser)

    return parser


def _log(message: str) -> None:
    print(message)


def _prepare_changes(args: argparse.Namespace) -> tuple[str, str] | None:
    """status/diff를 수집하고 safe-mode를 적용한다. 변경 사항이 없으면 None을 반환한다."""
    summary = git_utils.collect_changes()

    if not summary.has_changes:
        _log("[INFO] 변경 사항이 없습니다. 생성하지 않고 종료합니다.")
        return None

    _log(f"[INFO] Git status 수집 완료: {summary.changed_files}개 파일 변경 감지")
    _log(f"[INFO] Git diff 수집 완료: {summary.diff_lines}줄")

    diff_text = summary.diff_text
    if args.safe_mode:
        diff_text, report = safe_mode.apply_safe_mode(
            diff_text, max_files=args.max_files, max_lines=args.max_lines
        )
        _log(f"[INFO] safe-mode 적용: 민감정보 {report.masked_count}건 마스킹")
        if report.diff_limit and report.diff_limit.truncated:
            _log(
                f"[INFO] safe-mode 적용: diff {report.diff_limit.included_files}/"
                f"{report.diff_limit.total_files}개 파일만 전송"
            )

    return summary.status_text, diff_text


def run_commit(args: argparse.Namespace) -> int:
    try:
        git_utils.ensure_git_repo()
    except git_utils.GitError as exc:
        _log(f"[ERROR] {exc}")
        return 1

    prepared = _prepare_changes(args)
    if prepared is None:
        return 0
    status_text, diff_text = prepared

    system_prompt, user_prompt = templates.build_commit_prompt(status_text, diff_text)
    params = ai_client.AIParams(model=args.model, temperature=args.temperature, max_tokens=args.max_tokens)

    _log("[INFO] AI API 요청 중...")
    try:
        raw_text = ai_client.call_ai(system_prompt, user_prompt, params)
    except (ai_client.AIConfigError, ai_client.AIRequestError) as exc:
        _log(f"[ERROR] {exc}")
        return 1

    _log("[DONE] 커밋 메시지 생성 완료 (API 호출 1회)")
    commit = formatter.parse_commit_message(raw_text)
    print()
    print(formatter.render_commit_output(commit))
    return 0


def run_pr(args: argparse.Namespace) -> int:
    try:
        git_utils.ensure_git_repo()
    except git_utils.GitError as exc:
        _log(f"[ERROR] {exc}")
        return 1

    try:
        branch = git_utils.get_current_branch()
    except git_utils.GitError as exc:
        _log(f"[ERROR] {exc}")
        return 1

    _log(f"[INFO] 현재 브랜치: {branch}")

    prepared = _prepare_changes(args)
    if prepared is None:
        return 0
    status_text, diff_text = prepared

    system_prompt, user_prompt = templates.build_pr_prompt(branch, status_text, diff_text)
    params = ai_client.AIParams(model=args.model, temperature=args.temperature, max_tokens=args.max_tokens)

    _log("[INFO] AI API 요청 중...")
    try:
        raw_text = ai_client.call_ai(system_prompt, user_prompt, params)
    except (ai_client.AIConfigError, ai_client.AIRequestError) as exc:
        _log(f"[ERROR] {exc}")
        return 1

    _log("[DONE] PR 초안 생성 완료 (API 호출 1회)")
    pr = formatter.parse_pr_draft(raw_text)
    print()
    print(formatter.render_pr_output(pr))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "commit":
        return run_commit(args)
    if args.command == "pr":
        return run_pr(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
