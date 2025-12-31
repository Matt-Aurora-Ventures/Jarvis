"""
Free YouTube trading intelligence module.

Scrapes channel videos, extracts trading insights, and builds backtest ideas
without paid APIs. Uses yt-dlp / youtube-transcript-api if available.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from xml.etree import ElementTree
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core import config, notes_manager, trading_pipeline


ROOT = Path(__file__).resolve().parents[1]
TRADING_DIR = ROOT / "data" / "trader" / "youtube"
STRATEGIES_FILE = ROOT / "data" / "trader" / "strategies.json"
YOUTUBE_STRATEGIES_FILE = TRADING_DIR / "strategies_youtube.json"
YOUTUBE_ACTIONS_FILE = TRADING_DIR / "youtube_actions.json"
QUEUE_FILE = TRADING_DIR / "youtube_backtest_queue.jsonl"
RESULTS_FILE = TRADING_DIR / "youtube_backtest_results.jsonl"

DEFAULT_KEYWORDS = [
    "strategy", "entry", "exit", "stop", "take profit", "risk",
    "breakout", "mean reversion", "momentum", "trend", "range",
    "support", "resistance", "liquidity", "volume", "volatility",
    "rsi", "macd", "ema", "sma", "vwap", "bollinger", "funding",
    "open interest", "order book", "market making", "arbitrage",
]

INDICATOR_MAP = {
    "rsi": ["rsi", "relative strength"],
    "macd": ["macd"],
    "sma": ["sma", "simple moving average", "moving average"],
    "ema": ["ema", "exponential moving average"],
    "vwap": ["vwap"],
    "bollinger": ["bollinger", "bands"],
    "volume": ["volume"],
    "order_book": ["order book"],
    "open_interest": ["open interest"],
    "funding": ["funding"],
}

COMMON_SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "AVAX", "ARB", "OP", "AERO", "JUP"]


@dataclass
class VideoInsight:
    video_id: str
    title: str
    url: str
    transcript_len: int
    indicators: List[str]
    keywords: List[str]
    timeframes: List[str]
    symbols: List[str]
    key_sentences: List[str]
    strategy_hypotheses: List[Dict[str, Any]]


def compile_channel_digest(
    channel_url: str,
    limit: int = 3,
    enqueue_backtests: bool = True,
    return_insights: bool = False,
    allow_yt_dlp_fallback: bool = False,
) -> Dict[str, Any]:
    """Fetch latest channel videos, compile trading insights, and enqueue backtests."""
    TRADING_DIR.mkdir(parents=True, exist_ok=True)
    youtube_ingest = _load_youtube_ingest()
    videos = _list_videos(channel_url, limit, youtube_ingest)
    if not videos:
        return {
            "channel": channel_url,
            "video_count": 0,
            "error": "Unable to list videos from channel",
        }

    insights: List[VideoInsight] = []
    for video in videos:
        data = _fetch_transcript_api(video.get("id"), video.get("url"), video.get("title", ""))
        if not data and youtube_ingest and allow_yt_dlp_fallback:
            try:
                data = youtube_ingest.fetch_transcript(video["url"], label=video["id"])
            except Exception:
                data = None
        if not data:
            continue
        transcript = data.get("transcript", "")
        if not transcript:
            continue

        symbols = _symbols_from_config()
        extracted = extract_insights(transcript, symbols=symbols)
        hypotheses = derive_strategy_hypotheses(extracted, symbols)

        insight = VideoInsight(
            video_id=data.get("video_id", video["id"]),
            title=data.get("title", video.get("title", "")),
            url=data.get("url", video["url"]),
            transcript_len=len(transcript),
            indicators=extracted["indicators"],
            keywords=extracted["keywords"],
            timeframes=extracted["timeframes"],
            symbols=extracted["symbols"],
            key_sentences=extracted["key_sentences"],
            strategy_hypotheses=hypotheses,
        )
        insights.append(insight)

        _store_video_insight(insight)
        if enqueue_backtests and hypotheses:
            enqueue_backtest_jobs(hypotheses, channel_url, insight)

    digest = _render_digest(channel_url, insights)
    note_path, summary_path, _ = notes_manager.save_note(
        topic="trading_youtube",
        content=digest,
        fmt="md",
        tags=["youtube", "trading", "research"],
        source="trading_youtube",
        metadata={"channel": channel_url, "videos": [i.video_id for i in insights]},
    )

    response: Dict[str, Any] = {
        "channel": channel_url,
        "video_count": len(insights),
        "note_path": str(note_path),
        "summary_path": str(summary_path),
    }
    if return_insights:
        response["insights"] = [_insight_to_payload(i) for i in insights]
    return response


def compile_channel_strategies(
    channel_url: str,
    limit: int = 50,
    enqueue_backtests: bool = True,
    seed_trader: bool = True,
) -> Dict[str, Any]:
    """Full pipeline: scrape channel, compile strategies, and seed trading systems."""
    result = compile_channel_digest(
        channel_url=channel_url,
        limit=limit,
        enqueue_backtests=enqueue_backtests,
        return_insights=True,
        allow_yt_dlp_fallback=False,
    )

    insights = result.get("insights", [])
    strategies = _aggregate_strategies(insights)
    actions = _build_actions(strategies)

    TRADING_DIR.mkdir(parents=True, exist_ok=True)
    with open(YOUTUBE_STRATEGIES_FILE, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "channel": channel_url,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "strategies": strategies,
            },
            handle,
            indent=2,
        )

    with open(YOUTUBE_ACTIONS_FILE, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "channel": channel_url,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "actions": actions,
            },
            handle,
            indent=2,
        )

    if seed_trader:
        _seed_trader_strategies(strategies)

    return {
        "channel": channel_url,
        "video_count": result.get("video_count", 0),
        "strategies_added": len(strategies),
        "actions_added": len(actions),
        "strategies_path": str(YOUTUBE_STRATEGIES_FILE),
        "actions_path": str(YOUTUBE_ACTIONS_FILE),
        "digest_path": result.get("note_path"),
        "error": result.get("error"),
    }


def extract_insights(transcript: str, symbols: Optional[List[str]] = None) -> Dict[str, Any]:
    """Extract indicators, keywords, timeframes, symbols, and key sentences."""
    text = transcript.lower()
    symbols = symbols or COMMON_SYMBOLS
    keywords = _find_keywords(text, DEFAULT_KEYWORDS)
    indicators = _find_indicators(text)
    timeframes = _find_timeframes(text)
    symbols_found = _find_symbols(text, symbols)
    key_sentences = _extract_key_sentences(transcript, DEFAULT_KEYWORDS)

    return {
        "keywords": keywords,
        "indicators": indicators,
        "timeframes": timeframes,
        "symbols": symbols_found,
        "key_sentences": key_sentences,
    }


def derive_strategy_hypotheses(insights: Dict[str, Any], symbols: List[str]) -> List[Dict[str, Any]]:
    """Translate insights into deterministic backtest ideas."""
    cfg = config.load_config()
    trading_cfg = cfg.get("trading", {})
    interval_default = cfg.get("hyperliquid", {}).get("interval", "1h")

    timeframes = insights.get("timeframes") or [interval_default]
    sym_list = insights.get("symbols") or symbols
    indicators = set(insights.get("indicators") or [])
    keywords = set(insights.get("keywords") or [])

    strategies: List[Dict[str, Any]] = []

    ma_pair = _extract_ma_pair(insights.get("key_sentences", []))
    rsi_bounds = _extract_rsi_bounds(insights.get("key_sentences", []))

    if "rsi" in indicators or any(term in keywords for term in ["oversold", "overbought", "mean reversion"]):
        params = {
            "period": rsi_bounds.get("period", trading_cfg.get("rsi_period", 14)),
            "lower": rsi_bounds.get("lower", trading_cfg.get("rsi_lower", 30)),
            "upper": rsi_bounds.get("upper", trading_cfg.get("rsi_upper", 70)),
        }
        strategies.append({"strategy": "rsi", "params": params, "rationale": "RSI/mean reversion mention"})

    if "sma" in indicators or "ema" in indicators or "moving average" in keywords or "crossover" in keywords:
        params = {
            "fast": ma_pair.get("fast", trading_cfg.get("sma_fast", 5)),
            "slow": ma_pair.get("slow", trading_cfg.get("sma_slow", 20)),
        }
        strategies.append({"strategy": "sma_cross", "params": params, "rationale": "MA crossover mention"})

    if not strategies:
        params = {
            "fast": trading_cfg.get("sma_fast", 5),
            "slow": trading_cfg.get("sma_slow", 20),
        }
        strategies.append({"strategy": "sma_cross", "params": params, "rationale": "Default trend test"})

    jobs: List[Dict[str, Any]] = []
    for symbol in sym_list:
        for tf in timeframes[:2]:
            for strat in strategies[:2]:
                jobs.append({
                    "id": _job_id(),
                    "symbol": symbol,
                    "interval": tf,
                    "strategy": strat["strategy"],
                    "params": strat["params"],
                    "rationale": strat["rationale"],
                })
    return jobs


def enqueue_backtest_jobs(jobs: List[Dict[str, Any]], channel_url: str, insight: VideoInsight) -> None:
    """Append backtest jobs to queue."""
    if not jobs:
        return
    TRADING_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    with open(QUEUE_FILE, "a", encoding="utf-8") as handle:
        for job in jobs:
            payload = {
                **job,
                "source": "youtube",
                "channel": channel_url,
                "video_id": insight.video_id,
                "video_title": insight.title,
                "created_at": now,
            }
            handle.write(json.dumps(payload) + "\n")


def load_queue() -> List[Dict[str, Any]]:
    """Load queued backtest jobs."""
    return _read_jsonl(QUEUE_FILE)


def run_backtest_queue(limit: int = 3) -> List[Dict[str, Any]]:
    """Run a limited number of queued backtests."""
    queue = load_queue()
    if not queue:
        return []

    to_run = queue[:limit]
    remaining = queue[limit:]

    results: List[Dict[str, Any]] = []
    for job in to_run:
        result = _run_backtest_job(job)
        if result:
            results.append(result)

    _rewrite_queue(remaining)
    return results


def _run_backtest_job(job: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    symbol = job.get("symbol")
    interval = job.get("interval", "1h")
    strategy = job.get("strategy", "sma_cross")
    params = job.get("params", {})

    cfg = config.load_config()
    lookback_days = int(cfg.get("hyperliquid", {}).get("lookback_days", 30))

    trading_pipeline.ensure_hyperliquid_snapshot(symbol, interval, lookback_days)
    candles = trading_pipeline.load_candles_for_symbol(symbol, interval)
    if not candles:
        return None

    strategy_cfg = trading_pipeline.StrategyConfig(
        kind=strategy,
        params=params,
        fee_bps=float(cfg.get("trading", {}).get("fee_bps", 5.0)),
        slippage_bps=float(cfg.get("trading", {}).get("slippage_bps", 2.0)),
        risk_per_trade=float(cfg.get("trading", {}).get("risk_per_trade", 0.02)),
        stop_loss_pct=float(cfg.get("trading", {}).get("stop_loss_pct", 0.03)),
        take_profit_pct=float(cfg.get("trading", {}).get("take_profit_pct", 0.06)),
        max_position_pct=float(cfg.get("trading", {}).get("max_position_pct", 0.25)),
        capital_usd=float(cfg.get("trading", {}).get("paper_capital_usd", 1000.0)),
    )

    backtest = trading_pipeline.run_backtest(candles, symbol, interval, strategy_cfg)
    trading_pipeline.log_backtest_result(backtest)

    payload = {
        "timestamp": time.time(),
        "job": job,
        "result": {
            "total_trades": backtest.total_trades,
            "win_rate": backtest.win_rate,
            "profit_factor": backtest.profit_factor,
            "max_drawdown": backtest.max_drawdown,
            "sharpe_ratio": backtest.sharpe_ratio,
            "expectancy": backtest.expectancy,
            "net_pnl": backtest.net_pnl,
            "roi": backtest.roi,
        },
    }

    TRADING_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_FILE, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")

    return payload


def _find_keywords(text: str, keywords: Iterable[str]) -> List[str]:
    found = []
    for keyword in keywords:
        if keyword in text:
            found.append(keyword)
    return found


def _find_indicators(text: str) -> List[str]:
    found = []
    for indicator, patterns in INDICATOR_MAP.items():
        for pattern in patterns:
            if pattern in text:
                found.append(indicator)
                break
    return found


def _find_timeframes(text: str) -> List[str]:
    timeframes = set()
    for match in re.findall(r"\b(\d+)\s*([mhdw])\b", text):
        timeframes.add(f"{match[0]}{match[1]}")
    if "daily" in text:
        timeframes.add("1d")
    if "weekly" in text:
        timeframes.add("1w")
    return sorted(timeframes)


def _find_symbols(text: str, symbols: Iterable[str]) -> List[str]:
    found = []
    for symbol in symbols:
        if symbol.lower() in text:
            found.append(symbol)
    return found


def _extract_key_sentences(transcript: str, keywords: Iterable[str]) -> List[str]:
    sentences = re.split(r"(?<=[.!?])\s+", transcript)
    matches = []
    for sentence in sentences:
        lower = sentence.lower()
        if any(keyword in lower for keyword in keywords):
            matches.append(sentence.strip())
        if len(matches) >= 8:
            break
    return matches


def _extract_ma_pair(sentences: List[str]) -> Dict[str, int]:
    joined = " ".join(sentences).lower()
    pair_match = re.search(r"(\d{1,3})\s*/\s*(\d{1,3})", joined)
    if pair_match:
        fast = int(pair_match.group(1))
        slow = int(pair_match.group(2))
        if fast < slow:
            return {"fast": fast, "slow": slow}
        return {"fast": slow, "slow": fast}
    return {}


def _extract_rsi_bounds(sentences: List[str]) -> Dict[str, int]:
    joined = " ".join(sentences).lower()
    bounds = re.findall(r"\b(\d{2})\b", joined)
    values = [int(val) for val in bounds if 10 <= int(val) <= 90]
    if len(values) >= 2:
        lower = min(values)
        upper = max(values)
        return {"lower": lower, "upper": upper}
    return {}


def _render_digest(channel_url: str, insights: List[VideoInsight]) -> str:
    lines = [
        "# Trading YouTube Digest",
        f"Channel: {channel_url}",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"Videos analyzed: {len(insights)}",
        "",
    ]
    for insight in insights:
        lines.append(f"## {insight.title}")
        lines.append(f"URL: {insight.url}")
        lines.append(f"Indicators: {', '.join(insight.indicators) if insight.indicators else 'None'}")
        lines.append(f"Symbols: {', '.join(insight.symbols) if insight.symbols else 'None'}")
        lines.append(f"Timeframes: {', '.join(insight.timeframes) if insight.timeframes else 'None'}")
        lines.append("Key takeaways:")
        for sentence in insight.key_sentences[:5]:
            lines.append(f"- {sentence}")
        if insight.strategy_hypotheses:
            lines.append("Backtest ideas:")
            for strat in insight.strategy_hypotheses[:3]:
                lines.append(
                    f"- {strat['symbol']} {strat['interval']} {strat['strategy']} "
                    f"{strat.get('params', {})} ({strat.get('rationale', '')})"
                )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _store_video_insight(insight: VideoInsight) -> None:
    TRADING_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "video_id": insight.video_id,
        "title": insight.title,
        "url": insight.url,
        "transcript_len": insight.transcript_len,
        "indicators": insight.indicators,
        "keywords": insight.keywords,
        "timeframes": insight.timeframes,
        "symbols": insight.symbols,
        "key_sentences": insight.key_sentences,
        "strategy_hypotheses": insight.strategy_hypotheses,
        "stored_at": datetime.now(timezone.utc).isoformat(),
    }
    path = TRADING_DIR / f"{insight.video_id}.json"
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def _insight_to_payload(insight: VideoInsight) -> Dict[str, Any]:
    return {
        "video_id": insight.video_id,
        "title": insight.title,
        "url": insight.url,
        "transcript_len": insight.transcript_len,
        "indicators": insight.indicators,
        "keywords": insight.keywords,
        "timeframes": insight.timeframes,
        "symbols": insight.symbols,
        "key_sentences": insight.key_sentences,
        "strategy_hypotheses": insight.strategy_hypotheses,
    }


def _aggregate_strategies(insights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate strategy hypotheses into a unique list."""
    strategies: Dict[str, Dict[str, Any]] = {}
    for insight in insights:
        for strat in insight.get("strategy_hypotheses", []):
            key = _strategy_key(strat)
            if key not in strategies:
                strategies[key] = {
                    "id": key,
                    "name": f"{strat['strategy']} {strat.get('symbol')} {strat.get('interval')}",
                    "description": strat.get("rationale", "Derived from YouTube channel"),
                    "rules": {
                        "strategy": strat.get("strategy"),
                        "params": strat.get("params", {}),
                        "symbol": strat.get("symbol"),
                        "interval": strat.get("interval"),
                    },
                    "source": "youtube",
                    "created_at": time.time(),
                }
    return list(strategies.values())


