import asyncio
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.async_api import async_playwright, ConsoleMessage, Page, Request, Response


@dataclass
class ConsoleEvent:
  kind: str
  text: str
  url: Optional[str] = None
  line: Optional[int] = None
  column: Optional[int] = None
  ts: float = 0.0


@dataclass
class NetworkEvent:
  url: str
  method: str
  status: Optional[int]
  failure: Optional[str]
  resource: Optional[str]
  ts: float = 0.0


def now_ts() -> float:
  return time.time()


async def safe_screenshot(page: Page, path: Path) -> None:
  try:
    await page.screenshot(path=str(path), full_page=True)
  except Exception:
    # best-effort
    pass


async def wait_for_app_idle(page: Page) -> None:
  # The app has live polling; "networkidle" may never happen. Use a short settle delay.
  await page.wait_for_timeout(1500)


async def click_if_visible(page: Page, selector: str, timeout_ms: int = 1500) -> bool:
  try:
    loc = page.locator(selector)
    await loc.first.wait_for(state="visible", timeout=timeout_ms)
    await loc.first.click()
    return True
  except Exception:
    return False


async def get_cloud_run_tag_url(page: Page) -> Optional[str]:
  # Discover the Cloud Run tag URL from /api/health so we can validate the backtest CORS path.
  try:
    result = await page.evaluate(
      """async () => {
        const res = await fetch('/api/health', { cache: 'no-store' });
        const json = await res.json();
        return json?.backend?.cloudRunTagUrl || null;
      }"""
    )
    if not isinstance(result, str):
      return None
    result = result.strip()
    if result.startswith("https://") and result.endswith(".a.run.app"):
      return result
    return None
  except Exception:
    return None


async def validate_backtest_cors(page: Page, tag_url: str) -> Dict[str, Any]:
  # Avoid running a full backtest from the browser (can take many minutes). We only validate:
  # - CSP allows connect-src to *.a.run.app
  # - CORS is present and does not throw in fetch for backtest endpoints
  try:
    probe = await page.evaluate(
      """async (tagUrl) => {
        const res = await fetch(`${tagUrl}/api/backtest/runs/ui-smoke-nonexistent`, { cache: 'no-store' });
        const text = await res.text();
        return { ok: res.ok, status: res.status, ct: res.headers.get('content-type') || '', bodyHead: text.slice(0, 140) };
      }""",
      tag_url,
    )
    return {"tagUrl": tag_url, "probe": probe}
  except Exception as e:
    return {"tagUrl": tag_url, "probeError": str(e)}


