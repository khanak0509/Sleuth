import pytest
from pydantic import ValidationError

from agent import Grade
from guardrails import InputCheck, OutputCheck
from tools import ToolPick


def test_tool_pick_rejects_unknown_tool():
    with pytest.raises(ValidationError):
        ToolPick(tool_name="delete_cluster", params={}, reason="nope")


def test_tool_pick_accepts_literal():
    p = ToolPick(tool_name="block_ip", params={"ip": "1.2.3.4"}, reason="abuse")
    assert p.tool_name == "block_ip"
    assert p.params["ip"] == "1.2.3.4"


def test_tool_pick_none_ok():
    p = ToolPick(tool_name="none")
    assert p.params == {}


def test_grade_requires_bool():
    with pytest.raises(ValidationError):
        Grade(relevant="maybe", reason="x")


def test_grade_ok():
    g = Grade(relevant=True, reason="docs match repo")
    assert g.relevant is True


def test_input_check_requires_fields():
    with pytest.raises(ValidationError):
        InputCheck(safe=True)


def test_output_check_issues_must_be_list():
    with pytest.raises(ValidationError):
        OutputCheck(safe=False, issues="not-a-list")


def test_output_check_ok():
    o = OutputCheck(safe=False, issues=["leaked prompt"])
    assert len(o.issues) == 1
