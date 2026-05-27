"""Shared pytest fixtures."""

from __future__ import annotations

import json
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import pytest


@pytest.fixture
def sample_config() -> dict:
    """Minimal valid config dict."""
    return {
        "url": "https://example.com",
        "consent_statement": "Testing purposes only.",
        "steps": [{"action": "navigate", "value": "https://example.com"}],
    }


@pytest.fixture
def tmp_config_file(tmp_path: Path, sample_config: dict) -> str:
    """Write sample config to a temp JSON file and return its path."""
    p = tmp_path / "config.json"
    p.write_text(json.dumps(sample_config), encoding="utf-8")
    return str(p)


@pytest.fixture
def mock_form_html() -> str:
    """HTML content for a mock form used in integration tests."""
    return """<!DOCTYPE html>
<html>
<head><title>Test Form</title></head>
<body>
<form id="application">
  <input id="fullname" name="fullname" type="text" placeholder="Full Name" />
  <input name="email" type="email" placeholder="Email" />
  <input type="tel" name="phone" placeholder="Phone number" />
  <select id="position">
    <option value="">Select...</option>
    <option value="eng">Software Engineer</option>
    <option value="pm">Product Manager</option>
  </select>
  <label><input type="checkbox" id="has_experience" /> Has experience</label>
  <div id="exp-fields" style="display:none;">
    <input id="years_experience" name="years" type="number" />
    <input id="company_name" name="company" type="text" />
  </div>
  <label><input type="checkbox" id="agree-terms" /> I agree to terms</label>
  <input type="file" id="resume" />
  <button type="submit" id="submit-btn">Submit</button>
</form>
<script>
document.getElementById('has_experience').addEventListener('change', function() {
  document.getElementById('exp-fields').style.display = this.checked ? 'block' : 'none';
});
document.getElementById('application').addEventListener('submit', function(e) {
  e.preventDefault();
  document.getElementById('application').innerHTML =
    '<div class="success-message">Application submitted!</div>' +
    '<div class="app-id">APP-2026-001</div>';
});
</script>
</body>
</html>"""


@pytest.fixture
def mock_server(mock_form_html: str, tmp_path: Path):
    """Start a local HTTP server serving the mock form."""
    html_dir = tmp_path / "www"
    html_dir.mkdir()
    (html_dir / "index.html").write_text(mock_form_html, encoding="utf-8")

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(html_dir), **kwargs)

        def log_message(self, format, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield f"http://127.0.0.1:{port}/index.html"

    server.shutdown()
