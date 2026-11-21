"""Anthropic Claude API 연동."""

from __future__ import annotations

import os
from dataclasses import dataclass


class AIConfigError(RuntimeError):
    """API Key 미설정 등 설정 오류."""


class AIRequestError(RuntimeError):
    """API 호출 실패(네트워크/인증/응답 오류 등)."""


API_KEY_ENV = "ANTHROPIC_API_KEY"


@dataclass
class AIParams:
    model: str = "claude-sonnet-5"
    temperature: float = 0.3
    max_tokens: int = 1024


def get_api_key() -> str:
    api_key = os.environ.get(API_KEY_ENV)
    if not api_key:
        raise AIConfigError(
            f"{API_KEY_ENV} 환경변수가 설정되지 않았습니다.\n"
            f'예) export {API_KEY_ENV}="YOUR_KEY"'
        )
    return api_key


def call_ai(system_prompt: str, user_prompt: str, params: AIParams) -> str:
    """Anthropic Messages API를 호출해 생성된 텍스트를 반환한다."""
    api_key = get_api_key()

    try:
        import anthropic
    except ImportError as exc:
        raise AIRequestError(
            "anthropic 패키지가 설치되어 있지 않습니다. `pip install -r requirements.txt`를 실행하세요."
        ) from exc

    try:
        client = anthropic.Anthropic(api_key=api_key)
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