async def main() -> int:
  base_url = os.environ.get("JARVIS_BASE_URL", "https://kr8tiv.web.app").rstrip("/")
  ts = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
  out_dir = Path(os.environ.get("JARVIS_SMOKE_OUT", f"jarvis-sniper/debug/e2e-smoke-{ts}"))
  out_dir.mkdir(parents=True, exist_ok=True)

  console_events: List[ConsoleEvent] = []
  network_events: List[NetworkEvent] = []
  page_errors: List[str] = []

  def on_console(msg: ConsoleMessage) -> None:
    loc = msg.location or {}
    console_events.append(
      ConsoleEvent(
        kind=msg.type,
        text=msg.text,
        url=loc.get("url"),
        line=loc.get("lineNumber"),
        column=loc.get("columnNumber"),
        ts=now_ts(),
      )
    )

  def on_page_error(err: Exception) -> None:
    page_errors.append(str(err))

  def on_request_failed(req: Request) -> None:
    failure = None
    try:
      failure = req.failure
      if isinstance(failure, dict):
        failure = failure.get("errorText")
    except Exception:
      failure = None
    network_events.append(
      NetworkEvent(
        url=req.url,
        method=req.method,
        status=None,
        failure=str(failure) if failure else "requestfailed",
        resource=req.resource_type,
        ts=now_ts(),
      )
    )

  async def on_response(resp: Response) -> None:
    try:
      status = resp.status
      if status >= 400:
        req = resp.request
        network_events.append(
          NetworkEvent(
            url=resp.url,
            method=req.method,
            status=status,
            failure=None,
            resource=req.resource_type,
            ts=now_ts(),
          )
        )
    except Exception:
      pass

  async with async_playwright() as p:
    browser = await p.chromium.launch(headless=True)
    context = await browser.new_context(viewport={"width": 1440, "height": 900})
    page = await context.new_page()

    page.on("console", on_console)
    page.on("pageerror", on_page_error)
    page.on("requestfailed", on_request_failed)
    page.on("response", on_response)

    routes = [
      "/",
      "/bags-sniper",
      "/tradfi-sniper",
      "/bags-intel",
      "/bags-graduations",
    ]

    for route in routes:
      url = f"{base_url}{route}"
      await page.goto(url, wait_until="domcontentloaded", timeout=90_000)
      await wait_for_app_idle(page)
      await safe_screenshot(page, out_dir / f"page-{route.strip('/').replace('/', '_') or 'home'}.png")

      # Open and close Reset Auto modal if present (read-only).
      if await click_if_visible(page, "text=Reset Auto", timeout_ms=1200):
        await page.wait_for_timeout(400)
        await safe_screenshot(page, out_dir / f"modal-reset-auto-{route.strip('/').replace('/', '_') or 'home'}.png")
        await click_if_visible(page, "text=Cancel", timeout_ms=1200)
        await page.wait_for_timeout(250)

    tag_url = await get_cloud_run_tag_url(page)
    backtest_probe: Dict[str, Any] = {}
    if tag_url:
      backtest_probe = await validate_backtest_cors(page, tag_url)

    await browser.close()

  # Summarize into JSON + a readable markdown.
  payload = {
    "baseUrl": base_url,
    "routes": routes,
    "generatedAtUtc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "console": [asdict(e) for e in console_events],
    "pageErrors": page_errors,
    "network": [asdict(e) for e in network_events],
    "backtestProbe": backtest_probe,
  }

  (out_dir / "smoke-results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

  # Keep markdown short: only surface errors + warnings + failed requests.
  console_bad = [e for e in console_events if e.kind in ("error", "warning")]
  net_bad = [e for e in network_events if (e.status is not None and e.status >= 400) or e.failure]

  lines: List[str] = []
  lines.append(f"# Jarvis Sniper Production Smoke ({payload['generatedAtUtc']})")
  lines.append("")
  lines.append(f"- Base: `{base_url}`")
  lines.append(f"- Output: `{out_dir}`")
  lines.append("")

  lines.append("## Backtest CORS Probe")
  if backtest_probe:
    lines.append("```json")
    lines.append(json.dumps(backtest_probe, indent=2))
    lines.append("```")
  else:
    lines.append("- No Cloud Run tag URL discovered from `/api/health`.")
  lines.append("")

  lines.append("## Page Errors")
  if page_errors:
    for e in page_errors[:20]:
      lines.append(f"- `{e}`")
  else:
    lines.append("- None")
  lines.append("")

  lines.append("## Console Warnings/Errors")
  if console_bad:
    for e in console_bad[:40]:
      loc = f"{e.url}:{e.line}:{e.column}" if e.url else ""
      lines.append(f"- `{e.kind}` {loc} {e.text}")
  else:
    lines.append("- None")
  lines.append("")

  lines.append("## Network Failures (>=400 or requestfailed)")
  if net_bad:
    for e in net_bad[:60]:
      st = f"status={e.status}" if e.status is not None else ""
      fl = f"failure={e.failure}" if e.failure else ""
      lines.append(f"- `{e.method}` {st} {fl} `{e.url}`")
  else:
    lines.append("- None")
  lines.append("")

  (out_dir / "smoke-results.md").write_text("\n".join(lines), encoding="utf-8")
  return 0


if __name__ == "__main__":
  raise SystemExit(asyncio.run(main()))

