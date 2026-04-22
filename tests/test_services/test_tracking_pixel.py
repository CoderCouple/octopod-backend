from app.outreach.tracking_pixel import TRACKING_GIF, inject_tracking_pixel


def test_inject_before_body_close():
    html = "<html><body><p>Content</p></body></html>"
    result = inject_tracking_pixel(html, "track123", "https://t.example.com")
    assert "/t/track123.png" in result
    assert result.index("/t/track123.png") < result.index("</body>")


def test_inject_without_body_tag():
    html = "<p>Content</p>"
    result = inject_tracking_pixel(html, "track123", "https://t.example.com")
    assert "/t/track123.png" in result
    assert result.endswith('style="display:none;border:0;" />')


def test_tracking_gif_is_valid():
    assert TRACKING_GIF.startswith(b"GIF89a")
    assert len(TRACKING_GIF) > 0
