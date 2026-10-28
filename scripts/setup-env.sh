#!/usr/bin/env bash
# 왜: 영역 환경 준비의 정본은 이 파일 한 곳이다. 새 머신으로 옮길 때 README마다 설치법이 달랐던 것을 하나로 모았다.
# 근거: 의존은 requirements.lock(Git 태그 설치 + 잠금)이 정본이고 이 스크립트는 버전 숫자를 따로 적지 않는다. 다시 실행하면 .venv를 핀과 같게 맞춘다(멱등).
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

[ -f requirements.lock ] || { echo "setup-env: requirements.lock 이 없다" >&2; exit 1; }
[ -d .venv ] || python3 -m venv .venv || { echo "setup-env: python3 -m venv 실패(python3-venv 필요할 수 있음)" >&2; exit 1; }
PY=.venv/bin/python

# 왜 재시도 한 번: 일시적 네트워크 실패(GitHub SSH 등)를 흡수하되 오래 붙잡지 않는다.
run() {
  "$@" && return 0
  echo "setup-env: 실패, 한 번 재시도: $*" >&2
  sleep 3
  "$@" && return 0
  echo "setup-env: 실패(네트워크나 GitHub SSH 키 확인): $*" >&2
  return 1
}

# 왜 --force-reinstall --no-deps: 핀과 다른 옛 버전이 남아 있으면 핀 버전으로 교체한다. 의존 해석은 잠금 파일이 이미 끝냈다.
run "$PY" -m pip install --quiet --force-reinstall --no-deps -r requirements.lock
run "$PY" -m pip install --quiet --no-deps -e ".[dev]"

"$PY" -m pip check
echo "setup-env: 완료. 시험: .venv/bin/python -m pytest tests -q"
