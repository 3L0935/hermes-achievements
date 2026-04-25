"""Hermes Achievements dashboard plugin backend.

Mounted at /api/plugins/hermes-achievements/ by Hermes dashboard.
"""
from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

try:
    from fastapi import APIRouter
except Exception:  # Allows local unit tests without dashboard dependencies.
    class APIRouter:  # type: ignore
        def get(self, *_args, **_kwargs):
            return lambda fn: fn
        def post(self, *_args, **_kwargs):
            return lambda fn: fn

router = APIRouter()

ERROR_RE = re.compile(r"\b(error|failed|traceback|exception|permission denied|not found|eaddrinuse|already in use)\b", re.I)
PORT_RE = re.compile(r"\b(port\s+)?(3000|5173|8000|8080|9119)\b.*\b(in use|already|taken|eaddrinuse)\b|\beaddrinuse\b", re.I)
INSTALL_RE = re.compile(r"\b(npm|pnpm|yarn|pip|uv)\b.*\b(install|add)\b", re.I)
SUCCESS_RE = re.compile(r"\b(success|passed|built|compiled|done|exit_code[\"']?\s*[:=]\s*0)\b", re.I)

TIER_STYLE = {
    "Copper": {"rank": 1, "color": "#b87333"},
    "Silver": {"rank": 2, "color": "#c0c7d2"},
    "Gold": {"rank": 3, "color": "#f2c94c"},
    "Diamond": {"rank": 4, "color": "#67e8f9"},
    "Olympian": {"rank": 5, "color": "#c084fc"},
}

