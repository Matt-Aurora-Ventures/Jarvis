from playwright.sync_api import sync_playwright
from pathlib import Path
import json
import os
import re
import time


MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)


def main() -> int:
    base_url = os.environ.get("JARVIS_URL", "http://127.0.0.1:3001").rstrip("/")
    out_dir = Path(".jarvis-cache") / "playwright-smoke-mobile"
    out_dir.mkdir(parents=True, exist_ok=True)

    logs = []
    steps = []

    def log(msg: str) -> None:
        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] {msg}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 390, "height": 844},
            user_agent=MOBILE_UA,
            is_mobile=True,
            has_touch=True,
            device_scale_factor=3,
        )
        page = ctx.new_page()

        page.on(
            "console",
            lambda m: logs.append(
                {"type": m.type, "text": m.text, "location": str(m.location)}
            ),
        )
        page.on("pageerror", lambda e: logs.append({"type": "pageerror", "text": str(e)}))

        def snap(name: str) -> None:
            page.screenshot(path=str(out_dir / name), full_page=True)

        def assert_no_horizontal_overflow(label: str) -> None:
            iw, sw, bw = page.evaluate(
                "() => [window.innerWidth, document.documentElement.scrollWidth, document.body ? document.body.scrollWidth : 0]"
            )
            iw = int(iw or 0)
            sw = int(sw or 0)
            bw = int(bw or 0)
            worst = max(sw, bw)
            if worst > iw + 2:
                snap(f"_overflow-{label}.png")
                raise RuntimeError(
                    f"Horizontal overflow detected ({label}): scrollWidth={worst}, innerWidth={iw}"
                )

        def goto(path: str, shot: str) -> None:
            url = f"{base_url}{path}"
            log(f"goto {url}")
            last_err = None
            for _attempt in range(60):
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=15_000)
                    last_err = None
                    break
                except Exception as exc:
                    last_err = exc
                    time.sleep(0.5)
            if last_err is not None:
                raise last_err
            page.wait_for_selector("header")
            page.wait_for_timeout(600)
            assert_no_horizontal_overflow(path.strip("/").replace("/", "_") or "home")
            snap(shot)
            steps.append({"step": "goto", "path": path, "url": page.url})

        def ack_beta_modal_if_present() -> None:
            # If the Early Beta modal is present (fresh profile / cleared storage),
            # acknowledge it so it doesn't block interactions.
            try:
                modal_title = page.get_by_role(
                    "heading",
                    name=re.compile(
                        r"(Quick heads up|Read this before trading)", re.I
                    ),
                )
                if not modal_title.is_visible(timeout=15_000):
                    return

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
                    close_btn = page.get_by_role(
                        "button", name=re.compile(r"(Close|×)", re.I)
                    )
                    if close_btn.count() > 0:
                        close_btn.first.click()

                page.wait_for_timeout(700)
                snap("00-beta-ack.png")
                steps.append({"step": "beta_ack", "url": page.url})
            except Exception:
                return

        def assert_mobile_tabs_present() -> None:
            tablist = page.get_by_role("tablist", name="Mobile terminal tabs")
            tablist.wait_for(timeout=6000)

        def click_mobile_tab(label: str) -> None:
            btn = page.get_by_role("tab", name=re.compile(rf"^{re.escape(label)}$", re.I))
            btn.first.click()
            page.wait_for_timeout(450)
            assert_no_horizontal_overflow(f"tab-{label.lower()}")
            steps.append({"step": "click_tab", "tab": label, "url": page.url})

        def open_wallet_modal() -> None:
            # On mobile, the header should show "Open Wallet" (no extension injection),
            # which opens the deep-link modal.
            btn = page.get_by_role(
                "button",
                name=re.compile(
                    r"(Open Wallet|Install Wallet|Connect Phantom|Connect Solflare|Connect Wallet)",
                    re.I,
                ),
            )
            modal_title = page.get_by_role("heading", name=re.compile(r"Connect Wallet", re.I))

            # Hydration can be slow on CI/old devices; retry opening the modal a few times.
            opened = False
            for _attempt in range(12):
                try:
                    btn.first.click(timeout=2000)
                except Exception:
                    pass
                try:
                    modal_title.wait_for(timeout=700)
                    opened = True
                    break
                except Exception:
                    page.wait_for_timeout(250)

            if not opened:
                snap("_wallet-modal-missing.png")
                raise RuntimeError("Wallet connect modal did not open")

            page.get_by_role("button", name=re.compile(r"Open in Phantom", re.I)).wait_for(
                timeout=6000
            )
            page.get_by_role("button", name=re.compile(r"Open in Solflare", re.I)).wait_for(
                timeout=6000
            )
            snap("wallet-modal.png")
            steps.append({"step": "open_wallet_modal", "url": page.url})

            # Close via the explicit close button (avoid clicking backdrop which might be flaky).
            close = page.get_by_role("button", name=re.compile(r"^Close$", re.I))
            if close.count() > 0:
                close.first.click()
            else:
                # Fallback: aria-label close "X"
                page.get_by_label("Close").first.click()
            page.wait_for_timeout(250)

        # Sniper (mobile terminal)
        goto("/", "01-home-mobile.png")
        ack_beta_modal_if_present()
        assert_mobile_tabs_present()
        open_wallet_modal()
        for label in ["Trade", "Positions", "Log", "Chart", "Scan"]:
            click_mobile_tab(label)
            snap(f"01-tab-{label.lower()}.png")

        # Bags sniper (mobile terminal)
        goto("/bags-sniper", "02-bags-sniper-mobile.png")
        ack_beta_modal_if_present()
        assert_mobile_tabs_present()
        for label in ["Trade", "Positions", "Log", "Chart", "Scan"]:
            click_mobile_tab(label)
            snap(f"02-bags-tab-{label.lower()}.png")

        # TradFi sniper (mobile terminal)
        goto("/tradfi-sniper", "03-tradfi-sniper-mobile.png")
        ack_beta_modal_if_present()
        assert_mobile_tabs_present()
        for label in ["Trade", "Positions", "Log", "Chart", "Scan"]:
            click_mobile_tab(label)
            snap(f"03-tradfi-tab-{label.lower()}.png")

        # Intel + graduations (non-terminal pages)
        goto("/bags-intel", "04-bags-intel-mobile.png")
        goto("/bags-graduations", "05-bags-graduations-mobile.png")

        (out_dir / "console.json").write_text(json.dumps(logs, indent=2), encoding="utf-8")
        (out_dir / "steps.json").write_text(json.dumps(steps, indent=2), encoding="utf-8")
        browser.close()

    # Treat non-ignored page errors as failures, but ignore common third-party iframe noise.
    fast_refresh_full_reload = any(
        "performing full reload" in (l.get("text") or "")
        for l in logs
        if l.get("type") in ("log", "warning", "error")
    )

    ignored_page_errors = {
        "Failed to fetch",  # frequently thrown by third-party chart embeds (DexScreener iframe)
    }
    ignored_if_fast_refresh = {
        # Dev-mode transient during Fast Refresh; not representative of prod builds.
        "Invalid or unexpected token",
        "missing ) after argument list",
    }

    page_errors = []
    for l in logs:
        if l.get("type") != "pageerror":
            continue
        txt = l.get("text") or ""
        if txt in ignored_page_errors:
            continue
        if fast_refresh_full_reload and txt in ignored_if_fast_refresh:
            continue
        page_errors.append(l)
    if page_errors:
        log(f"FAIL: page errors detected ({len(page_errors)}). See {out_dir / 'console.json'}")
        return 2

    log(f"OK: mobile smoke test complete. Artifacts in {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
