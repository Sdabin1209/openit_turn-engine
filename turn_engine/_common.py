"""공통 오류. I/O·시간·난수를 쓰지 않는다."""
from __future__ import annotations

class ContractViolation(ValueError):
    """입력이 문진 스키마(입력 계약)를 위반했다. 입력 값은 메시지에 담지 않는다."""

    def __init__(self, contract: str, errors: list[str]):
        self.contract = contract
        self.errors = errors
        super().__init__(f"{contract} 계약 위반: " + "; ".join(errors[:5]))
