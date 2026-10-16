from pagequay.main import create_app
from pagequay.settings import Settings


def test_all_client_operations_document_required_bearer_auth():
    schema = create_app(Settings()).openapi()
    assert schema["components"]["securitySchemes"]["BearerAuth"]["scheme"] == "bearer"
    for path, methods in schema["paths"].items():
        if path.startswith("/v1/"):
            for operation in methods.values():
                assert operation["security"] == [{"BearerAuth": []}]
    assert "security" not in schema["paths"]["/health/live"]["get"]


def test_structured_content_options_are_documented():
    schema = create_app(Settings()).openapi()
    operation = schema["paths"]["/v1/projects/{slug}/tabs/{tab_id}/content"]["get"]
    params = {item["name"]: item["schema"] for item in operation["parameters"]}
    assert "structured" in params["format"]["enum"]
    assert params["include_dom"]["type"] == "boolean"
    assert params["include_dom"]["default"] is False


def test_versioned_public_client_contract_on_api_listener(client):
    response = client.get("http://127.0.0.1:8766/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["version"] == "1.1.0"
    assert all(path.startswith(("/v1/", "/health/")) for path in schema["paths"])
    search = schema["paths"]["/v1/projects/{slug}/search"]["post"]
    assert any(p["name"] == "idempotency-key" and p["in"] == "header" for p in search["parameters"])
    assert "Retry-After" in search["responses"]["429"]["headers"]
    assert "cursor" in schema["components"]["schemas"]["Search"]["properties"]
    fields = schema["components"]["schemas"]["Search"]["properties"]
    assert "pl-pl" in fields["region"]["enum"]
    assert fields["time_range"]["enum"] == ["any", "day", "week", "month", "year"]
    result = schema["components"]["schemas"]["SearchResult"]["properties"]
    for name in (
        "next_cursor",
        "has_more",
        "requested_count",
        "returned_count",
        "stop_reason",
        "engine",
    ):
        assert name in result


def test_acquisition_and_typed_frame_diagnostics_contract():
    schema = create_app(Settings()).openapi()
    fields = schema["components"]["schemas"]["Navigate"]["properties"]
    assert fields["allow_redirects"]["default"] is True
    assert fields["respect_robots"]["default"] is False
    assert "expected_url" in fields
    for path in ("/v1/projects/{slug}/tabs", "/v1/projects/{slug}/tabs/{tab_id}/navigate"):
        params = schema["paths"][path]["post"]["parameters"]
        assert any(p["name"] == "idempotency-key" for p in params)
    params = schema["paths"]["/v1/projects/{slug}/tabs/{tab_id}/content"]["get"]["parameters"]
    assert any(p["name"] == "expected_url" for p in params)
    assert (
        "WORLD_NOT_FOUND"
        in schema["components"]["schemas"]["FrameDiagnostic"]["properties"]["cause"]["enum"]
    )
    assert "navigation_id" in schema["components"]["schemas"]["NavigationMetadata"]["properties"]
    assert "StructuredSnapshot" in schema["components"]["schemas"]


def test_cookie_action_and_persistent_policy_contract():
    schema = create_app(Settings()).openapi()
    assert (
        "validate_cookies"
        in schema["components"]["schemas"]["Action"]["properties"]["type"]["enum"]
    )
    policy = schema["components"]["schemas"]["CookiePolicy"]["properties"]
    assert {"type": "null"} in policy["choice"]["anyOf"]
    assert policy["timeout_ms"]["maximum"] == 10000
    assert set(schema["paths"]["/v1/projects/{slug}/cookie-policy"]) == {"get", "put"}


def test_checked_in_contract_matches_public_listener(client):
    import json
    from pathlib import Path

    documented = json.loads((Path(__file__).parents[1] / "docs/openapi.json").read_text())
    public = client.get("http://127.0.0.1:8766/openapi.json")
    assert public.status_code == 200
    assert documented == public.json()
