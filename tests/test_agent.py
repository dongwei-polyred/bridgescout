import json

import httpx

from bridgescout import fake_qloo
from bridgescout.agent import BridgeScoutAgent
from bridgescout.llm import LLMClient
from bridgescout.qloo import QlooClient
from bridgescout.tools import Toolbox

REQ = {"brand": "Moonbun", "description": "blind-box toys", "goal": "pop-up",
       "references": [{"name": "Pop Mart", "type": "brand"}, {"name": "Sanrio", "type": "brand"}],
       "cities": ["Los Angeles", "London", "Bangkok"]}


def toolbox():
    return Toolbox(QlooClient("demo", base_url="https://demo.invalid", transport=fake_qloo.transport()))


def test_scripted_agent_produces_complete_cited_brief():
    events = []
    out = BridgeScoutAgent(toolbox(), emit=events.append).run(REQ)
    assert out["planner"] == "scripted"
    assert out["lead_market"]["city"] in {m["city"] for m in out["markets"]}
    scores = [m["score"] for m in out["markets"]]
    assert scores == sorted(scores, reverse=True)
    lead = out["lead_market"]["city"]
    assert {"place", "brand", "artist", "podcast"} <= set(out["partners"][lead])
    assert out["hotspots"][lead]
    ids = {e["id"] for e in out["evidence"]}
    for a in out["actions"]:
        assert set(a["evidence"]) <= ids, a  # every action cites a real request
    assert any(e["type"] == "tool_call" for e in events)
    # own references never recommended back as partners
    own = {r["entity_id"] for r in out["references"]}
    assert not own & {p["entity_id"] for p in out["partners"][lead]["brand"]}


def test_unresolvable_reference_is_reported():
    req = dict(REQ, references=[{"name": "zzunknown", "type": "brand"}, {"name": "Sanrio", "type": "brand"}])
    out = BridgeScoutAgent(toolbox()).run(req)
    assert out["unresolved"][0]["input"] == "zzunknown"
    assert [r["name"] for r in out["references"]] == ["Sanrio"]


def fake_llm(script):
    """OpenAI-compatible endpoint replaying a scripted list of assistant messages."""
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        msg = script.pop(0) if script else {"role": "assistant", "content": "Memo citing [E1]."}
        return httpx.Response(200, json={"choices": [{"message": msg}]})

    return LLMClient("x", "https://llm.invalid/v1", "m", transport=httpx.MockTransport(handler)), calls


def tc(i, name, args):
    return {"id": f"c{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def test_llm_planner_drives_tools_and_writes_memo():
    script = [
        {"role": "assistant", "content": "Resolving.", "tool_calls": [tc(1, "resolve_references", {"references": REQ["references"]})]},
        {"role": "assistant", "content": None, "tool_calls": [tc(2, "score_markets", {"cities": ["Tokyo", "Paris"]}), tc(3, "bogus_tool", {})]},
        {"role": "assistant", "content": None, "tool_calls": [tc(4, "finish", {"reason": "ok"})]},
    ]
    llm, calls = fake_llm(script)
    out = BridgeScoutAgent(toolbox(), llm=llm).run(REQ)
    assert out["planner"] == "llm"
    assert {m["city"] for m in out["markets"]} == {"Tokyo", "Paris"}  # model's choice respected
    assert out["narrative_source"] == "llm" and "[E1]" in out["narrative"]
    assert calls[0]["tools"]  # tools advertised to the model
    tool_msgs = [m for m in calls[2]["messages"] if m["role"] == "tool"]
    assert any("unknown tool" in m["content"] for m in tool_msgs)


def test_llm_failure_falls_back_to_scripted():
    def boom(request):
        return httpx.Response(500, json={})

    llm = LLMClient("x", "https://llm.invalid/v1", "m", transport=httpx.MockTransport(boom))
    events = []
    out = BridgeScoutAgent(toolbox(), llm=llm, emit=events.append).run(REQ)
    assert out["lead_market"] and out["narrative_source"] == "template"
    assert any(e["type"] == "warning" for e in events)
