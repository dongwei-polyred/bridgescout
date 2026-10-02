import httpx
import pytest

from bridgescout.qloo import EvidenceLog, QlooClient, QlooError, urn


def recording_client(responses):
    seen = []

    def handler(request):
        seen.append(request)
        status, body = responses.pop(0)
        return httpx.Response(status, json=body)

    return QlooClient("k-123", transport=httpx.MockTransport(handler), max_retries=1), seen


def test_request_shape_matches_hackathon_guide():
    client, seen = recording_client([(200, {"results": {"entities": [{"entity_id": "A", "query": {"affinity": 0.9}}]}})])
    log = EvidenceLog()
    client.insights({"filter.type": urn("brand"), "signal.interests.entities": ["A", "B"], "take": 3}, log, "t")
    req = seen[0]
    assert req.method == "GET"
    assert str(req.url).startswith("https://hackathon.api.qloo.com/v2/insights?")
    assert req.headers["X-Api-Key"] == "k-123"
    assert "authorization" not in req.headers
    assert req.url.params["signal.interests.entities"] == "A,B"
    assert log.items[0].id == "E1" and log.items[0].result_count == 1
    assert "k-123" not in str(log.items[0].as_dict())  # key never in evidence


def test_cache_avoids_duplicate_calls():
    client, seen = recording_client([(200, {"results": []})])
    client.search("Pop Mart", types=[urn("brand")])
    client.search("Pop Mart", types=[urn("brand")])
    assert len(seen) == 1


def test_retries_on_429_then_raises_on_401():
    client, seen = recording_client([(429, {}), (200, {"results": []})])
    assert client.search("x") == []
    assert len(seen) == 2
    client2, _ = recording_client([(401, {"error": "No API key found in request"})])
    with pytest.raises(QlooError) as e:
        client2.search("y")
    assert e.value.status == 401 and not e.value.retryable


def test_rejects_unsupported_types_and_missing_filter_type():
    with pytest.raises(ValueError):
        urn("music")
    client, _ = recording_client([])
    with pytest.raises(ValueError):
        client.insights({"take": 1})