ACHIEVEMENTS: List[Dict[str, Any]] = [
    {"id": "let_him_cook", "name": "Let Him Cook", "description": "Let Hermes run a long autonomous tool chain in one session.", "category": "Agent Autonomy", "rarity": "Rare", "threshold_metric": "max_tool_calls_in_session", "tiers": [{"name": "Copper", "threshold": 10}, {"name": "Silver", "threshold": 25}, {"name": "Gold", "threshold": 50}, {"name": "Diamond", "threshold": 100}, {"name": "Olympian", "threshold": 200}]},
    {"id": "toolchain_maxxer", "name": "Toolchain Maxxer", "description": "Use many distinct Hermes tools in a single session.", "category": "Agent Autonomy", "rarity": "Epic", "threshold_metric": "max_distinct_tools_in_session", "tiers": [{"name": "Copper", "threshold": 3}, {"name": "Silver", "threshold": 5}, {"name": "Gold", "threshold": 8}, {"name": "Diamond", "threshold": 12}]},
    {"id": "full_send", "name": "Full Send", "description": "Use terminal, files, and web/browser capabilities in one run.", "category": "Agent Autonomy", "rarity": "Rare", "metric": "saw_full_send"},
    {"id": "subagent_commander", "name": "Subagent Commander", "description": "Delegate work to at least one subagent.", "category": "Agent Autonomy", "rarity": "Epic", "metric": "used_delegate"},
    {"id": "background_process_enjoyer", "name": "Background Process Enjoyer", "description": "Start or manage a background process.", "category": "Agent Autonomy", "rarity": "Uncommon", "metric": "used_process"},
    {"id": "cron_lord", "name": "Cron Lord", "description": "Create, inspect, or control scheduled autonomous jobs.", "category": "Agent Autonomy", "rarity": "Epic", "metric": "used_cron"},

    {"id": "red_text_connoisseur", "name": "Red Text Connoisseur", "description": "Encounter errors and keep going anyway.", "category": "Debugging Chaos", "rarity": "Cursed", "threshold_metric": "total_errors", "tiers": [{"name": "Copper", "threshold": 3}, {"name": "Silver", "threshold": 10}, {"name": "Gold", "threshold": 25}, {"name": "Diamond", "threshold": 50}]},
    {"id": "stack_trace_sommelier", "name": "Stack Trace Sommelier", "description": "Taste a traceback or exception in tool output.", "category": "Debugging Chaos", "rarity": "Rare", "metric": "saw_traceback"},
    {"id": "actually_read_the_logs", "name": "Actually Read The Logs", "description": "Inspect logs instead of guessing.", "category": "Debugging Chaos", "rarity": "Uncommon", "metric": "read_logs"},
    {"id": "port_3000_taken", "name": "Port 3000 Is Taken", "description": "Discover that a dev server port is already occupied. Again.", "category": "Debugging Chaos", "rarity": "Cursed", "metric": "saw_port_conflict"},
    {"id": "dependency_hell_tourist", "name": "Dependency Hell Tourist", "description": "Run into package/install chaos.", "category": "Debugging Chaos", "rarity": "Cursed", "metric": "saw_install_error"},
    {"id": "the_fix_was_restarting", "name": "The Fix Was Restarting It", "description": "Restart after an error cluster.", "category": "Debugging Chaos", "rarity": "Rare", "metric": "restart_after_error"},

    {"id": "supposed_to_be_quick", "name": "This Was Supposed To Be Quick", "description": "Turn a small ask into a large session.", "category": "Vibe Coding", "rarity": "Cursed", "threshold_metric": "max_messages_in_session", "tiers": [{"name": "Copper", "threshold": 20}, {"name": "Silver", "threshold": 50}, {"name": "Gold", "threshold": 100}, {"name": "Diamond", "threshold": 200}]},
    {"id": "one_more_small_change", "name": "One More Small Change", "description": "Make lots of file edits in one session.", "category": "Vibe Coding", "rarity": "Rare", "threshold_metric": "max_file_tool_calls_in_session", "tiers": [{"name": "Copper", "threshold": 3}, {"name": "Silver", "threshold": 8}, {"name": "Gold", "threshold": 15}, {"name": "Diamond", "threshold": 30}]},
    {"id": "vibe_architect", "name": "Vibe Architect", "description": "Touch many files or perform broad codebase surgery.", "category": "Vibe Coding", "rarity": "Epic", "threshold_metric": "max_files_touched_in_session", "tiers": [{"name": "Copper", "threshold": 3}, {"name": "Silver", "threshold": 8}, {"name": "Gold", "threshold": 15}, {"name": "Diamond", "threshold": 30}]},
    {"id": "pixel_goblin", "name": "Pixel Goblin", "description": "Work on frontend, CSS, SVG, or visual files.", "category": "Vibe Coding", "rarity": "Uncommon", "metric": "touched_frontend"},
    {"id": "ship_first_ask_later", "name": "Ship First, Ask Later", "description": "Use git after a serious tool chain.", "category": "Vibe Coding", "rarity": "Legendary", "metric": "git_after_many_tools"},

    {"id": "skillsmith", "name": "Skillsmith", "description": "Load, create, patch, or inspect Hermes skills.", "category": "Hermes Native", "rarity": "Rare", "metric": "used_skills"},
    {"id": "memory_keeper", "name": "Memory Keeper", "description": "Persist durable knowledge with memory or Mnemosyne.", "category": "Hermes Native", "rarity": "Rare", "metric": "used_memory"},
    {"id": "context_dragon", "name": "Context Dragon", "description": "Brush against compression, long context, or context management.", "category": "Hermes Native", "rarity": "Legendary", "metric": "saw_context"},
    {"id": "gateway_dweller", "name": "Gateway Dweller", "description": "Run Hermes through gateway-connected platforms.", "category": "Hermes Native", "rarity": "Uncommon", "metric": "gateway_connected"},
    {"id": "plugin_goblin", "name": "Plugin Goblin", "description": "Use or develop dashboard plugins.", "category": "Hermes Native", "rarity": "Epic", "metric": "plugin_activity"},
    {"id": "model_hopper", "name": "Model Hopper", "description": "Switch or inspect providers/models.", "category": "Hermes Native", "rarity": "Uncommon", "metric": "model_activity"},

    {"id": "rabbit_hole_certified", "name": "Rabbit Hole Certified", "description": "Search or extract enough web content to qualify as a research spiral.", "category": "Research/Web", "rarity": "Rare", "threshold_metric": "total_web_calls", "tiers": [{"name": "Copper", "threshold": 3}, {"name": "Silver", "threshold": 10}, {"name": "Gold", "threshold": 25}, {"name": "Diamond", "threshold": 50}]},
    {"id": "docs_archaeologist", "name": "Docs Archaeologist", "description": "Dig through documentation sources.", "category": "Research/Web", "rarity": "Uncommon", "metric": "docs_activity"},
    {"id": "browser_possession", "name": "Browser Possession", "description": "Possess a browser through automation.", "category": "Research/Web", "rarity": "Rare", "metric": "used_browser"},
    {"id": "citation_goblin", "name": "Citation Goblin", "description": "Extract enough web pages to become a tiny librarian.", "category": "Research/Web", "rarity": "Rare", "threshold_metric": "total_web_extract_calls", "tiers": [{"name": "Copper", "threshold": 2}, {"name": "Silver", "threshold": 8}, {"name": "Gold", "threshold": 20}, {"name": "Diamond", "threshold": 50}]},

    {"id": "terminal_goblin", "name": "Terminal Goblin", "description": "Spend serious time in shell-land.", "category": "Tool Mastery", "rarity": "Uncommon", "threshold_metric": "total_terminal_calls", "tiers": [{"name": "Copper", "threshold": 5}, {"name": "Silver", "threshold": 25}, {"name": "Gold", "threshold": 100}, {"name": "Diamond", "threshold": 250}, {"name": "Olympian", "threshold": 500}]},
    {"id": "patch_wizard", "name": "Patch Wizard", "description": "Bend files to your will with targeted patches.", "category": "Tool Mastery", "rarity": "Rare", "threshold_metric": "total_patch_calls", "tiers": [{"name": "Copper", "threshold": 3}, {"name": "Silver", "threshold": 10}, {"name": "Gold", "threshold": 30}, {"name": "Diamond", "threshold": 75}]},
    {"id": "file_archaeologist", "name": "File Archaeologist", "description": "Dig through the filesystem with reads and searches.", "category": "Tool Mastery", "rarity": "Uncommon", "threshold_metric": "total_file_reads_searches", "tiers": [{"name": "Copper", "threshold": 5}, {"name": "Silver", "threshold": 25}, {"name": "Gold", "threshold": 100}, {"name": "Diamond", "threshold": 250}]},
    {"id": "image_whisperer", "name": "Image Whisperer", "description": "Use image generation or vision tools.", "category": "Tool Mastery", "rarity": "Rare", "metric": "used_image_or_vision"},
    {"id": "voice_of_the_machine", "name": "Voice Of The Machine", "description": "Use text-to-speech or voice tooling.", "category": "Tool Mastery", "rarity": "Epic", "metric": "used_tts"},

    {"id": "openrouter_enjoyer", "name": "OpenRouter Enjoyer", "description": "Route model work through OpenRouter.", "category": "Model Lore", "rarity": "Uncommon", "metric": "openrouter_activity"},
    {"id": "codex_conjurer", "name": "Codex Conjurer", "description": "Summon Codex-flavored assistance.", "category": "Model Lore", "rarity": "Rare", "metric": "codex_activity"},
    {"id": "multi_model_mage", "name": "Multi-Model Mage", "description": "Use several model/provider names across your Hermes history.", "category": "Model Lore", "rarity": "Epic", "threshold_metric": "distinct_model_count", "tiers": [{"name": "Copper", "threshold": 2}, {"name": "Silver", "threshold": 4}, {"name": "Gold", "threshold": 7}, {"name": "Diamond", "threshold": 12}]},

    {"id": "weekend_warrior", "name": "Weekend Warrior", "description": "Run Hermes on a weekend because the agent grind never sleeps.", "category": "Lifestyle", "rarity": "Cursed", "metric": "weekend_activity"},
    {"id": "night_shift_operator", "name": "Night Shift Operator", "description": "Run a session during gremlin hours.", "category": "Lifestyle", "rarity": "Cursed", "metric": "night_activity"},
    {"id": "marathon_operator", "name": "Marathon Operator", "description": "Accumulate a large number of Hermes sessions.", "category": "Lifestyle", "rarity": "Legendary", "threshold_metric": "session_count", "tiers": [{"name": "Copper", "threshold": 10}, {"name": "Silver", "threshold": 50}, {"name": "Gold", "threshold": 100}, {"name": "Diamond", "threshold": 250}, {"name": "Olympian", "threshold": 500}]},
]


