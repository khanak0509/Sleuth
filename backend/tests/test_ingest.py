from ingest import flatten_event


def test_flatten_push_has_required_meta(sample_push):
    text, meta = flatten_event(sample_push)
    assert meta["repo"] == "acme/widget"
    assert meta["event_type"] == "PushEvent"
    assert meta["timestamp"] == "2024-06-01T12:00:00Z"
    assert meta["actor"] == "dev1"
    for k in ("repo", "event_type", "timestamp", "actor", "text"):
        assert meta.get(k) is not None
        assert meta[k] != ""
    assert "PushEvent" in text
    assert "acme/widget" in text
    assert "fix flaky test" in text


def test_flatten_workflow_failure():
    ev = {
        "id": "99",
        "type": "WorkflowRunEvent",
        "created_at": "2024-07-01T08:00:00Z",
        "repo": {"name": "org/svc"},
        "actor": {"login": "github-actions[bot]"},
        "payload": {
            "action": "completed",
            "workflow_run": {
                "name": "CI",
                "conclusion": "failure",
                "status": "completed",
            },
        },
    }
    text, meta = flatten_event(ev)
    assert meta["event_type"] == "WorkflowRunEvent"
    assert meta["repo"] == "org/svc"
    assert meta["timestamp"]
    assert "conclusion=failure" in text
    assert None not in meta.values()


def test_flatten_missing_repo_uses_fallback_not_none():
    ev = {
        "id": "1",
        "type": "WatchEvent",
        "created_at": "2024-01-01T00:00:00Z",
        "repo": None,
        "actor": {},
        "payload": {"action": "started"},
    }
    text, meta = flatten_event(ev)
    assert meta["repo"] is not None and meta["repo"] != ""
    assert meta["actor"] is not None and meta["actor"] != ""
    assert meta["event_type"] == "WatchEvent"
    assert meta["timestamp"] == "2024-01-01T00:00:00Z"
    assert "WatchEvent" in text


def test_flatten_blank_timestamp_stays_explicit():
    ev = {
        "id": "2",
        "type": "IssuesEvent",
        "created_at": "",
        "repo": {"name": "a/b"},
        "actor": {"login": "x"},
        "payload": {"action": "opened", "issue": {"title": "bug", "state": "open"}},
    }
    _, meta = flatten_event(ev)
    assert meta["repo"] == "a/b"
    assert meta["event_type"] == "IssuesEvent"
    assert meta["timestamp"] == ""
