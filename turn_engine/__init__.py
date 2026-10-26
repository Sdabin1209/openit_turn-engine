"""turn-engine: 문진 한 턴의 판단 로직(순수 함수). 인터페이스 I8."""
from ._common import (
    SUPPORTED_RUNTIME_CONTRACT_VERSION,
    ContractViolation,
    OutputContractError,
)
from .flow import DATASET_V2_FLOW, QuestionFlowTable, SkipRule
from ._deprecated import deprecated
from .judge import judge as _judge
from .normalizer import normalize as _normalize
from .planner import plan as _plan
from .validation import Violation, validate_extraction
from .writer import write_record as _write_record

ENGINE_VERSION = "0.3.0"

# 계약 2.0.0(D74·D75)에서 정규화기·판정기·기록기·Plan은 서비스에 없다. 폐기 표시만 하고 제거 시점은
# survey-service 이전이 끝난 뒤다(헤드 지시, migration-2.0.0). 동작은 0.2.0과 같다.
normalize = deprecated(_normalize)
judge = deprecated(_judge)
write_record = deprecated(_write_record)
plan = deprecated(_plan)

__all__ = [
    "normalize", "judge", "write_record", "plan",
    "ENGINE_VERSION", "SUPPORTED_RUNTIME_CONTRACT_VERSION",
    "ContractViolation", "OutputContractError",
    "validate_extraction", "Violation", "QuestionFlowTable", "SkipRule", "DATASET_V2_FLOW",
]
