"""Anthropic Claude API 연동."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass


class AIConfigError(RuntimeError):
    """API Key 미설정 등 설정 오류."""


class AIRequestError(RuntimeError):
    """API 호출 실패(네트워크/인증/응답 오류 등)."""


API_KEY_ENV = "ANTHROPIC_API_KEY"
BASE_URL_ENV = "ANTHROPIC_BASE_URL"  # 선택: Anthropic 호환 프록시(예: 코디세이) 주소

# OpenAI 호환 API(/v1/chat/completions) 사용 시
OPENAI_KEY_ENV = "OPENAI_API_KEY"
OPENAI_BASE_URL_ENV = "OPENAI_BASE_URL"
OPENAI_DEFAULT_BASE_URL = "https://api.openai.com"

PROVIDERS = ("anthropic", "openai")


@dataclass
class AIParams:
    model: str = "claude-sonnet-4"
    temperature: float = 0.3
    max_tokens: int = 1024
    provider: str = "anthropic"


def get_openai_api_key() -> str:
    api_key = os.environ.get(OPENAI_KEY_ENV)
    if not api_key:
        raise AIConfigError(
            f"{OPENAI_KEY_ENV} 환경변수가 설정되지 않았습니다.\n"
            f'예) export {OPENAI_KEY_ENV}="YOUR_KEY"'
        )
    return api_key


def get_api_key() -> str:
    api_key = os.environ.get(API_KEY_ENV)
    if not api_key:
        raise AIConfigError(
            f"{API_KEY_ENV} 환경변수가 설정되지 않았습니다.\n"
            f'예) export {API_KEY_ENV}="YOUR_KEY"'
        )
    return api_key


def call_ai(system_prompt: str, user_prompt: str, params: AIParams) -> str:
    """선택된 provider의 API를 호출해 생성된 텍스트를 반환한다."""
    if params.provider == "openai":
        return _call_openai_compatible(system_prompt, user_prompt, params)
    return _call_anthropic(system_prompt, user_prompt, params)


def _call_openai_compatible(system_prompt: str, user_prompt: str, params: AIParams) -> str:
    """OpenAI 호환 Chat Completions REST API(/v1/chat/completions)를 호출한다."""
    api_key = get_openai_api_key()
    base_url = (os.environ.get(OPENAI_BASE_URL_ENV) or OPENAI_DEFAULT_BASE_URL).rstrip("/")
    if base_url.endswith("/v1"):
        base_url = base_url[: -len("/v1")]

    payload = {
        "model": params.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": params.max_tokens,
        "temperature": params.temperature,
    }
    request = urllib.request.Request(
        f"{base_url}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        if exc.code in (401, 403):
            raise AIRequestError(f"AI API 인증/권한 오류입니다. API Key를 확인하세요. (status={exc.code}, {detail})") from exc
        if exc.code == 429:
            raise AIRequestError(f"AI API 요청 한도를 초과했습니다. 잠시 후 다시 시도하세요. ({detail})") from exc
        raise AIRequestError(f"AI API가 오류를 반환했습니다. (status={exc.code}, {detail})") from exc
    except urllib.error.URLError as exc:
        raise AIRequestError(f"AI API 서버에 연결할 수 없습니다. 네트워크 상태를 확인하세요. ({exc.reason})") from exc
    except (TimeoutError, json.JSONDecodeError) as exc:
        raise AIRequestError(f"AI API 응답 처리 중 오류가 발생했습니다: {exc}") from exc

    try:
        result = (body["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise AIRequestError(f"AI API 응답 형식이 올바르지 않습니다: {str(body)[:300]}") from exc
    if not result:
        raise AIRequestError(
            "AI API 응답이 비어 있습니다. 추론형 모델은 -max-tokens를 늘려 보세요."
        )
    return result


def _call_anthropic(system_prompt: str, user_prompt: str, params: AIParams) -> str:
    """Anthropic Messages API를 호출해 생성된 텍스트를 반환한다."""
    api_key = get_api_key()

    try:
        import anthropic
    except ImportError as exc:
        raise AIRequestError(
            "anthropic 패키지가 설치되어 있지 않습니다. `pip install -r requirements.txt`를 실행하세요."
        ) from exc

    try:
        base_url = os.environ.get(BASE_URL_ENV) or None
        client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
        response = client.messages.create(
            model=params.model,
            max_tokens=params.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            # 최신 SDK가 temperature를 타입 파라미터로 노출하지 않는 경우를 대비해
            # extra_body로 전달한다(Anthropic Messages API 자체는 이 필드를 지원한다).
            extra_body={"temperature": params.temperature},
        )
    except anthropic.AuthenticationError as exc:
        raise AIRequestError(f"AI API 인증에 실패했습니다. API Key를 확인하세요. ({exc})") from exc
    except anthropic.APIConnectionError as exc:
        raise AIRequestError(f"AI API 서버에 연결할 수 없습니다. 네트워크 상태를 확인하세요. ({exc})") from exc
    except anthropic.RateLimitError as exc:
        raise AIRequestError(f"AI API 요청 한도를 초과했습니다. 잠시 후 다시 시도하세요. ({exc})") from exc
    except anthropic.APIStatusError as exc:
        raise AIRequestError(f"AI API가 오류를 반환했습니다. (status={exc.status_code}, {exc})") from exc
    except Exception as exc:  # noqa: BLE001 - 예상치 못한 오류도 사용자에게 원인과 함께 보고한다.
        raise AIRequestError(f"AI API 호출 중 알 수 없는 오류가 발생했습니다: {exc}") from exc

    text_parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
    result = "\n".join(text_parts).strip()
    if not result:
        raise AIRequestError("AI API 응답에서 텍스트를 찾을 수 없습니다.")
    return result
