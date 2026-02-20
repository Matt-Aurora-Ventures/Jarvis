from playwright.sync_api import sync_playwright
from pathlib import Path
import json
import os
import re
import sys
import time


def main() -> int:
    base_url = os.environ.get("JARVIS_URL", "http://127.0.0.1:3001").rstrip("/")
    out_dir = Path(".jarvis-cache") / "playwright-smoke"
    out_dir.mkdir(parents=True, exist_ok=True)

    logs = []
    route_events = []

    def log(msg: str) -> None:
        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] {msg}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()

        page.on(
            "console",
            lambda m: logs.append({"type": m.type, "text": m.text, "location": str(m.location)}),
        )
        page.on("pageerror", lambda e: logs.append({"type": "pageerror", "text": str(e)}))

        def snap(name: str) -> None:
            page.screenshot(path=str(out_dir / name), full_page=True)

        def capture_exec_markers(label: str) -> None:
            try:
                markers = page.evaluate(
                    """() => {
                      const text = (document.body?.innerText || '').split('\\n');
                      return text
                        .map((line) => String(line || '').trim())
                        .filter((line) => line.length > 0)
                        .filter((line) => /(AUTO_STOP_|Run monitor unavailable|SNIPE|SL\\/TP|ExecutionLog|Swap failed|Swap submitted|Insufficient signer SOL)/i.test(line))
                        .slice(0, 12);
                    }""",
                )
            except Exception:
                markers = []
            route_events.append(
                {
                    "label": label,
                    "url": page.url,
                    "markers": markers,
                }
            )

        def goto(path: str, shot: str) -> None:
            url = f"{base_url}{path}"
            log(f"goto {url}")
            page.goto(url)
            # This app has live polling; "networkidle" may never happen.
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_selector("header")
            page.wait_for_timeout(500)
            snap(shot)
            capture_exec_markers(f"goto:{path}")

        goto("/", "01-home.png")

        # If the Early Beta modal is present (fresh profile / cleared storage),
        # acknowledge it so it doesn't block navigation.
        try:
            modal_title = page.get_by_role("heading", name=re.compile(r"(Quick heads up|Read this before trading)", re.I))
            if modal_title.is_visible(timeout=1200):
                log("acknowledge Early Beta modal")
                accepted = False
                for label in [
                    r"I understand the risk for this session",
                    r"I understand",
                    r"I accept",
                ]:
                    btn = page.get_by_role("button", name=re.compile(label, re.I))
                    if btn.count() > 0:
                        btn.first.click()
                        accepted = True
                        break

                if not accepted:
                    # Fallback close if accept copy changed.
                    close_btn = page.get_by_role("button", name=re.compile(r"(Close|×)", re.I))
                    if close_btn.count() > 0:
                        close_btn.first.click()

                page.wait_for_timeout(700)
                snap("01b-beta-ack.png")
        except Exception:
            pass

        # Route switching via nav links (the user reported they couldn't switch pages).
        for href, shot in [
            ("/bags-intel", "02-bags-intel.png"),
            ("/bags-graduations", "03-bags-graduations.png"),
            ("/bags-sniper", "04-bags-sniper.png"),
            ("/", "05-home-again.png"),
        ]:
            log(f"click nav {href}")
            page.locator(f'a[href="{href}"]').first.click()
            page.wait_for_url(re.compile(rf".*{re.escape(href)}$"))
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_selector("header")
            page.wait_for_timeout(500)
            snap(shot)
            capture_exec_markers(f"nav:{href}")

        # Parse Data modal should open and close without breaking routing.
        log("open Parse Data modal")
        try:
            parse_btn = page.get_by_role("button", name=re.compile(r"^Parse Data$", re.I))
            if parse_btn.count() == 0:
                parse_btn = page.get_by_role("button", name=re.compile(r"Open parse data dialog", re.I))
            if parse_btn.count() > 0:
                parse_btn.first.click()
                page.wait_for_selector("text=Parse Data (reset this browser instance)", timeout=6000)
                snap("06-parse-modal.png")
                cancel_btn = page.get_by_role("button", name=re.compile(r"^Cancel$", re.I))
                if cancel_btn.count() > 0:
                    cancel_btn.first.click()
                page.wait_for_timeout(250)
                capture_exec_markers("post-parse-close")
            else:
                log("Parse Data control not found; skipping modal check")
        except Exception as exc:
            log(f"Parse Data modal check skipped: {exc}")

        # Dump logs
        (out_dir / "console.json").write_text(json.dumps(logs, indent=2), encoding="utf-8")
        (out_dir / "events.json").write_text(json.dumps(route_events, indent=2), encoding="utf-8")
        browser.close()

    # Treat page errors as failures, but ignore common third-party iframe noise.
    ignored_page_errors = {
        "Failed to fetch",  # frequently thrown by third-party chart embeds (DexScreener iframe)
    }
    page_errors = [
        l for l in logs
        if l.get("type") == "pageerror" and (l.get("text") not in ignored_page_errors)
    ]
    if page_errors:
        log(f"FAIL: page errors detected ({len(page_errors)}). See {out_dir / 'console.json'}")
        return 2

    api_parse_warning = re.compile(
        r"(Unexpected token '<'.*not valid JSON|\[useMacroData\] Fetch failed|\[useTVScreener\] Fetch failed)",
        re.IGNORECASE,
    )
    api_warning_logs = [
        l for l in logs
        if l.get("type") in {"warning", "error"}
        and api_parse_warning.search(str(l.get("text") or ""))
    ]
    if api_warning_logs:
        log(f"FAIL: API parse/backend wiring warnings detected ({len(api_warning_logs)}). See {out_dir / 'console.json'}")
        return 3

    log(f"OK: navigation smoke test complete. Artifacts in {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
