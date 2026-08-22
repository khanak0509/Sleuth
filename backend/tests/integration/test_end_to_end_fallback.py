def test_unrelated_query_triggers_fallback(client):
    # passes topic guardrail (CI/incident flavored) but should not match live index
    q = (
        "Investigate CI workflow conclusion=failure for the fictional never-ingested "
        "repository zz-sleuth-nonexistent-org/zz-never-seen-repo-xyz-99999 and explain "
        "root cause from local logs only"
    )
    r = client.post("/incident", json={"query": q})
    assert r.status_code == 200
    body = r.json()
    assert body["rejected"] is False
    assert body["path_taken"] == "fallback", (
        f"expected fallback, got {body['path_taken']}: {body.get('grade_reason')}"
    )
    assert isinstance(body["answer"], str) and body["answer"]
