#!/usr/bin/env python3
"""AI 기반 Git 커밋 메시지 / PR 초안 자동 생성 CLI 진입점."""

import sys

from gitgen.cli import main

if __name__ == "__main__":
    sys.exit(main())
