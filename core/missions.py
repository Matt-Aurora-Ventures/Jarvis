"""
Background mission scheduler for Jarvis.

Runs lightweight missions (research, crawling, interviews) whenever the system
detects the user is idle, and writes findings into context documents.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from core import (
    config,
    context_manager,
    crypto_trading,
    git_ops,
    hyperliquid,
    interview,
    notes_manager,
    prompt_library,
    providers,
    research_engine,
    state,
    system_profiler,
    youtube_ingest,
)
from core import memory

ROOT = Path(__file__).resolve().parents[1]
MISSIONS_PATH = ROOT / "data" / "missions"
MISSION_STATE_FILE = MISSIONS_PATH / "mission_state.json"
MISSION_LOG_FILE = MISSIONS_PATH / "mission_log.jsonl"


@dataclass
class Mission:
    mission_id: str
    name: str
    interval_minutes: int
    min_idle_seconds: int
    runner: Callable[[], Optional[Dict[str, str]]]
    last_run: float = 0.0
    tags: List[str] = field(default_factory=list)


def _ensure_storage() -> None:
    MISSIONS_PATH.mkdir(parents=True, exist_ok=True)
    if not MISSION_STATE_FILE.exists():
        MISSION_STATE_FILE.write_text("{}", encoding="utf-8")


def _load_state() -> Dict[str, float]:
    _ensure_storage()
    try:
        return json.loads(MISSION_STATE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_state(state_map: Dict[str, float]) -> None:
    _ensure_storage()
    MISSION_STATE_FILE.write_text(json.dumps(state_map, indent=2), encoding="utf-8")


def _log_event(mission_id: str, status: str, payload: Dict[str, str]) -> None:
    _ensure_storage()
    entry = {
        "timestamp": time.time(),
        "mission": mission_id,
        "status": status,
        "payload": payload,
    }
    with MISSION_LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


def _research_summary(title: str, description: str, findings: List[Dict[str, str]]) -> str:
    if not findings:
        return f"No findings collected for {title}. Observation: {description}"
    lines = [f"Findings for {title}", ""]
    for item in findings:
        lines.append(f"- {item.get('title')}: {item.get('snippet', '')[:200]} ({item.get('url')})")
    return "\n".join(lines)


def _summarize_with_model(topic: str, findings: List[Dict[str, str]], goal: str) -> str:
    if not findings:
        return f"No data available for {topic}. Goal: {goal}"
    prompt = (
        f"You are Jarvis researching {topic} to support the user's autonomy goals.\n"
        f"Goal: {goal}\n"
        "Use the findings below to produce a concise summary with actionable insights:\n"
        f"{json.dumps(findings[:5], indent=2)}\n"
        "Output:\n"
        "1. Executive summary (2 sentences)\n"
        "2. Actionable insights (bullets)\n"
        "3. Follow-up experiments or interviews to schedule\n"
    )
    try:
        response = providers.generate_text(prompt, max_output_tokens=400)
        if response:
            return response.strip()
    except Exception:
        pass
    return _research_summary(topic, goal, findings)


def _run_moondev_watcher() -> Optional[Dict[str, str]]:
    url = "https://x.com/MoonDevOnYT"
    try:
        raw_path, payload = notes_manager.ingest_via_curl(url, label="moondev-x", timeout=20)
    except Exception:
        payload = ""
        raw_path = None
    findings = [
        {
            "title": "MoonDev X feed",
            "snippet": payload[:800],
            "url": url,
        }
    ]
    summary = _summarize_with_model(
        "MoonDevOnYT Feed",
        findings,
        "Track actionable strategy drops or hints from MoonDev's X posts.",
    )
    note_body = f"# MoonDevOnYT Feed Digest\n\nSource: {url}\nRaw capture: {raw_path or 'N/A'}\n\n## Summary\n{summary}\n"
    notes_manager.save_note(
        topic="moondev",
        content=note_body,
        fmt="md",
        tags=["moondev", "x", "research"],
        source="mission.moondev_watcher",
        metadata={"url": url},
    )
    doc = context_manager.add_context_document(
        title="MoonDev X Feed Digest",
        source="MoonDev Watcher",
        category="research",
        summary=summary.splitlines()[0] if summary else "MoonDev social snapshot",
        content=summary,
        tags=["moondev", "social", "research"],
        monetization_angle="Spot HFT and automation cues to test quickly.",
        metadata={"source": url},
    )
    return {"doc_id": doc.doc_id, "summary": doc.summary}


def _run_hft_sandbox() -> Optional[Dict[str, str]]:
    trader = crypto_trading.CryptoTrading()
    result = trader.run_hft_sandbox_cycle()
    if not result:
        return None
    strategy = result["strategy"]
    summary = (
        f"{strategy['objective']} on {strategy['chain']} {strategy['pair']} "
        f"PnL {result['pnl']} ({result['roi']*100:.2f}% ROI)"
    )
    doc = context_manager.add_context_document(
        title=f"HFT Sandbox – {strategy['pair']} ({strategy['chain']})",
        source="HFT Sandbox",
        category="research",
        summary=summary,
        content=(
            f"## Strategy\n- Chain: {strategy['chain']}\n- Pair: {strategy['pair']}\n"
            f"- Objective: {strategy['objective']}\n- Liquidity: {strategy['liquidity_source']}\n"
            f"- Capital: ${strategy['entry_capital']}\n\n"
            f"## Simulation Results\n- Trades: {result['trades']}\n"
            f"- Win rate: {result['win_rate']*100:.1f}%\n- PnL: {result['pnl']}\n"
            f"- ROI: {result['roi']*100:.2f}%\n"
        ),
        tags=["crypto", "hft", "sandbox"],
        monetization_angle="Identify low-cap strategies worth live testing.",
    )
    return {"doc_id": doc.doc_id, "summary": summary}


def _run_algotradecamp_digest() -> Optional[Dict[str, str]]:
    url = "https://algotradecamp.com"
    try:
        raw_path, payload = notes_manager.ingest_via_curl(url, label="algotradecamp", timeout=30)
    except Exception:
        payload = ""
        raw_path = None
    findings = [{"title": "AlgoTradeCamp Landing", "snippet": payload[:800], "url": url}]
    summary = _summarize_with_model(
        "AlgoTradeCamp Digest",
        findings,
        "Extract new lessons, toolkits, or calls to action relevant to low-cap HFT.",
    )
    note_body = (
        f"# AlgoTradeCamp Snapshot\n\nSource: {url}\nRaw capture: {raw_path or 'N/A'}\n\n"
        f"## Summary\n{summary}\n"
    )
    notes_manager.save_note(
        topic="algotradecamp",
        content=note_body,
        fmt="md",
        tags=["algotradecamp", "learning", "research"],
        source="mission.algotradecamp",
        metadata={"url": url},
    )
    doc = context_manager.add_context_document(
        title="AlgoTradeCamp Learning Digest",
        source="Learning Mission",
        category="research",
        summary=summary.splitlines()[0] if summary else "AlgoTradeCamp snapshot",
        content=summary,
        tags=["learning", "algo", "research"],
        monetization_angle="Convert lessons into concrete HFT experiments.",
        metadata={"source": url},
    )
    return {"doc_id": doc.doc_id, "summary": doc.summary}


def _run_youtube_transcripts() -> Optional[Dict[str, str]]:
    channel_url = "https://www.youtube.com/channel/UCN7D80fY9xMYu5mHhUhXEFw"
    videos = youtube_ingest.list_latest_videos(channel_url, limit=3)
    transcripts: List[Dict[str, str]] = []
    for video in videos:
        data = youtube_ingest.fetch_transcript(video["url"], label=video["id"])
        if not data:
            continue
        snippet = data["transcript"][:1200]
        transcripts.append(
            {
                "title": data["title"],
                "snippet": snippet,
                "url": data["url"],
            }
        )
        notes_manager.save_note(
            topic="moondev_youtube",
            content=f"# {data['title']}\n\nSource: {data['url']}\n\n{data['transcript']}",
            fmt="md",
            tags=["moondev", "youtube", "transcript"],
            source="mission.youtube_transcripts",
            metadata={"video_id": data["video_id"], "raw_path": data.get("raw_path")},
        )
    if not transcripts:
        return None
    summary = _summarize_with_model(
        "MoonDev YouTube Transcripts",
        transcripts,
        "Distill concrete bot ideas and infrastructure notes from MoonDev videos.",
    )
    doc = context_manager.add_context_document(
        title="MoonDev YouTube Transcript Digest",
        source="YouTube Harvester",
        category="research",
        summary=summary.splitlines()[0] if summary else "Video transcript digest",
        content=summary,
        tags=["moondev", "youtube", "research"],
        monetization_angle="Select low-cap HFT strategies to prototype.",
        metadata={"videos": [v["url"] for v in transcripts]},
    )
    return {"doc_id": doc.doc_id, "summary": doc.summary}


def _run_hyperliquid_snapshot() -> Optional[Dict[str, str]]:
    cfg = config.load_config()
    hcfg = cfg.get("hyperliquid", {})
    if not hcfg.get("enabled", True):
        return None
    coins = hcfg.get("symbols", ["ETH", "BTC", "SOL"])
    interval = hcfg.get("interval", "1h")
    lookback_days = int(hcfg.get("lookback_days", 30))
    results = hyperliquid.pull_lookback(coins, interval=interval, lookback_days=lookback_days)
    summary = hyperliquid.summarize_snapshot(results)
    note_body = (
        f"# Hyperliquid {lookback_days}d Snapshot\n\n"
        f"Interval: {interval}\n"
        f"Coins: {', '.join(coins)}\n\n"
        f"## Summary\n{summary}\n"
    )
    notes_manager.save_note(
        topic="hyperliquid",
        content=note_body,
        fmt="md",
        tags=["hyperliquid", "data", "research"],
        source="mission.hyperliquid_snapshot",
        metadata={"lookback_days": lookback_days, "interval": interval},
    )
    doc = context_manager.add_context_document(
        title="Hyperliquid Data Snapshot",
        source="Hyperliquid Ingest",
        category="research",
        summary=summary.splitlines()[0] if summary else "Hyperliquid data snapshot captured.",
        content=summary,
        tags=["hyperliquid", "data", "trading"],
        monetization_angle="Use 30-day data to validate low-fee DEX strategies.",
        metadata={"coins": coins, "interval": interval, "lookback_days": lookback_days},
    )
    return {"doc_id": doc.doc_id, "summary": doc.summary}


def _run_dex_api_scout() -> Optional[Dict[str, str]]:
    cfg = config.load_config()
    trading_cfg = cfg.get("trading", {})
    chains = trading_cfg.get("preferred_chains", [])
    queries = [
        "Solana DEX API Jupiter Raydium Orca free",
        "Base DEX API Aerodrome BaseSwap free",
        "BNB Chain DEX API PancakeSwap free",
        "Arbitrum DEX API Uniswap Camelot free",
        "Optimism DEX API Velodrome free",
        "Hyperliquid API docs",
    ]
    if chains:
        for chain in chains:
            queries.append(f"{chain} decentralized exchange api free")
    engine = research_engine.get_research_engine()
    findings: List[Dict[str, str]] = []
    for query in queries[:8]:
        try:
            results = engine.search_web(query, max_results=4)
            findings.extend(results)
        except Exception:
            continue
    summary = _summarize_with_model(
        "DEX API Scout",
        findings,
        "Identify free or low-cost DEX APIs for low-fee chains to build bots quickly.",
    )
    note_body = (
        "# DEX API Scout\n\n"
        "## Summary\n"
        f"{summary}\n\n"
        "## Raw Findings\n"
        + "\n".join(
            f"- {item.get('title')}: {item.get('url')}" for item in findings[:15]
        )
    )
    notes_manager.save_note(
        topic="dex_api_scout",
        content=note_body,
        fmt="md",
        tags=["dex", "api", "research"],
        source="mission.dex_api_scout",
    )
    doc = context_manager.add_context_document(
        title="DEX API Scout",
        source="Mission Scheduler",
        category="research",
        summary=summary.splitlines()[0] if summary else "DEX API scouting summary.",
        content=summary,
        tags=["dex", "api", "trading"],
        monetization_angle="Prioritize free API access for low-cap bot experiments.",
    )
    return {"doc_id": doc.doc_id, "summary": doc.summary}


def _parse_prompt_pack(text: str) -> List[Dict[str, str]]:
    prompts: List[Dict[str, str]] = []
    if "###" not in text:
        return prompts
    for block in text.split("### "):
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        title = lines[0].strip()
        tags: List[str] = []
        prompt_lines: List[str] = []
        in_prompt = False
        for line in lines[1:]:
            lowered = line.strip().lower()
            if lowered.startswith("tags:"):
                raw_tags = line.split(":", 1)[-1]
                tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
            elif lowered.startswith("prompt:"):
                in_prompt = True
            elif lowered.startswith("use case:"):
                in_prompt = False
            elif in_prompt:
                prompt_lines.append(line)
        prompt_text = "\n".join(prompt_lines).strip()
        if title and prompt_text:
            prompts.append({"title": title, "tags": ",".join(tags), "prompt": prompt_text})
    return prompts


def _run_prompt_pack_builder() -> Optional[Dict[str, str]]:
    prompt = (
        "Create a prompt pack for a media/creative agency + website builder who also "
        "wants crypto trading bots. Provide 10 prompts.\n\n"
        "Format strictly as:\n"
        "### <Title>\n"
        "Tags: tag1, tag2\n"
        "Prompt:\n"
        "<prompt text>\n"
        "Use case: <short use case>\n"
    )
    try:
        response = providers.generate_text(prompt, max_output_tokens=900)
    except Exception:
        response = ""
    if not response:
        return None
    prompts = _parse_prompt_pack(response)
    added: List[str] = []
    for entry in prompts:
        try:
            record = prompt_library.add_prompt(
                title=entry["title"],
                body=entry["prompt"],
                tags=[t.strip() for t in entry.get("tags", "").split(",") if t.strip()],
                source="mission.prompt_pack_builder",
            )
            added.append(record.id)
        except Exception:
            continue
    note_body = f"# Prompt Pack (Agency + Trading)\n\n{response}\n"
    notes_manager.save_note(
        topic="prompt_pack",
        content=note_body,
        fmt="md",
        tags=["prompt", "agency", "trading"],
        source="mission.prompt_pack_builder",
        metadata={"added_prompt_ids": added},
    )
    doc = context_manager.add_context_document(
        title="Prompt Pack: Agency + Trading",
        source="Prompt Pack Builder",
        category="prompts",
        summary="Generated a fresh prompt pack for creative agency work and trading research.",
        content=response,
        tags=["prompts", "agency", "trading"],
        monetization_angle="Use prompt packs to speed up client delivery and trading research.",
        metadata={"prompt_count": len(prompts), "prompt_ids": added},
    )
    try:
        import subprocess
        script = 'display notification "Prompt pack ready." with title "Jarvis"'
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
    except Exception:
        pass
    return {"doc_id": doc.doc_id, "summary": doc.summary}


def _run_idle_deep_research() -> Optional[Dict[str, str]]:
    cfg = config.load_config()
    idle_cfg = cfg.get("idle_research", {})
    if not idle_cfg.get("enabled", True):
        return None
    max_pages = int(idle_cfg.get("max_pages", 5))
    engine = research_engine.get_research_engine()
    topics = engine.queue.get("priority_topics", [])
    if not topics:
        return None
    topic = topics[int(time.time()) % len(topics)]
    result = engine.research_topic(topic, max_pages=max_pages)
    summary = result.get("summary", "").strip()
    if not summary:
        return None
    doc = context_manager.add_context_document(
        title=f"Idle Research: {topic}",
        source="Idle Research",
        category="research",
        summary=summary.splitlines()[0],
        content=summary,
        tags=["research", "idle"],
        monetization_angle="Idle time turned into lightweight research wins.",
    )
    return {"doc_id": doc.doc_id, "summary": doc.summary}


def _run_ai_news_scan() -> Optional[Dict[str, str]]:
    queries = [
        "AI agents latest news 2025",
        "open source LLM release news",
        "self hosted TTS latest model",
        "macOS security monitoring tools",
        "network packet monitoring open source mac",
    ]
    engine = research_engine.get_research_engine()
    findings: List[Dict[str, str]] = []
    for query in queries:
        try:
            results = engine.search_web(query, max_results=3)
            findings.extend(results)
        except Exception:
            continue
    if not findings:
        return None
    summary = _summarize_with_model(
        "AI/ML + Security News",
        findings,
        "Find new tools or model releases that improve Jarvis, plus security monitoring ideas.",
    )
    note_body = (
        "# AI + Security News Scan\n\n"
        "## Summary\n"
        f"{summary}\n\n"
        "## Sources\n"
        + "\n".join(
            f"- {item.get('title')}: {item.get('url')}" for item in findings[:12]
        )
    )
    notes_manager.save_note(
        topic="ai_news",
        content=note_body,
        fmt="md",
        tags=["news", "ai", "security"],
        source="mission.ai_news_scan",
    )
    doc = context_manager.add_context_document(
        title="AI + Security News Scan",
        source="Mission Scheduler",
        category="research",
        summary=summary.splitlines()[0] if summary else "AI + security news scan.",
        content=summary,
        tags=["news", "ai", "security"],
        monetization_angle="Upgrade Jarvis with recent releases and monitoring tools.",
    )
    return {"doc_id": doc.doc_id, "summary": doc.summary}


def _run_business_suggestions() -> Optional[Dict[str, str]]:
    ctx_summary = context_manager.get_context_summary()
    recent_memory = memory.summarize_entries(memory.get_recent_entries()[-10:])
    prompt = (
        "You are Jarvis. Generate 5 concise, high-impact suggestions for the user's "
        "media/creative agency + website workflows and trading research.\n\n"
        f"Context summary:\n{ctx_summary}\n\n"
        f"Recent memory:\n{recent_memory}\n\n"
        "Output as bullets."
    )
    try:
        response = providers.generate_text(prompt, max_output_tokens=300)
    except Exception:
        response = ""
    if not response:
        return None
    notes_manager.save_note(
        topic="business_suggestions",
        content=f"# Business Suggestions\n\n{response}\n",
        fmt="md",
        tags=["business", "agency", "suggestions"],
        source="mission.business_suggestions",
    )
    doc = context_manager.add_context_document(
        title="Business Suggestions Digest",
        source="Mission Scheduler",
        category="business",
        summary="Fresh suggestions generated for agency and trading workflows.",
        content=response,
        tags=["business", "agency", "suggestions"],
        monetization_angle="Translate suggestions into quick wins and new offers.",
    )
    return {"doc_id": doc.doc_id, "summary": doc.summary}


def _run_directive_digest() -> Optional[Dict[str, str]]:
    ctx_summary = context_manager.get_context_summary()
    recent_memory = memory.summarize_entries(memory.get_recent_entries()[-10:])
    prompt = (
        "Summarize Jarvis directives into a crisp, 8-bullet operating brief.\n"
        "Keep it tight, non-repetitive, and action-oriented.\n\n"
        f"Context summary:\n{ctx_summary}\n\n"
        f"Recent memory:\n{recent_memory}\n"
    )
    try:
        response = providers.generate_text(prompt, max_output_tokens=260)
    except Exception:
        response = ""
    if not response:
        return None
    notes_manager.save_note(
        topic="directive_digest",
        content=f"# Jarvis Directive Digest\n\n{response}\n",
        fmt="md",
        tags=["directives", "summary"],
        source="mission.directive_digest",
    )
    doc = context_manager.add_context_document(
        title="Jarvis Directive Digest",
        source="Mission Scheduler",
        category="directives",
        summary="Condensed operating directives for Jarvis.",
        content=response,
        tags=["directives", "summary"],
        monetization_angle="Keep focus tight and reduce instruction drift.",
    )
    return {"doc_id": doc.doc_id, "summary": doc.summary}


def _run_hyperliquid_backtest() -> Optional[Dict[str, str]]:
    cfg = config.load_config()
    hcfg = cfg.get("hyperliquid", {})
    coins = hcfg.get("symbols", ["ETH"])
    interval = hcfg.get("interval", "1h")
    for coin in coins:
        path = hyperliquid.latest_snapshot_for_coin(coin, interval=interval)
        if not path:
            continue
        snapshot = hyperliquid.load_snapshot(str(path))
        if not snapshot:
            continue
        candles = snapshot.get("candles", [])
        result = hyperliquid.simple_ma_backtest(candles, fast=5, slow=20)
        if result.get("error"):
            continue
        summary = (
            f"{coin} {interval} MA(5/20) backtest: "
            f"{result['trades']} trades, PnL {result['pnl']}, ROI {result['roi']}"
        )
        notes_manager.save_note(
            topic="hyperliquid_backtest",
            content=f"# Hyperliquid Backtest\n\n{summary}\n\nData: {path}\n",
            fmt="md",
            tags=["hyperliquid", "backtest", "trading"],
            source="mission.hyperliquid_backtest",
            metadata={"coin": coin, "interval": interval, "path": str(path)},
        )
        doc = context_manager.add_context_document(
            title=f"Hyperliquid Backtest ({coin})",
            source="Mission Scheduler",
            category="trading",
            summary=summary,
            content=summary,
            tags=["hyperliquid", "backtest", "trading"],
            monetization_angle="Use quick backtests to vet low-fee strategies.",
        )
        return {"doc_id": doc.doc_id, "summary": doc.summary}
    return None


def _run_self_improvement() -> Optional[Dict[str, str]]:
    attempts = providers.last_generation_attempts(limit=5)
    provider_errors = providers.last_provider_errors()
    recent_memory = memory.get_recent_entries()[-5:]
    summary_lines = [
        "## Provider Diagnostics",
        json.dumps(provider_errors, indent=2),
        "\n## Recent Attempts",
        json.dumps(attempts, indent=2),
        "\n## Recent Memory Highlights",
    ]
    for entry in recent_memory:
        summary_lines.append(f"- {entry.get('text', '')[:160]}")
    note_body = "\n".join(summary_lines)
    notes_manager.save_note(
        topic="self_improvement",
        content=f"# Self-Improvement Scan\n\n{note_body}",
        fmt="md",
        tags=["self-improvement", "diagnostics"],
        source="mission.self_improvement",
    )
    findings = [
        {
            "title": "Provider error state",
            "snippet": json.dumps(provider_errors),
            "url": "internal://providers",
        }
    ]
    summary = _summarize_with_model(
        "Self-Improvement Audit",
        findings,
        "Decide which capabilities to upgrade next (providers, prompts, data ingestion).",
    )
    doc = context_manager.add_context_document(
        title="Self-Improvement Audit",
        source="Mission Scheduler",
        category="improvement",
        summary=summary.splitlines()[0] if summary else "Self-improvement status",
        content=summary,
        tags=["improvement", "diagnostics"],
        monetization_angle="Prioritize upgrades that unblock revenue-driving tasks.",
    )
    return {"doc_id": doc.doc_id, "summary": doc.summary}


def _run_weekly_interview() -> Optional[Dict[str, str]]:
    questions = interview.generate_smart_questions()
    ctx_summary = context_manager.get_context_summary()
    content = f"## Weekly Interview Questions\n\n{questions}\n\n## Current Context\n\n{ctx_summary}"
    doc = context_manager.add_context_document(
        title="Weekly Interview Prep",
        source="Mission Scheduler",
        category="interview",
        summary="Prepared a new set of interview questions based on recent context.",
        content=content,
        tags=["interview", "self-reflection"],
        monetization_angle="Keep alignment between Jarvis improvements and user goals.",
    )
    return {"doc_id": doc.doc_id, "questions": questions[:120]}


def _default_missions(state_map: Dict[str, float]) -> List[Mission]:
    cfg = config.load_config()
    idle_cfg = cfg.get("idle_research", {})
    idle_min_seconds = int(idle_cfg.get("min_idle_seconds", 1200))
    missions = [
        Mission(
            mission_id="moondev_watcher",
            name="Moondev Watcher",
            interval_minutes=180,
            min_idle_seconds=180,
            runner=_run_moondev_watcher,
            tags=["crypto", "research"],
        ),
        Mission(
            mission_id="algotradecamp_digest",
            name="AlgoTradeCamp Digest",
            interval_minutes=240,
            min_idle_seconds=600,
            runner=_run_algotradecamp_digest,
            tags=["learning", "research"],
        ),
        Mission(
            mission_id="youtube_transcripts",
            name="MoonDev YouTube Transcripts",
            interval_minutes=180,
            min_idle_seconds=600,
            runner=_run_youtube_transcripts,
            tags=["youtube", "moondev"],
        ),
        Mission(
            mission_id="hyperliquid_snapshot",
            name="Hyperliquid Snapshot",
            interval_minutes=360,
            min_idle_seconds=600,
            runner=_run_hyperliquid_snapshot,
            tags=["hyperliquid", "data"],
        ),
        Mission(
            mission_id="dex_api_scout",
            name="DEX API Scout",
            interval_minutes=240,
            min_idle_seconds=600,
            runner=_run_dex_api_scout,
            tags=["dex", "api", "research"],
        ),
        Mission(
            mission_id="prompt_pack_builder",
            name="Prompt Pack Builder",
            interval_minutes=720,
            min_idle_seconds=600,
            runner=_run_prompt_pack_builder,
            tags=["prompts", "agency"],
        ),
        Mission(
            mission_id="idle_deep_research",
            name="Idle Deep Research",
            interval_minutes=120,
            min_idle_seconds=idle_min_seconds,
            runner=_run_idle_deep_research,
            tags=["research", "idle"],
        ),
        Mission(
            mission_id="ai_news_scan",
            name="AI + Security News",
            interval_minutes=360,
            min_idle_seconds=600,
            runner=_run_ai_news_scan,
            tags=["news", "ai", "security"],
        ),
        Mission(
            mission_id="business_suggestions",
            name="Business Suggestions",
            interval_minutes=240,
            min_idle_seconds=600,
            runner=_run_business_suggestions,
            tags=["business", "agency"],
        ),
        Mission(
            mission_id="directive_digest",
            name="Directive Digest",
            interval_minutes=720,
            min_idle_seconds=600,
            runner=_run_directive_digest,
            tags=["directives", "summary"],
        ),
        Mission(
            mission_id="hyperliquid_backtest",
            name="Hyperliquid Backtest",
            interval_minutes=240,
            min_idle_seconds=600,
            runner=_run_hyperliquid_backtest,
            tags=["hyperliquid", "backtest"],
        ),
        Mission(
            mission_id="self_improvement",
            name="Self-Improvement Pulse",
            interval_minutes=90,
            min_idle_seconds=600,
            runner=_run_self_improvement,
            tags=["improvement", "diagnostics"],
        ),
        Mission(
            mission_id="hft_sandbox",
            name="HFT Sandbox",
            interval_minutes=180,
            min_idle_seconds=900,
            runner=_run_hft_sandbox,
            tags=["crypto", "automation"],
        ),
        Mission(
            mission_id="weekly_interview",
            name="Weekly Interview Prep",
            interval_minutes=60 * 24 * 3,  # every 3 days
            min_idle_seconds=120,
            runner=_run_weekly_interview,
            tags=["interview", "reflection"],
        ),
    ]
    for mission in missions:
        mission.last_run = float(state_map.get(mission.mission_id, 0.0))
    return missions


class MissionScheduler(threading.Thread):
    def __init__(self, poll_seconds: int = 60, idle_grace_seconds: int = 120) -> None:
        super().__init__(daemon=True)
        self._stop_event = threading.Event()
        self._poll_seconds = poll_seconds
        self._idle_grace_seconds = idle_grace_seconds
        cfg = config.load_config()
        self._mission_cfg = cfg.get("missions", {})
        state_map = _load_state()
        self._missions = _default_missions(state_map)

    def stop(self) -> None:
        self._stop_event.set()

    def _current_idle(self) -> float:
        current = state.read_state()
        return float(current.get("passive_idle_seconds", 0))

    def _resources_ok(self) -> bool:
        cfg = config.load_config()
        mission_cfg = cfg.get("missions", {})
        max_cpu = mission_cfg.get("max_cpu_load")
        min_ram = mission_cfg.get("min_free_ram_gb")
        if max_cpu is None and min_ram is None:
            return True
        profile = system_profiler.read_profile()
        if max_cpu is not None and profile.cpu_load and profile.cpu_load > float(max_cpu):
            return False
        if min_ram is not None and profile.ram_free_gb and profile.ram_free_gb < float(min_ram):
            return False
        return True

    def _should_run(self, mission: Mission) -> bool:
        if not self._resources_ok():
            return False
        if time.time() - mission.last_run < mission.interval_minutes * 60:
            return False
        idle_seconds = self._current_idle()
        return idle_seconds >= max(mission.min_idle_seconds, self._idle_grace_seconds)

    def _maybe_auto_commit(self, mission: Mission, payload: Optional[Dict[str, str]]) -> None:
        if not self._mission_cfg.get("auto_commit_enabled", True):
            return
        summary = ""
        if isinstance(payload, dict):
            summary = payload.get("summary") or payload.get("doc_id", "")
        try:
            result = git_ops.auto_commit_with_state(
                task_name=f"mission:{mission.mission_id}",
                summary=summary,
                push_after=bool(self._mission_cfg.get("auto_commit_push", True)),
                throttle_seconds=int(self._mission_cfg.get("auto_commit_min_seconds", 10800)),
            )
            if result.get("status") == "committed":
                _log_event(mission.mission_id, "auto_commit", result)
        except Exception as exc:
            _log_event(mission.mission_id, "auto_commit_error", {"error": str(exc)})

    def _run_mission(self, mission: Mission) -> None:
        try:
            result = mission.runner()
            mission.last_run = time.time()
            _log_event(mission.mission_id, "success", result or {})
            if result:
                self._maybe_auto_commit(mission, result)
        except Exception as exc:
            mission.last_run = time.time()
            _log_event(mission.mission_id, "error", {"error": str(exc)})
        finally:
            state_map = {m.mission_id: m.last_run for m in self._missions}
            _save_state(state_map)

    def run(self) -> None:
        cfg = config.load_config()
        mission_cfg = cfg.get("missions", {})
        if not mission_cfg.get("enabled", True):
            state.update_state(missions_enabled=False)
            return
        state.update_state(missions_enabled=True)
        while not self._stop_event.is_set():
            for mission in self._missions:
                if self._should_run(mission):
                    self._run_mission(mission)
            time.sleep(self._poll_seconds)


_scheduler: Optional[MissionScheduler] = None


def start_scheduler(poll_seconds: int = 60) -> MissionScheduler:
    global _scheduler
    if _scheduler and _scheduler.is_alive():
        return _scheduler
    cfg = config.load_config()
    idle_grace = int(cfg.get("missions", {}).get("idle_grace_seconds", 120))
    scheduler = MissionScheduler(poll_seconds=poll_seconds, idle_grace_seconds=idle_grace)
    scheduler.start()
    _scheduler = scheduler
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.stop()
        _scheduler.join(timeout=5)
        _scheduler = None
