"""계약 준수, 입출력 예시, 결정성, 순수성 시험."""
import builtins
import json
import pathlib
import random
import re
import socket
import time

import pytest
from jsonschema import Draft202012Validator

import turn_engine as te
from turn_engine import ContractViolation

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXAMPLES = sorted((ROOT / "examples").glob("*.json"))
SCHEMA_SRC = ROOT.parent / "survey-service" / "schema"
PKG_SCHEMAS = ROOT / "turn_engine" / "_schemas"
FUNCS = {"normalize": te.normalize, "judge": te.judge, "write_record": te.write_record, "plan": te.plan}
IN_SCHEMA = {"normalize": "AnswerNormalizerInput", "judge": "AnswerJudgeInput", "write_record": "RecordWriterInput", "plan": "DialoguePlannerInput"}
OUT_SCHEMA = {"normalize": "NormalizerOutput", "judge": "JudgeOutput", "write_record": "StoreResult", "plan": "PlannerOutput"}


def validator(name):
    return Draft202012Validator(json.loads((PKG_SCHEMAS / f"{name}.json").read_text(encoding="utf-8")))


def test_versions():
    assert isinstance(te.ENGINE_VERSION, str) and re.fullmatch(r"\d+\.\d+\.\d+", te.ENGINE_VERSION)
    assert te.SUPPORTED_RUNTIME_CONTRACT_VERSION == int((PKG_SCHEMAS / "CONTRACT_VERSION").read_text().strip())


@pytest.mark.skipif(not SCHEMA_SRC.exists(), reason="문진 스키마 원본이 없는 환경")
def test_vendored_schemas_match_survey_schema():
    assert (SCHEMA_SRC / "CONTRACT_VERSION").read_text().strip() == (PKG_SCHEMAS / "CONTRACT_VERSION").read_text().strip()
    for f in PKG_SCHEMAS.glob("*.json"):
        assert f.read_bytes() == (SCHEMA_SRC / "schemas" / f.name).read_bytes(), f.name


@pytest.mark.skipif(not SCHEMA_SRC.exists(), reason="문진 스키마 원본이 없는 환경")
def test_component_contract_names_match_components_yaml():
    text = (SCHEMA_SRC / "COMPONENTS.yaml").read_text(encoding="utf-8")
    for cid, fn in (("answer_normalizer", "normalize"), ("answer_judge", "judge"), ("record_writer", "write_record"),
                    ("dialogue_planner", "plan")):
        block = text.split(f"id: {cid}\n", 1)[1].split("\n- name:", 1)[0]
        assert f"input: {IN_SCHEMA[fn]}" in block and f"output: {OUT_SCHEMA[fn]}" in block


def test_examples_exist_for_every_component():
    comps = {p.name.split(".")[1] for p in EXAMPLES}
    assert comps == set(FUNCS)


@pytest.mark.parametrize("path", EXAMPLES, ids=[p.name for p in EXAMPLES])
def test_example_input_passes_input_schema_and_output_passes_output_schema(path):
    comp = path.name.split(".")[1]
    ex = json.loads(path.read_text(encoding="utf-8"))
    assert not list(validator(IN_SCHEMA[comp]).iter_errors(ex["input"]))
    out = FUNCS[comp](ex["input"])
    assert not list(validator(OUT_SCHEMA[comp]).iter_errors(out))
    assert out == ex["output"]  # 기대 출력(golden). 바꾸려면 scripts/gen_examples.py로 다시 만든다


@pytest.mark.parametrize("path", EXAMPLES, ids=[p.name for p in EXAMPLES])
def test_determinism_same_input_same_output_regardless_of_key_order(path):
    comp = path.name.split(".")[1]
    inp = json.loads(path.read_text(encoding="utf-8"))["input"]

    def reorder(x):
        if isinstance(x, dict):
            return {k: reorder(x[k]) for k in reversed(list(x))}
        if isinstance(x, list):
            return [reorder(v) for v in x]
        return x

    a = FUNCS[comp](inp)
    assert FUNCS[comp](inp) == a
    assert FUNCS[comp](reorder(inp)) == a


@pytest.mark.parametrize("path", EXAMPLES, ids=[p.name for p in EXAMPLES])
def test_pure_no_io_time_or_randomness(path, monkeypatch):
    comp = path.name.split(".")[1]
    inp = json.loads(path.read_text(encoding="utf-8"))["input"]
    FUNCS[comp](inp)  # 검증기 준비(가져올 때 한 번 읽는 스키마)

    def boom(*a, **k):
        raise AssertionError("순수 함수가 I/O·시간·난수를 썼다")

    monkeypatch.setattr(builtins, "open", boom)
    monkeypatch.setattr(time, "time", boom)
    monkeypatch.setattr(time, "monotonic", boom)
    monkeypatch.setattr(random, "random", boom)
    monkeypatch.setattr(socket, "socket", boom)
    FUNCS[comp](inp)


@pytest.mark.parametrize("comp", sorted(FUNCS))
def test_violations_raise_contract_violation(comp):
    path = next(p for p in EXAMPLES if p.name.split(".")[1] == comp)
    inp = json.loads(path.read_text(encoding="utf-8"))["input"]
    for bad in ({}, [], None, {**inp, "unexpected": 1}):
        with pytest.raises(ContractViolation):
            FUNCS[comp](bad)
    missing = dict(inp)
    missing.pop(next(iter(inp)))
    with pytest.raises(ContractViolation):
        FUNCS[comp](missing)


def test_violation_carries_contract_name_and_paths_only():
    with pytest.raises(ContractViolation) as e:
        te.write_record({"judgments": "비밀", "invalidated_questions": [], "question_slots": [], "target_records": []})
    assert e.value.contract == "RecordWriterInput" and "비밀" not in str(e.value) and e.value.errors


def test_mutation_of_output_does_not_affect_next_call():
    inp = json.loads(next(p for p in EXAMPLES if p.name == "conflict.plan.json").read_text(encoding="utf-8"))["input"]
    a = te.plan(inp)
    a["directive"]["notices"].append("x")
    a["directive"]["sentence_materials"]["fixed_sentences"].clear()
    assert te.plan(inp) != a and te.plan(inp) == te.plan(inp)


def test_random_sessions_always_produce_schema_valid_outputs():
    """무작위 발화 열을 이어 돌려도 모든 출력이 출력 계약을 통과한다(엔진이 출력을 검증하므로 예외가 없어야 한다)."""
    import sys
    sys.path.insert(0, str(ROOT / "tests"))
    from fuzz_tool import run
    for seed in range(12):
        run(1000 + seed, turns=25)
