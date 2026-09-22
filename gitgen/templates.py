"""AI 요청용 프롬프트 템플릿."""

from __future__ import annotations

COMMIT_SYSTEM_PROMPT = """당신은 숙련된 소프트웨어 엔지니어로서 Git 커밋 메시지를 작성합니다.
아래 규칙을 반드시 지키세요.

1. 첫 줄은 커밋 제목이며, "type: 설명" 형식(feat/fix/docs/refactor/test/chore 중 하나)을 따르고 50자 이내를 권장하며 72자를 넘기지 않습니다.
2. 제목 다음 빈 줄을 두고, 본문에는 변경된 파일(또는 모듈)을 1~3개 언급하거나, 핵심 변경 사항을 1~2개의 불릿(-)으로 요약합니다.
3. 코드 자체를 반복해서 출력하지 말고, 변경의 의미를 요약합니다.
4. 한국어로 작성합니다.
5. 커밋 메시지 텍스트만 출력하고, 다른 설명이나 마크다운 코드블록은 포함하지 않습니다."""

COMMIT_USER_TEMPLATE = """다음은 Git 변경 사항입니다. 이를 기반으로 커밋 메시지를 작성하세요.

## git status
{status}

## git diff
{diff}
"""

PR_SYSTEM_PROMPT = """당신은 숙련된 소프트웨어 엔지니어로서 Pull Request 초안을 작성합니다.
아래 규칙을 반드시 지키세요.

1. 첫 줄은 PR 제목이며 "PR_TITLE: " 접두사로 시작하고, 전체 길이는 80자를 넘기지 않습니다.
2. 그다음 "PR_BODY:" 라는 줄을 쓰고, 이후에 아래 마크다운 섹션 헤더를 정확히 이 이름으로 포함한 PR 본문을 작성합니다.
   - "## Why" : 변경 배경. 최소 1개의 불릿(-) 포함
   - "## What" : 핵심 변경 사항. 최소 1개의 불릿(-) 포함
   - "## How to Test" : 테스트 방법. 최소 1개의 불릿(-) 포함
3. 각 섹션은 실제 diff 내용에 근거해 구체적으로 작성합니다.
4. 한국어로 작성합니다.
5. 지정된 형식(PR_TITLE:, PR_BODY:, ## 섹션) 외의 다른 설명이나 코드블록은 포함하지 않습니다."""

PR_USER_TEMPLATE = """다음은 현재 브랜치와 Git 변경 사항입니다. 이를 기반으로 PR 제목과 본문을 작성하세요.

## 현재 브랜치
{branch}

## git status
{status}

## git diff
{diff}
"""


def build_commit_prompt(status: str, diff: str) -> tuple[str, str]:
    user_prompt = COMMIT_USER_TEMPLATE.format(status=status.strip(), diff=diff.strip())
    return COMMIT_SYSTEM_PROMPT, user_prompt


def build_pr_prompt(branch: str, status: str, diff: str) -> tuple[str, str]:
    user_prompt = PR_USER_TEMPLATE.format(branch=branch, status=status.strip(), diff=diff.strip())
    return PR_SYSTEM_PROMPT, user_prompt