def _build_actions(strategies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    for strat in strategies:
        rules = strat.get("rules", {})
        actions.append({
            "action": "backtest",
            "symbol": rules.get("symbol"),
            "interval": rules.get("interval"),
            "strategy": rules.get("strategy"),
            "params": rules.get("params", {}),
        })
    return actions


def _seed_trader_strategies(strategies: List[Dict[str, Any]]) -> None:
    if not strategies:
        return
    existing = []
    if STRATEGIES_FILE.exists():
        try:
            with open(STRATEGIES_FILE, "r", encoding="utf-8") as handle:
                data = json.load(handle)
                existing = data.get("strategies", [])
        except Exception:
            existing = []

    existing_names = {item.get("name") for item in existing if isinstance(item, dict)}
    new_entries = []
    for strat in strategies:
        name = strat.get("name")
        if name in existing_names:
            continue
        new_entries.append({
            "id": strat.get("id"),
            "name": name,
            "description": strat.get("description", ""),
            "rules": strat.get("rules", {}),
            "created_at": strat.get("created_at", time.time()),
            "backtest_results": None,
            "paper_results": None,
            "approved_for_live": False,
        })

    if not new_entries:
        return

    merged = existing + new_entries
    STRATEGIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STRATEGIES_FILE, "w", encoding="utf-8") as handle:
        json.dump({"strategies": merged, "updated_at": time.time()}, handle, indent=2)


