import json

from fastapi.testclient import TestClient

from bridgescout.app import EXAMPLES, create_app
from bridgescout.config import load_settings


def client():
    return TestClient(create_app(load_settings({})))


def test_health_reports_demo_without_key():
    h = client().get("/api/health").json()
    assert h["mode"] == "demo" and h["planner"] == "scripted"


def test_settings_live_with_key_and_default_hackathon_url():
    s = load_settings({"QLOO_API_KEY": "abc"})
    assert s.mode == "live" and s.qloo_base_url == "https://hackathon.api.qloo.com"


def test_brief_stream_end_to_end():
    r = client().post("/api/brief", json=EXAMPLES[0])
    assert r.status_code == 200
    events = [json.loads(line) for line in r.text.splitlines() if line.strip()]
    assert events[0] == {"type": "start", "mode": "demo"}
    final = events[-1]
    assert final["type"] == "brief" and final["brief"]["mode"] == "demo"
    assert final["brief"]["evidence"]


def test_validation_and_index():
    c = client()
    assert c.post("/api/brief", json={"references": []}).status_code == 422
    bad = dict(EXAMPLES[0], references=[{"name": "x", "type": "music"}])
    assert c.post("/api/brief", json=bad).status_code == 422
    assert "BridgeScout" in c.get("/").text
