"""turn-engine: 문진 한 턴의 검증 로직(순수 함수). 인터페이스 I8."""
from ._common import ContractViolation
from .flow import DATASET_V2_FLOW, QuestionFlowTable, SkipRule
from .validation import Violation, validate_extraction

ENGINE_VERSION = "0.4.3"

__all__ = [
    "ENGINE_VERSION", "ContractViolation",
    "validate_extraction", "Violation", "QuestionFlowTable", "SkipRule", "DATASET_V2_FLOW",
]
