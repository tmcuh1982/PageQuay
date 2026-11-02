"""Un refus de format garde la page exacte dans un artefact privé borné."""

import hashlib
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from pagequay.errors import PQError
from pagequay.search import SearchService


class SearchParseProofTests(unittest.TestCase):
    def test_unrecognized_page_is_preserved_with_existing_project_scope(self):
        artifacts = MagicMock()
        artifacts.put.return_value = {"artifact_id": "a" * 32}
        browser = SimpleNamespace(artifacts=artifacts)
        service = SearchService(browser, MagicMock(), MagicMock())
        project = {"id": "fixture", "slug": "fixture"}
        html = "<html><body>Format inconnu, sans résultat interprétable</body></html>"
        with self.assertRaises(PQError) as caught:
            service.parse_page(project, None, None, "duckduckgo", html, 10)
        artifacts.put.assert_called_once_with(project, html.encode(), "text/html", "content:read")
        error = caught.exception
        self.assertEqual("UPSTREAM_CHANGED", error.code)
        self.assertEqual("a" * 32, error.details["artifact_id"])
        self.assertEqual(
            hashlib.sha256(html.encode()).hexdigest(), error.details["artifact_sha256"]
        )
        self.assertNotIn(html, str(error.details))

    def test_storage_failure_preserves_original_refusal(self):
        artifacts = MagicMock()
        artifacts.put.side_effect = PQError("RATE_LIMITED", "fixture quota", 429)
        service = SearchService(SimpleNamespace(artifacts=artifacts), MagicMock(), MagicMock())
        with self.assertRaises(PQError) as caught:
            service.parse_page(
                {"id": "fixture"}, None, None, "duckduckgo", "<html>unknown</html>", 10
            )
        self.assertEqual("UPSTREAM_CHANGED", caught.exception.code)
        self.assertFalse(caught.exception.details["diagnostic_available"])
        self.assertEqual("PQError", caught.exception.details["diagnostic_error_type"])

    def test_recognized_empty_page_creates_no_diagnostic_artifact(self):
        browser = SimpleNamespace(artifacts=MagicMock())
        service = SearchService(browser, MagicMock(), MagicMock())
        self.assertEqual(
            [],
            service.parse_page(
                {"id": "fixture"}, None, None, "duckduckgo", "<html>No results</html>", 10
            ),
        )
        browser.artifacts.put.assert_not_called()


if __name__ == "__main__":
    unittest.main()
