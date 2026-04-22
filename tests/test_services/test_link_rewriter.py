from app.outreach.link_rewriter import rewrite_links


def test_rewrite_basic_links():
    html = '<a href="https://example.com">Click</a>'
    result, link_map = rewrite_links(html, "track123", "https://t.example.com")
    assert "https://example.com" not in result
    assert "/c/track123/" in result
    assert len(link_map) == 1
    assert list(link_map.values())[0] == "https://example.com"


def test_skip_mailto_links():
    html = '<a href="mailto:test@example.com">Email</a>'
    result, link_map = rewrite_links(html, "track123", "https://t.example.com")
    assert "mailto:test@example.com" in result
    assert len(link_map) == 0


def test_skip_tel_links():
    html = '<a href="tel:+1234567890">Call</a>'
    result, link_map = rewrite_links(html, "track123", "https://t.example.com")
    assert "tel:+1234567890" in result
    assert len(link_map) == 0


def test_skip_anchor_links():
    html = '<a href="#section">Jump</a>'
    result, link_map = rewrite_links(html, "track123", "https://t.example.com")
    assert "#section" in result
    assert len(link_map) == 0


def test_multiple_links():
    html = (
        '<a href="https://one.com">One</a>'
        '<a href="https://two.com">Two</a>'
        '<a href="mailto:x@y.com">Mail</a>'
    )
    result, link_map = rewrite_links(html, "track123", "https://t.example.com")
    assert len(link_map) == 2
    assert "https://one.com" in link_map.values()
    assert "https://two.com" in link_map.values()


def test_skip_template_vars():
    html = '<a href="{{ unsubscribe_url }}">Unsub</a>'
    result, link_map = rewrite_links(html, "track123", "https://t.example.com")
    assert "{{ unsubscribe_url }}" in result
    assert len(link_map) == 0
