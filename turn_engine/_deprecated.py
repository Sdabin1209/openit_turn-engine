"""폐기 표시. 호출은 그대로 동작하고 DeprecationWarning만 낸다(결정성·순수성에 영향 없음)."""
import functools
import warnings


def deprecated(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        warnings.warn(
            f"turn_engine.{fn.__name__}은 boundary-contracts 2.0.0에서 폐기되었다(D74, D75). "
            "survey-service 이전이 끝나면 제거된다. 대신 validate_extraction을 쓴다.",
            DeprecationWarning, stacklevel=2)
        return fn(*args, **kwargs)
    wrapper.__deprecated__ = True
    return wrapper