def _symbols_from_config() -> List[str]:
    cfg = config.load_config()
    symbols = cfg.get("hyperliquid", {}).get("symbols", [])
    if not symbols:
        return COMMON_SYMBOLS
    return [str(symbol).upper() for symbol in symbols]


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    entries: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                entries.append(payload)
    return entries


def _rewrite_queue(queue: List[Dict[str, Any]]) -> None:
    TRADING_DIR.mkdir(parents=True, exist_ok=True)
    with open(QUEUE_FILE, "w", encoding="utf-8") as handle:
        for entry in queue:
            handle.write(json.dumps(entry) + "\n")


def _job_id() -> str:
    return f"ytjob_{int(time.time() * 1000)}"


def _strategy_key(strat: Dict[str, Any]) -> str:
    params = strat.get("params", {})
    key = f"{strat.get('strategy')}-{strat.get('symbol')}-{strat.get('interval')}-{json.dumps(params, sort_keys=True)}"
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", key).strip("-")
    return slug[:60]


def _load_youtube_ingest():
    try:
        from core import youtube_ingest  # type: ignore
    except Exception:
        return None
    return youtube_ingest


def _list_videos(channel_url: str, limit: int, youtube_ingest) -> List[Dict[str, str]]:
    videos: List[Dict[str, str]] = []
    channel_id = _channel_id_from_url(channel_url)
    if youtube_ingest:
        try:
            if channel_id and channel_id.startswith("UC"):
                playlist_url = _uploads_playlist_url(channel_id)
                videos = youtube_ingest.list_latest_videos(playlist_url, limit=limit)
            else:
                videos = youtube_ingest.list_latest_videos(channel_url, limit=limit)
        except Exception:
            videos = []
    if videos:
        return videos
    return _list_videos_rss(channel_url, limit=limit)


