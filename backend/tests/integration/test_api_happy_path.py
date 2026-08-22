def test_incident_happy_path(client):
    r = client.post(
        "/incident",
        json={"query": "Summarize recent PushEvent or WorkflowRunEvent activity in the ingested logs"},
    )
    assert r.status_code == 200
    body = r.json()
    for k in ("answer", "path_taken", "tool_used", "grade_reason"):
        assert k in body
    assert body["rejected"] is False
    assert body["path_taken"] in ("direct", "fallback")
    assert isinstance(body["answer"], str) and len(body["answer"]) > 0
    assert isinstance(body.get("retrieved_docs"), list)
