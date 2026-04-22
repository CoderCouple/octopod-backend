"""Tracking pixel injection for email open tracking."""

# 1x1 transparent GIF bytes
TRACKING_GIF = (
    b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00"
    b"\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x00\x00\x00\x00"
    b"\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02"
    b"\x44\x01\x00\x3b"
)


def inject_tracking_pixel(html: str, tracking_id: str, base_url: str) -> str:
    """Inject a 1x1 tracking pixel image tag before </body>.

    Args:
        html: The email body HTML.
        tracking_id: Unique tracking identifier for this message.
        base_url: Base URL for the tracking server (e.g. https://track.example.com).

    Returns:
        Modified HTML with tracking pixel injected.
    """
    pixel_url = f"{base_url.rstrip('/')}/t/{tracking_id}.png"
    pixel_tag = (
        f'<img src="{pixel_url}" width="1" height="1" '
        f'alt="" style="display:none;border:0;" />'
    )

    if "</body>" in html.lower():
        # Insert before closing body tag
        idx = html.lower().rfind("</body>")
        return html[:idx] + pixel_tag + html[idx:]
    else:
        # Append to the end
        return html + pixel_tag
