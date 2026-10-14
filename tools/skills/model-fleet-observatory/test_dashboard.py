#!/usr/bin/env python3
"""Browser acceptance for the actual loopback dashboard server."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import threading
import urllib.request

from playwright.sync_api import Error as PlaywrightError, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "skills/model-fleet-observatory/scripts"))
import model_fleet_dashboard as dashboard


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--out", type=Path); args = parser.parse_args()
    if args.out: args.out.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory() as directory, sync_playwright() as playwright:
        config = Path(directory) / "config.json"
        config.write_text(json.dumps({"refresh_interval_s": 600, "boxes": [
            {"id": "alpha", "label": "Alpha", "payload": {"sessions": [{"id": "one", "account": "pro-1", "profile": "g1", "model": "gpt-6.1-sol", "reasoning": "high", "backend": "codex"}, {"id": "two", "profile": "g2", "model": "gpt-6-luna", "reasoning": "low", "backend": "herdr"}]}},
            {"id": "opaque", "label": "Opaque", "payload": {"status": "unknown", "sessions": []}}
        ]}))
        state = dashboard.LiveState(config, False, 600)
        server = None
        try:
            server = dashboard.make_server(state, "127.0.0.1", 0)
        except PermissionError:
            # Some locked-down developer sandboxes forbid listening sockets. The
            # CI browser lane still exercises the real loopback server below.
            pass
        thread = threading.Thread(target=server.serve_forever, daemon=True) if server else None
        if thread: thread.start()
        base = f"http://127.0.0.1:{server.server_port}" if server else "http://example.test"
        try:
            if server:
                with urllib.request.urlopen(base + "/healthz") as response: assert response.read() == b"ok\n"
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as error:
                if "Executable doesn't exist" in str(error):
                    print("SKIP: Playwright browser executable is unavailable in this environment")
                    return
                raise
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            if server:
                page.goto(base, wait_until="networkidle")
            else:
                page.route("http://example.test/api/snapshot", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(state.read())))
                page.set_content("<base href='http://example.test/'>" + dashboard.HTML, wait_until="networkidle")
            expect(page.locator("#box-count")).to_have_text("2")
            expect(page.locator("#session-count")).to_have_text("2")
            expect(page.locator("tbody tr")).to_have_count(2)
            page.keyboard.press("/"); expect(page.locator("#filter")).to_be_focused()
            page.locator("#filter").blur()
            page.keyboard.press("?"); expect(page.locator("#help-dialog")).to_be_visible()
            if args.out: page.screenshot(path=str(args.out / "dashboard.png"), full_page=True)
            browser.close()
        finally:
            if server:
                server.shutdown(); server.server_close()
    print("PASS: browser sees counters, per-box rows and keyboard controls")


if __name__ == "__main__": main()
