import pytest

from tools import (
    ToolPick,
    block_ip,
    log_tool,
    page_oncall,
    restart_pod,
    rollback_deploy,
    scale_replica,
)


def test_restart_pod_shape():
    s = restart_pod(namespace="prod", pod="api-0")
    assert isinstance(s, str)
    assert "[mock]" in s
    assert "api-0" in s
    assert "prod" in s


def test_block_ip_shape():
    s = block_ip(ip="203.0.113.1", reason="scan")
    assert "[mock]" in s
    assert "203.0.113.1" in s
    assert "scan" in s


def test_rollback_deploy_shape():
    s = rollback_deploy(service="web", version="v1.2")
    assert "web" in s and "v1.2" in s


def test_scale_replica_shape():
    s = scale_replica(service="ingest", replicas=5)
    assert "ingest" in s and "5" in s


def test_page_oncall_shape():
    s = page_oncall(severity="sev1", summary="db down")
    assert "sev1" in s and "db down" in s


def test_defaults_still_string():
    assert isinstance(restart_pod(), str)
    assert isinstance(block_ip(), str)
    assert isinstance(rollback_deploy(), str)
    assert isinstance(scale_replica(), str)
    assert isinstance(page_oncall(), str)


def test_log_tool_none():
    assert log_tool(ToolPick(tool_name="none", params={}, reason="n/a")) == "none"


def test_log_tool_filters_bad_params():
    pick = ToolPick(
        tool_name="restart_pod",
        params={"namespace": "ns", "pod": "p1", "extra_garbage": True},
        reason="crash",
    )
    assert log_tool(pick) == "restart_pod"


def test_scale_replica_weird_replicas_still_returns():
    s = scale_replica(service="x", replicas="many")
    assert isinstance(s, str)
    assert "x" in s