def state_path() -> Path:
    return Path.home() / ".hermes" / "plugins" / "hermes-achievements" / "state.json"


def load_state() -> Dict[str, Any]:
    path = state_path()
    if not path.exists():
        return {"unlocks": {}}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {"unlocks": {}}


def save_state(state: Dict[str, Any]) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True))


def _tool_name_from_call(call: Any) -> Optional[str]:
    if not isinstance(call, dict):
        return None
    fn = call.get("function") or {}
    return call.get("name") or fn.get("name")


def _content(msg: Dict[str, Any]) -> str:
    content = msg.get("content")
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    try:
        return json.dumps(content)
    except Exception:
        return str(content)


def analyze_messages(session_id: str, title: str, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    tool_names: Set[str] = set()
    file_tool_calls = 0
    web_calls = 0
    web_extract_calls = 0
    terminal_calls = 0
    patch_calls = 0
    file_reads_searches = 0
    files_touched: Set[str] = set()
    full_text_parts: List[str] = []
    error_count = 0

    for msg in messages:
        text = _content(msg)
        full_text_parts.append(text)
        if msg.get("tool_name"):
            tool_names.add(str(msg["tool_name"]))
        for call in msg.get("tool_calls") or []:
            name = _tool_name_from_call(call)
            if name:
                tool_names.add(name)
        if ERROR_RE.search(text):
            error_count += 1
        blob = text
        if msg.get("tool_calls"):
            blob += " " + json.dumps(msg.get("tool_calls"), default=str)
        for match in re.findall(r"(?:/home/|~/?|\./|/mnt/)[\w./-]+\.(?:py|js|ts|tsx|jsx|css|html|md|json|yaml|yml|svg)", blob):
            files_touched.add(match)

    for name in tool_names:
        lname = name.lower()
        if lname in {"read_file", "write_file", "patch", "search_files"} or "file" in lname or "patch" in lname:
            file_tool_calls += 1
        if lname in {"read_file", "search_files"}:
            file_reads_searches += 1
        if lname == "patch":
            patch_calls += 1
        if lname == "terminal":
            terminal_calls += 1
        if lname == "web_extract":
            web_extract_calls += 1
        if lname in {"web_search", "web_extract"} or lname.startswith("web"):
            web_calls += 1

    full_text = "\n".join(full_text_parts)
    lower_tools = {t.lower() for t in tool_names}
    has_terminal = "terminal" in lower_tools
    has_file = any(t in lower_tools for t in ["read_file", "write_file", "patch", "search_files"])
    has_web_or_browser = any(t.startswith("web") or t.startswith("browser") for t in lower_tools)

    return {
        "session_id": session_id,
        "title": title or "Untitled session",
        "message_count": len(messages),
        "tool_call_count": sum(len(m.get("tool_calls") or []) for m in messages),
        "tool_names": tool_names,
        "distinct_tool_count": len(tool_names),
        "error_count": error_count,
        "web_calls": web_calls,
        "web_extract_calls": web_extract_calls,
        "terminal_calls": terminal_calls,
        "patch_calls": patch_calls,
        "file_reads_searches": file_reads_searches,
        "file_tool_calls": file_tool_calls,
        "files_touched_count": len(files_touched),
        "port_conflict": bool(PORT_RE.search(full_text)),
        "traceback": "traceback" in full_text.lower() or "exception" in full_text.lower(),
        "install_error": bool(INSTALL_RE.search(full_text) and ERROR_RE.search(full_text)),
        "restart_after_error": bool(error_count and re.search(r"\brestart|reload|kill|start\b", full_text, re.I)),
        "full_send": has_terminal and has_file and has_web_or_browser,
        "used_delegate": "delegate_task" in lower_tools,
        "used_process": "process" in lower_tools or "background=true" in full_text,
        "used_cron": "cronjob" in lower_tools or re.search(r"\bcron\b", full_text, re.I) is not None,
        "read_logs": re.search(r"gateway\.log|errors\.log|agent\.log|/api/logs|\blogs\b", full_text, re.I) is not None,
        "touched_frontend": re.search(r"\.(css|svg|tsx|jsx)|frontend|tailwind|react", full_text, re.I) is not None,
        "git_after_many_tools": has_terminal and "git " in full_text and sum(len(m.get("tool_calls") or []) for m in messages) >= 10,
        "used_skills": any(t.startswith("skill") for t in lower_tools) or "skills" in full_text.lower(),
        "used_memory": any("memory" in t or "mnemosyne" in t for t in lower_tools),
        "saw_context": re.search(r"compress|context window|token", full_text, re.I) is not None,
        "plugin_activity": re.search(r"plugin|dashboard-plugins|__HERMES_PLUGIN", full_text, re.I) is not None,
        "model_activity": re.search(r"model|provider|openrouter|codex|gemini|claude", full_text, re.I) is not None,
        "docs_activity": re.search(r"docs|documentation|docusaurus|README", full_text, re.I) is not None,
        "used_browser": any(t.startswith("browser") for t in lower_tools),
        "used_image_or_vision": any("image" in t or "vision" in t for t in lower_tools),
        "used_tts": any("tts" in t or "speech" in t for t in lower_tools),
        "openrouter_activity": "openrouter" in full_text.lower(),
        "codex_activity": "codex" in full_text.lower(),
        "model_names": {str(m.get("model")) for m in messages if m.get("model")},
    }


def evaluate_tiered(definition: Dict[str, Any], aggregate: Dict[str, Any]) -> Dict[str, Any]:
    metric = definition["threshold_metric"]
    progress = int(aggregate.get(metric, 0) or 0)
    tiers = sorted(definition.get("tiers", []), key=lambda t: t["threshold"])
    achieved = [t for t in tiers if progress >= t["threshold"]]
    next_tiers = [t for t in tiers if progress < t["threshold"]]
    tier = achieved[-1]["name"] if achieved else None
    next_tier = next_tiers[0]["name"] if next_tiers else None
    next_threshold = next_tiers[0]["threshold"] if next_tiers else (tiers[-1]["threshold"] if tiers else 1)
    current_threshold = achieved[-1]["threshold"] if achieved else 0
    denom = max(1, next_threshold - current_threshold)
    pct = 100 if not next_tiers and achieved else max(0, min(100, math.floor(((progress - current_threshold) / denom) * 100)))
    return {"unlocked": bool(achieved), "tier": tier, "progress": progress, "next_tier": next_tier, "next_threshold": next_threshold, "progress_pct": pct}


def evaluate_boolean(definition: Dict[str, Any], aggregate: Dict[str, Any]) -> Dict[str, Any]:
    unlocked = bool(aggregate.get(definition["metric"]))
    return {"unlocked": unlocked, "tier": None, "progress": 1 if unlocked else 0, "next_tier": None, "next_threshold": 1, "progress_pct": 100 if unlocked else 0}


def scan_sessions(limit: int = 200) -> Dict[str, Any]:
    try:
        from hermes_state import SessionDB
    except Exception as exc:
        return {"sessions": [], "aggregate": {}, "error": f"Could not import SessionDB: {exc}"}

    db = SessionDB()
    try:
        sessions_meta = db.list_sessions_rich(limit=limit, include_children=True, project_compression_tips=False)
        sessions = []
        for meta in sessions_meta:
            sid = meta.get("id")
            messages = db.get_messages(sid) if sid else []
            stats = analyze_messages(sid, meta.get("title") or meta.get("preview") or "Untitled", messages)
            stats["started_at"] = meta.get("started_at")
            stats["last_active"] = meta.get("last_active")
            stats["source"] = meta.get("source")
            if meta.get("model"):
                stats["model_names"].add(str(meta.get("model")))
            sessions.append(stats)
    finally:
        close = getattr(db, "close", None)
        if close:
            close()

    aggregate = aggregate_stats(sessions)
    try:
        # Use status-like signal for gateway connected when dashboard process has access to logs/config.
        aggregate["gateway_connected"] = any(s.get("source") not in (None, "cli") for s in sessions)
    except Exception:
        pass
    return {"sessions": sessions, "aggregate": aggregate}


def aggregate_stats(sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    agg: Dict[str, Any] = {
        "session_count": len(sessions),
        "max_tool_calls_in_session": 0,
        "max_distinct_tools_in_session": 0,
        "max_messages_in_session": 0,
        "max_file_tool_calls_in_session": 0,
        "max_files_touched_in_session": 0,
        "total_errors": 0,
        "total_web_calls": 0,
        "total_web_extract_calls": 0,
        "total_terminal_calls": 0,
        "total_patch_calls": 0,
        "total_file_reads_searches": 0,
        "distinct_model_count": 0,
    }
    bool_map = {
        "saw_full_send": "full_send", "used_delegate": "used_delegate", "used_process": "used_process", "used_cron": "used_cron",
        "saw_traceback": "traceback", "read_logs": "read_logs", "saw_port_conflict": "port_conflict", "saw_install_error": "install_error", "restart_after_error": "restart_after_error",
        "touched_frontend": "touched_frontend", "git_after_many_tools": "git_after_many_tools", "used_skills": "used_skills", "used_memory": "used_memory",
        "saw_context": "saw_context", "plugin_activity": "plugin_activity", "model_activity": "model_activity", "docs_activity": "docs_activity", "used_browser": "used_browser",
        "used_image_or_vision": "used_image_or_vision", "used_tts": "used_tts", "openrouter_activity": "openrouter_activity", "codex_activity": "codex_activity",
    }
    model_names: Set[str] = set()
    for s in sessions:
        agg["max_tool_calls_in_session"] = max(agg["max_tool_calls_in_session"], s.get("tool_call_count", 0))
        agg["max_distinct_tools_in_session"] = max(agg["max_distinct_tools_in_session"], s.get("distinct_tool_count", 0))
        agg["max_messages_in_session"] = max(agg["max_messages_in_session"], s.get("message_count", 0))
        agg["max_file_tool_calls_in_session"] = max(agg["max_file_tool_calls_in_session"], s.get("file_tool_calls", 0))
        agg["max_files_touched_in_session"] = max(agg["max_files_touched_in_session"], s.get("files_touched_count", 0))
        agg["total_errors"] += s.get("error_count", 0)
        agg["total_web_calls"] += s.get("web_calls", 0)
        agg["total_web_extract_calls"] += s.get("web_extract_calls", 0)
        agg["total_terminal_calls"] += s.get("terminal_calls", 0)
        agg["total_patch_calls"] += s.get("patch_calls", 0)
        agg["total_file_reads_searches"] += s.get("file_reads_searches", 0)
        model_names.update(s.get("model_names") or set())
        if s.get("started_at"):
            try:
                ts = float(s.get("started_at"))
                lt = time.localtime(ts)
                agg["weekend_activity"] = bool(agg.get("weekend_activity") or lt.tm_wday >= 5)
                agg["night_activity"] = bool(agg.get("night_activity") or lt.tm_hour < 6 or lt.tm_hour >= 23)
            except Exception:
                pass
        for metric, source in bool_map.items():
            agg[metric] = bool(agg.get(metric) or s.get(source))
    agg["distinct_model_count"] = len({m for m in model_names if m and m != "None"})
    return agg


def evaluate_all() -> Dict[str, Any]:
    scan = scan_sessions()
    aggregate = scan.get("aggregate", {})
    state = load_state()
    unlocks = state.setdefault("unlocks", {})
    now = int(time.time())
    evaluated = []
    for definition in ACHIEVEMENTS:
        result = evaluate_tiered(definition, aggregate) if "threshold_metric" in definition else evaluate_boolean(definition, aggregate)
        unlock_id = definition["id"]
        if result["unlocked"] and unlock_id not in unlocks:
            unlocks[unlock_id] = {"unlocked_at": now, "first_tier": result.get("tier"), "evidence": evidence_for(definition, scan.get("sessions", []))}
        item = {**definition, **result, "unlocked_at": unlocks.get(unlock_id, {}).get("unlocked_at"), "evidence": unlocks.get(unlock_id, {}).get("evidence")}
        evaluated.append(item)
    save_state(state)
    unlocked = [a for a in evaluated if a["unlocked"]]
    return {"achievements": evaluated, "sessions": scan.get("sessions", []), "aggregate": aggregate, "error": scan.get("error"), "unlocked_count": len(unlocked), "total_count": len(evaluated)}


def evidence_for(definition: Dict[str, Any], sessions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    metric = definition.get("metric")
    threshold_metric = definition.get("threshold_metric")
    if metric:
        source_key = {
            "saw_full_send": "full_send", "saw_traceback": "traceback", "saw_port_conflict": "port_conflict", "saw_install_error": "install_error"
        }.get(metric, metric)
        for s in sessions:
            if s.get(source_key) or (metric.startswith("used_") and s.get(metric)):
                return {"session_id": s.get("session_id"), "title": s.get("title")}
    if threshold_metric:
        key = threshold_metric.replace("max_", "").replace("_in_session", "")
        mapping = {"tool_calls": "tool_call_count", "distinct_tools": "distinct_tool_count", "messages": "message_count", "file_tool_calls": "file_tool_calls", "files_touched": "files_touched_count"}
        stat_key = mapping.get(key)
        if stat_key and sessions:
            s = max(sessions, key=lambda x: x.get(stat_key, 0))
            return {"session_id": s.get("session_id"), "title": s.get("title"), "value": s.get(stat_key, 0)}
    return None


@router.get("/achievements")
async def achievements():
    data = evaluate_all()
    return {k: data[k] for k in ["achievements", "unlocked_count", "total_count", "error"] if k in data}


@router.get("/overview")
async def overview():
    data = evaluate_all()
    unlocked = [a for a in data["achievements"] if a["unlocked"]]
    latest = sorted(unlocked, key=lambda a: a.get("unlocked_at") or 0, reverse=True)[:5]
    categories = sorted({a["category"] for a in data["achievements"]})
    return {"unlocked_count": data["unlocked_count"], "total_count": data["total_count"], "aggregate": data["aggregate"], "latest": latest, "categories": categories, "error": data.get("error")}


@router.get("/recent-unlocks")
async def recent_unlocks():
    data = evaluate_all()
    return sorted([a for a in data["achievements"] if a["unlocked"]], key=lambda a: a.get("unlocked_at") or 0, reverse=True)[:20]


@router.get("/sessions/{session_id}/badges")
async def session_badges(session_id: str):
    data = evaluate_all()
    session = next((s for s in data["sessions"] if s["session_id"] == session_id), None)
    if not session:
        return {"session_id": session_id, "badges": []}
    aggregate = aggregate_stats([session])
    badges = []
    for definition in ACHIEVEMENTS:
        result = evaluate_tiered(definition, aggregate) if "threshold_metric" in definition else evaluate_boolean(definition, aggregate)
        if result["unlocked"]:
            badges.append({**definition, **result})
    return {"session_id": session_id, "badges": badges}


@router.post("/rescan")
async def rescan():
    return {"ok": True, **evaluate_all()}


@router.post("/reset-state")
async def reset_state():
    save_state({"unlocks": {}})
    return {"ok": True}
