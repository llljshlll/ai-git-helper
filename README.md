# ai-git-helper

Git 변경 사항(`git status` / `git diff`)을 수집해 Anthropic Claude API로 전달하고,
커밋 메시지와 Pull Request 초안을 자동 생성해주는 터미널 CLI 도구입니다.

생성된 결과는 초안일 뿐이며, 사용자가 검토 후 직접 커밋/PR에 적용합니다.
이 도구는 `git push`나 GitHub PR 생성(API) 등 원격 저장소 반영은 수행하지 않습니다.

## 1. 설치

```bash
git clone <이 저장소 URL>
cd ai-git-helper
python3 -m venv .venv && source .venv/bin/activate   # 선택 사항
pip install -r requirements.txt
```

- Python 3.10 이상이 필요합니다.

## 2. 환경변수(API Key) 설정

Anthropic Claude API Key는 **환경변수로만** 관리하며 코드에 하드코딩하지 않습니다.

```bash
export ANTHROPIC_API_KEY="sk-ant-여기에_발급받은_키"
```

매 터미널 세션마다 다시 설정하기 번거롭다면 `~/.zshrc` 또는 `~/.bashrc`에 위 줄을 추가하세요.

키가 없으면 아래와 같이 안내 메시지를 출력하고 종료합니다.

```text
[ERROR] ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.
예) export ANTHROPIC_API_KEY="YOUR_KEY"
```

## 3. 실행 방법

Git이 초기화된 프로젝트 루트 디렉토리에서 실행합니다.

### 커밋 메시지 생성

```bash
python3 main.py commit
```

### PR 제목/본문 생성

```bash
python3 main.py pr
```

### CLI 옵션 (commit / pr 공통)

| 옵션 | 설명 | 기본값 |
| --- | --- | --- |
| `-model`, `--model` | 사용할 AI 모델 | `claude-sonnet-5` |
| `-temperature`, `--temperature` | 생성 다양성(0~1). 낮을수록 일관되고 보수적, 높을수록 다양하고 창의적인 결과 | `0.3` |
| `-max-tokens`, `--max-tokens` | 응답 최대 토큰 수 | `1024` |
| `-safe-mode`, `--safe-mode` | 민감정보 마스킹 + diff 전송량 제한 적용 | 꺼짐 |
| `-max-files`, `--max-files` | [safe-mode] 전송할 최대 파일 수 | `10` |
| `-max-lines`, `--max-lines` | [safe-mode] 전송할 최대 diff 줄 수 | `200` |

예시:

```bash
python3 main.py commit -model claude-sonnet-5 -temperature 0.2 -max-tokens 800
python3 main.py pr -safe-mode -max-files 5 -max-lines 150
```

## 4. 출력 예시

### 커밋 메시지 생성

```text
$ python3 main.py commit
[INFO] Git status 수집 완료: 3개 파일 변경 감지
[INFO] Git diff 수집 완료: 128줄
[INFO] AI API 요청 중...
[DONE] 커밋 메시지 생성 완료 (API 호출 1회)

--- Commit Message ---
feat: Git 변경 사항 기반 커밋 메시지 자동 생성 기능 추가

- git diff 결과를 수집해 AI 입력 컨텍스트로 전달하도록 구현
- 커밋 메시지 템플릿(feat/fix 등) 생성 규칙 적용
----------------------
```

### PR 제목/본문 생성

```text
$ python3 main.py pr
[INFO] 현재 브랜치: feature/commit-pr-generator
[INFO] Git status 수집 완료: 4개 파일 변경 감지
[INFO] Git diff 수집 완료: 210줄
[INFO] AI API 요청 중...
[DONE] PR 초안 생성 완료 (API 호출 1회)

--- PR Title ---
feat: 커밋/PR 자동 생성 기능 추가

--- PR Body ---
## Why
- 팀 협업 시 커밋 메시지와 PR 설명 작성에 시간이 소요되어 자동 생성 도구가 필요했습니다.

## What
- git status, git diff 결과를 수집해 AI 입력 컨텍스트로 전달하는 로직 추가
- 커밋 메시지 자동 생성 기능(`python3 main.py commit`) 구현
- PR 제목/본문 자동 생성 기능(`python3 main.py pr`) 구현

## How to Test
- `export ANTHROPIC_API_KEY="YOUR_KEY"`
- `python3 main.py commit`
- `python3 main.py pr`
----------------
```

### 변경 사항이 없는 경우

```text
$ python3 main.py commit
[INFO] 변경 사항이 없습니다. 생성하지 않고 종료합니다.
```

## 5. 주의사항 / 운영 관점

### 민감정보 포함 가능성과 대응 (`-safe-mode`)

`git diff`에는 API Key, 이메일 등 민감정보가 포함될 수 있습니다. `-safe-mode` 옵션을 켜면 두 가지 보호 장치가 함께 적용됩니다.

- **(A) 마스킹**: OpenAI/Anthropic/GitHub/AWS/Slack 토큰 형태, Bearer 토큰, 이메일 주소, `key/secret/password/token=값` 형태의 문자열을 정규식으로 탐지해 `[MASKED:종류]`로 치환한 뒤 AI에 전달합니다. (`gitgen/safe_mode.py`의 `MASK_PATTERNS`에서 패턴을 추가/조정할 수 있습니다.)
- **(B) 전송량 제한**: 기본적으로 최대 10개 파일, 최대 200줄까지만 diff를 전송합니다(`-max-files`, `-max-lines`로 조정 가능). 초과분은 생략되었다는 안내와 함께 잘립니다.

민감한 저장소에서는 항상 `-safe-mode`를 함께 사용하는 것을 권장하며, 그럼에도 생성 결과를 커밋/PR에 반영하기 전 반드시 직접 검토하세요.

### 비용 / 요청 횟수

- `commit`, `pr` 명령은 각각 AI API를 **1회**만 호출합니다. 실행 결과에 `(API 호출 1회)`로 로그가 남습니다.
- 과도한 반복 실행은 비용 증가로 이어지므로, 변경 사항을 어느 정도 모은 뒤 한 번에 실행하는 것을 권장합니다.
- `-max-tokens`를 낮추면 응답 길이와 비용을 함께 줄일 수 있습니다.

## 6. 프로젝트 구조

```text
ai-git-helper/
├── main.py                # CLI 진입점
├── gitgen/
│   ├── cli.py              # argparse 기반 커맨드 처리 (commit / pr)
│   ├── git_utils.py        # git status / git diff 수집
│   ├── safe_mode.py        # 민감정보 마스킹 + diff 전송량 제한
│   ├── templates.py        # AI 프롬프트 템플릿
│   ├── ai_client.py        # Anthropic Claude API 호출
│   └── formatter.py        # 출력 길이/형식 검증 및 후처리
├── requirements.txt
└── README.md
```

## 7. 제약 사항

- Git 연동 범위는 `git status`, `git diff`로 제한되며, `git push`나 GitHub PR 생성 API 연동은 포함하지 않습니다.
- 생성된 커밋/PR 문구는 초안이며 최종 정답이 아닙니다. 반드시 검토 후 적용하세요.