def _list_videos_rss(channel_url: str, limit: int = 10) -> List[Dict[str, str]]:
    channel_id = _channel_id_from_url(channel_url)
    if not channel_id:
        return []
    feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    try:
        import urllib.request
        with urllib.request.urlopen(feed_url, timeout=20) as response:
            raw = response.read().decode("utf-8")
    except Exception:
        return []

    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError:
        return []

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
    }
    entries = root.findall("atom:entry", ns)
    videos: List[Dict[str, str]] = []
    for entry in entries[:limit]:
        video_id = entry.findtext("yt:videoId", default="", namespaces=ns)
        title = entry.findtext("atom:title", default="", namespaces=ns)
        link = entry.find("atom:link", ns)
        url = ""
        if link is not None:
            url = link.attrib.get("href", "")
        if not url and video_id:
            url = f"https://www.youtube.com/watch?v={video_id}"
        if not video_id or not url:
            continue
        videos.append({"id": video_id, "url": url, "title": title or "Untitled video"})
    return videos


def _channel_id_from_url(channel_url: str) -> Optional[str]:
    if not channel_url:
        return None
    match = re.search(r"/channel/([A-Za-z0-9_-]+)", channel_url)
    if match:
        return match.group(1)
    return None


def _uploads_playlist_url(channel_id: str) -> str:
    if channel_id.startswith("UC") and len(channel_id) > 2:
        playlist_id = "UU" + channel_id[2:]
    else:
        playlist_id = channel_id
    return f"https://www.youtube.com/playlist?list={playlist_id}"


def _fetch_transcript_api(video_id: Optional[str], url: Optional[str], title: str) -> Optional[Dict[str, str]]:
    if not video_id:
        return None
    try:
        from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
    except Exception:
        return None
    try:
        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
            text = " ".join(item.get("text", "") for item in transcript if item.get("text"))
        else:
            api = YouTubeTranscriptApi()
            fetched = api.fetch(video_id, languages=["en"])
            text = " ".join(snippet.text for snippet in fetched if getattr(snippet, "text", ""))
    except Exception:
        return None
    if not text:
        return None
    raw_path = notes_manager.log_command_snapshot(
        ["youtube_transcript_api", video_id],
        f"youtube-api-{video_id}",
        text,
    )
    return {
        "video_id": video_id,
        "title": title or f"YouTube Video {video_id}",
        "url": url or f"https://www.youtube.com/watch?v={video_id}",
        "transcript": text.strip(),
        "raw_path": str(raw_path),
    }
