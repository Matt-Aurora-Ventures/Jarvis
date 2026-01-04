"""Tokenized equities universe ingestion and normalization."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE_PATH = ROOT / "data" / "trader" / "universe" / "tokenized_equities.json"
CACHE_DIR = ROOT / "data" / "trader" / "tokenized_equities_cache"

XSTOCKS_BASE = "https://xstocks.fi"
PRESTOCKS_BASE = "https://prestocks.com"


@dataclass
class EquityToken:
    symbol: str
    name: str
    issuer: str
    mint_address: str
    underlying_ticker: str
    asset_type: str
    venues: List[str]
    quote_currencies: List[str]
    liquidity_usd: float
    volume_24h_usd: float
    estimated_spread_bps: float
    fees_bps: float
    compliance: str
    provenance: Dict[str, Any]
    confidence: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _fetch_text(url: str, *, timeout: int = 20, retries: int = 5) -> Optional[str]:
    headers = {"User-Agent": "Mozilla/5.0 (LifeOS)"}  # avoid TLS reset
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException:
            time.sleep(0.5 * (attempt + 1))
    return None


def _fetch_json(url: str, *, timeout: int = 20, retries: int = 5) -> Optional[Dict[str, Any]]:
    headers = {"User-Agent": "Mozilla/5.0 (LifeOS)"}
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            time.sleep(0.5 * (attempt + 1))
        except ValueError:
            return None
    return None


def _cache_path(name: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / name


def _save_cache(name: str, payload: Dict[str, Any]) -> None:
    _write_json(_cache_path(name), payload)


def _load_cache(name: str) -> Optional[Dict[str, Any]]:
    payload = _load_json(_cache_path(name))
    if isinstance(payload, dict):
        return payload
    return None


def _extract_build_id(html: str) -> Optional[str]:
    match = re.search(r'\"buildId\"\\s*:\\s*\"([^\"]+)\"', html)
    if match:
        return match.group(1)
    return None


def _extract_next_data(html: str) -> Optional[Dict[str, Any]]:
    match = re.search(r'<script[^>]+id=\"__NEXT_DATA__\"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def fetch_xstocks_universe(*, force_refresh: bool = False) -> Tuple[List[EquityToken], List[str]]:
    warnings: List[str] = []
    cached = _load_cache("xstocks.json")
    if cached and not force_refresh and time.time() - cached.get("updated_at", 0) < 3600:
        items = cached.get("items", [])
        return [_from_raw(item) for item in items], cached.get("warnings", [])

    products_html = _fetch_text(f"{XSTOCKS_BASE}/products")
    if not products_html:
        return [], ["xstocks: failed to load products page"]

    payload = _extract_next_data(products_html)
    if not payload:
        return [], ["xstocks: __NEXT_DATA__ missing"]

    build_id = payload.get("buildId")
    if not build_id:
        warnings.append("xstocks: buildId missing from __NEXT_DATA__")
    data = None
    if build_id:
        data = _fetch_json(f"{XSTOCKS_BASE}/_next/data/{build_id}/products.json")

    products = []
    if isinstance(data, dict):
        products = data.get("pageProps", {}).get("products", []) or []
    if not products:
        products = payload.get("props", {}).get("pageProps", {}).get("products", []) or []

    items: List[EquityToken] = []
    for product in products:
        if not isinstance(product, dict):
            continue
        addresses = product.get("addresses") or {}
        solana_mint = addresses.get("solana")
        if not solana_mint:
            continue
        symbol = str(product.get("symbol") or "").upper()
        underlying = symbol.rstrip("X").rstrip("x")
        items.append(
            EquityToken(
                symbol=symbol,
                name=product.get("name") or symbol,
                issuer="xstocks",
                mint_address=solana_mint,
                underlying_ticker=underlying,
                asset_type="stock",
                venues=["solana_dex"],
                quote_currencies=["USDC", "SOL"],
                liquidity_usd=0.0,
                volume_24h_usd=0.0,
                estimated_spread_bps=40.0,
                fees_bps=5.0,
                compliance="unknown",
                provenance={"source": "xstocks_products", "url": f"{XSTOCKS_BASE}/products"},
                confidence="high",
            )
        )

    if not items:
        warnings.append("xstocks: no products parsed")

    snapshot = {
        "updated_at": time.time(),
        "items": [item.to_dict() for item in items],
        "warnings": warnings,
    }
    _save_cache("xstocks.json", snapshot)
    return items, warnings


def _prestocks_sitemap_urls() -> List[str]:
    xml = _fetch_text(f"{PRESTOCKS_BASE}/sitemap.xml")
    if not xml:
        return []
    return re.findall(r"<loc>(.*?)</loc>", xml)

def _extract_solscan_mints(html: str) -> List[str]:
    return re.findall(r"solscan.io/token/([1-9A-HJ-NP-Za-km-z]{32,44})", html)

def _fetch_prestocks_products_mints() -> Tuple[List[str], List[str]]:
    warnings: List[str] = []
    html = _fetch_text(f"{PRESTOCKS_BASE}/products")
    if not html:
        return [], ["prestocks: failed to load products page"]
    mints = _extract_solscan_mints(html)
    base58_candidates = re.findall(r"[1-9A-HJ-NP-Za-km-z]{32,44}", html)
    combined = sorted(set(mints + base58_candidates))
    if not combined:
        warnings.append("prestocks: no token candidates found on products page")
    return combined, warnings


def _extract_prestocks_mint(html: str) -> Optional[str]:
    matches = re.findall(r"solscan.io/token/([1-9A-HJ-NP-Za-km-z]{32,44})", html)
    if matches:
        return matches[0]
    return None


def _guess_symbol_from_url(url: str) -> str:
    slug = url.rstrip("/").split("/")[-1]
    return slug.upper()


def fetch_prestocks_universe(*, force_refresh: bool = False) -> Tuple[List[EquityToken], List[str]]:
    warnings: List[str] = []
    cached = _load_cache("prestocks.json")
    if cached and not force_refresh and time.time() - cached.get("updated_at", 0) < 3600:
        items = cached.get("items", [])
        return [_from_raw(item) for item in items], cached.get("warnings", [])

    urls = _prestocks_sitemap_urls()
    if not urls:
        return [], ["prestocks: sitemap unavailable"]

    excluded = {PRESTOCKS_BASE, f"{PRESTOCKS_BASE}/", f"{PRESTOCKS_BASE}/products"}
    product_pages = []
    for url in urls:
        if url in excluded:
            continue
        path = url.replace(PRESTOCKS_BASE, "")
        if path in ("", "/"):
            continue
        if path.startswith("/products"):
            continue
        product_pages.append(url)
    items: List[EquityToken] = []
    products_mints, products_warnings = _fetch_prestocks_products_mints()
    warnings.extend(products_warnings)
    for mint in products_mints:
        items.append(
            EquityToken(
                symbol="UNKNOWN",
                name="UNKNOWN",
                issuer="prestocks",
                mint_address=mint,
                underlying_ticker="UNKNOWN",
                asset_type="pre_ipo",
                venues=["solana_dex"],
                quote_currencies=["USDC", "SOL"],
                liquidity_usd=0.0,
                volume_24h_usd=0.0,
                estimated_spread_bps=80.0,
                fees_bps=10.0,
                compliance="unknown",
                provenance={"source": "prestocks_products", "url": f"{PRESTOCKS_BASE}/products"},
                confidence="low",
            )
        )

    for url in product_pages:
        html = _fetch_text(url)
        if not html:
            warnings.append(f"prestocks: failed to load {url}")
            continue
        mint = _extract_prestocks_mint(html)
        if not mint:
            warnings.append(f"prestocks: mint missing for {url}")
            continue
        symbol = _guess_symbol_from_url(url)
        items.append(
            EquityToken(
                symbol=symbol,
                name=symbol,
                issuer="prestocks",
                mint_address=mint,
                underlying_ticker=symbol,
                asset_type="pre_ipo",
                venues=["solana_dex"],
                quote_currencies=["USDC", "SOL"],
                liquidity_usd=0.0,
                volume_24h_usd=0.0,
                estimated_spread_bps=80.0,
                fees_bps=10.0,
                compliance="unknown",
                provenance={"source": "prestocks_page", "url": url},
                confidence="medium",
            )
        )

    snapshot = {
        "updated_at": time.time(),
        "items": [item.to_dict() for item in items],
        "warnings": warnings,
    }
    _save_cache("prestocks.json", snapshot)
    return items, warnings


def refresh_universe() -> Dict[str, Any]:
    xstocks_items, xstocks_warnings = fetch_xstocks_universe(force_refresh=True)
    prestocks_items, prestocks_warnings = fetch_prestocks_universe(force_refresh=True)

    items = xstocks_items + prestocks_items
    warnings = xstocks_warnings + prestocks_warnings

    snapshot = {
        "updated_at": time.time(),
        "items": [item.to_dict() for item in items],
        "warnings": warnings,
        "sources": ["xstocks", "prestocks"],
    }
    _write_json(UNIVERSE_PATH, snapshot)
    return snapshot


def load_universe() -> Dict[str, Any]:
    payload = _load_json(UNIVERSE_PATH)
    if isinstance(payload, dict) and payload.get("items"):
        return payload
    return refresh_universe()


def validate_universe(snapshot: Dict[str, Any]) -> Tuple[bool, List[str]]:
    issues: List[str] = []
    items = snapshot.get("items", [])
    if not isinstance(items, list) or not items:
        issues.append("no_items")
        return False, issues
    for item in items:
        for field in ("symbol", "mint_address", "issuer"):
            if not item.get(field):
                issues.append(f"missing_{field}")
                break
    return len(issues) == 0, issues


def _from_raw(raw: Dict[str, Any]) -> EquityToken:
    return EquityToken(
        symbol=raw.get("symbol", ""),
        name=raw.get("name", ""),
        issuer=raw.get("issuer", ""),
        mint_address=raw.get("mint_address", ""),
        underlying_ticker=raw.get("underlying_ticker", raw.get("symbol", "")),
        asset_type=raw.get("asset_type", "stock"),
        venues=list(raw.get("venues", [])),
        quote_currencies=list(raw.get("quote_currencies", [])),
        liquidity_usd=float(raw.get("liquidity_usd", 0.0)),
        volume_24h_usd=float(raw.get("volume_24h_usd", 0.0)),
        estimated_spread_bps=float(raw.get("estimated_spread_bps", 0.0)),
        fees_bps=float(raw.get("fees_bps", 0.0)),
        compliance=raw.get("compliance", "unknown"),
        provenance=dict(raw.get("provenance", {})),
        confidence=raw.get("confidence", "unknown"),
    )
