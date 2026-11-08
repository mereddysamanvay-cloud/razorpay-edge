"""Gate 7: the built app serves every route after a deploy-style refresh, the supplied logo is delivered byte-for-byte, and the palette is applied.
Skipped when the UI has not been built (run `npm run build` in web/)."""
import hashlib
import re

import pytest
from fastapi.testclient import TestClient

from api.main import app
from src.config import ROOT

DIST = ROOT / "web" / "dist"
PUBLIC_LOGO = ROOT / "web" / "public" / "razorpay-edge-logo.webp"
pytestmark = pytest.mark.skipif(not (DIST / "index.html").exists(), reason="web/dist not built")
client = TestClient(app)

ROUTES = ["/", "/new", "/a/x/overview", "/a/x/portfolio", "/a/x/queue", "/a/x/merchant/C2001", "/a/x/studio", "/a/x/actions", "/a/x/insights", "/a/x/reports", "/a/x/settings"]


@pytest.mark.parametrize("path", ROUTES)
def test_every_route_serves_the_app_on_a_direct_visit(path):
    r = client.get(path)
    assert r.status_code == 200 and "<div id=\"root\">" in r.text


def test_logo_is_served_unchanged():
    assert PUBLIC_LOGO.exists()
    r = client.get("/razorpay-edge-logo.webp")
    assert r.status_code == 200
    assert hashlib.sha256(r.content).hexdigest() == hashlib.sha256(PUBLIC_LOGO.read_bytes()).hexdigest()


def test_logo_component_never_redraws_the_logo():
    src = (ROOT / "web" / "src" / "components" / "Logo.tsx").read_text(encoding="utf-8")
    assert "razorpay-edge-logo.webp" in src and "<svg" not in src and "<path" not in src


def test_restrained_palette_and_accessibility_styles_are_in_the_build():
    css = "".join(p.read_text(encoding="utf-8", errors="ignore") for p in (DIST / "assets").glob("*.css")).lower()
    # Tailwind may emit a colour as hex or as an rgb triple, so accept either form
    for hex_, rgb in (("#355cff", "53 92 255"), ("#10213e", "16 33 62"), ("#f5f7fb", "245 247 251")):
        assert hex_ in css or rgb in css, hex_
    assert ":focus-visible" in css and "skip-link" in css


def test_no_gradient_or_decorative_ticker_on_the_welcome_page():
    welcome = (ROOT / "web" / "src" / "pages" / "Welcome.tsx").read_text(encoding="utf-8")
    assert "Ticker" not in welcome and not re.search(r"gradient", welcome)
