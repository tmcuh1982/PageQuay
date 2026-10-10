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
