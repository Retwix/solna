import base64
import io

import qrcode


def qr_png_base64(url: str) -> str:
    """Return a base64-encoded PNG QR code for the given URL."""
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")
