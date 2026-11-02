"""Pages vides : typographie équivalente, protections et résultats inchangés."""

import pytest

from pagequay.errors import PQError
from pagequay.search import ADAPTERS, ddg_continuation


@pytest.mark.parametrize(
    "message",
    [
        "Aucun résultat trouvé",
        "Aucun\u00a0résultat trouvé",
        "Aucun\u202frésultat trouvé",
        "Aucun\n  résultat trouvé",
        "Aucun re\u0301sultat trouvé",
        "No\u00a0results found",
        "No\nresults found",
        "NO MORE RESULTS",
    ],
)
def test_empty_notice_and_pagination_accept_equivalent_typography(message):
    html = f'<html><body><div class="no-results">{message}</div></body></html>'
    assert ADAPTERS["duckduckgo"].parse(html, 10) == []
    assert ddg_continuation(html, "https://html.duckduckgo.com/html/", "robots") == (
        None,
        False,
        "exhausted",
    )


@pytest.mark.parametrize(
    "html,code",
    [
        ("<p>Search layout unknown</p>", "UPSTREAM_CHANGED"),
        ('<div data-pq-challenge="true">Aucun résultat</div>', "CHALLENGE_REQUIRED"),
        ("<p>Too many requests. Aucun résultat</p>", "RATE_LIMITED"),
    ],
)
def test_unknown_page_and_human_or_quota_controls_remain_errors(html, code):
    with pytest.raises(PQError) as exc:
        ADAPTERS["duckduckgo"].parse(html, 10)
    assert exc.value.code == code


def test_result_text_is_not_rewritten_by_notice_normalization():
    title = "Modèle\u00a0robot e\u0301"
    snippet = "Charge\u202futile\n5 kg"
    html = (
        '<div class="result"><a class="result__a" href="https://example.org/model">'
        + title
        + '</a><span class="result__snippet">'
        + snippet
        + "</span></div>"
    )
    row = ADAPTERS["duckduckgo"].parse(html, 10)[0]
    assert row["title"] == title
    assert row["snippet"] == snippet
