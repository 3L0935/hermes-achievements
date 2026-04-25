"""Hermes Achievements dashboard plugin backend.

Mounted at /api/plugins/hermes-achievements/ by Hermes dashboard.
"""
from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:
    from fastapi import APIRouter
except Exception:  # Allows local unit tests without dashboard dependencies.
    class APIRouter:  # type: ignore
        def get(self, *_args, **_kwargs):
            return lambda fn: fn
        def post(self, *_args, **_kwargs):
            return lambda fn: fn

router = APIRouter()

ERROR_RE = re.compile(r"\b(error|failed|failure|traceback|exception|permission denied|not found|eaddrinuse|already in use|timed out|blocked)\b", re.I)
PORT_RE = re.compile(r"\b(port\s+)?(3000|5173|8000|8080|9119)\b.*\b(in use|already|taken|eaddrinuse)\b|\beaddrinuse\b", re.I)
INSTALL_RE = re.compile(r"\b(npm|pnpm|yarn|pip|uv)\b.*\b(install|add)\b", re.I)
SUCCESS_RE = re.compile(r"\b(success|passed|built|compiled|done|exit_code[\"']?\s*[:=]\s*0|verified|ok)\b", re.I)
FILE_RE = re.compile(r"(?:/home/|~/?|\./|/mnt/)[\w./-]+\.(?:py|js|ts|tsx|jsx|css|html|md|json|yaml|yml|svg|sql|sh)")

TIER_NAMES = ["Copper", "Silver", "Gold", "Diamond", "Olympian"]


def tiers(values: List[int]) -> List[Dict[str, Any]]:
    return [{"name": name, "threshold": threshold} for name, threshold in zip(TIER_NAMES, values)]


def req(metric: str, gte: int) -> Dict[str, Any]:
    return {"metric": metric, "gte": gte}


ACHIEVEMENTS: List[Dict[str, Any]] = [
    # Agent Autonomy — mostly best-session feats
    {"id": "let_him_cook", "name": "Let Him Cook", "description": "Let Hermes run a serious autonomous tool chain in one session.", "category": "Agent Autonomy", "rarity": "Rare", "kind": "best_session", "icon": "flame", "threshold_metric": "max_tool_calls_in_session", "tiers": tiers([200, 500, 1200, 3000, 8000])},
    {"id": "autonomous_avalanche", "name": "Autonomous Avalanche", "description": "A single session becomes a tool-call weather event.", "category": "Agent Autonomy", "rarity": "Legendary", "kind": "best_session", "icon": "avalanche", "threshold_metric": "max_tool_calls_in_session", "tiers": tiers([500, 1000, 2500, 6000, 15000])},
    {"id": "toolchain_maxxer", "name": "Toolchain Maxxer", "description": "Use a wide spread of distinct Hermes tools in one session.", "category": "Agent Autonomy", "rarity": "Epic", "kind": "best_session", "icon": "nodes", "threshold_metric": "max_distinct_tools_in_session", "tiers": tiers([18, 28, 45, 70, 100])},
    {"id": "full_send", "name": "Full Send", "description": "Terminal, files, and web/browser all get involved in one real run.", "category": "Agent Autonomy", "rarity": "Rare", "kind": "multi_condition", "icon": "rocket", "requirements": [req("max_terminal_calls_in_session", 180), req("max_file_tool_calls_in_session", 120), req("max_web_browser_calls_in_session", 60)]},
    {"id": "subagent_commander", "name": "Subagent Commander", "description": "Coordinate delegated agent work.", "category": "Agent Autonomy", "rarity": "Epic", "kind": "lifetime", "icon": "branch", "threshold_metric": "total_delegate_calls", "tiers": tiers([1000, 3000, 8000, 20000, 50000])},
    {"id": "background_process_enjoyer", "name": "Background Process Enjoyer", "description": "Start or control enough long-running processes to deserve the title.", "category": "Agent Autonomy", "rarity": "Uncommon", "kind": "lifetime", "icon": "daemon", "threshold_metric": "total_process_calls", "tiers": tiers([300, 800, 2000, 6000, 15000])},
    {"id": "cron_necromancer", "name": "Cron Necromancer", "description": "Raise scheduled autonomous jobs from the dead.", "category": "Agent Autonomy", "rarity": "Legendary", "kind": "lifetime", "icon": "clock", "threshold_metric": "total_cron_calls", "tiers": tiers([1000, 3000, 8000, 20000, 50000])},

    # Debugging Chaos — higher thresholds + multi-condition events
    {"id": "red_text_connoisseur", "name": "Red Text Connoisseur", "description": "Encounter enough errors to develop a palate for red text.", "category": "Debugging Chaos", "rarity": "Cursed", "kind": "lifetime", "icon": "warning", "threshold_metric": "total_errors", "tiers": tiers([1500, 4000, 10000, 25000, 75000])},
    {"id": "stack_trace_sommelier", "name": "Stack Trace Sommelier", "description": "Taste tracebacks by the flight, not by the sip.", "category": "Debugging Chaos", "rarity": "Rare", "kind": "lifetime", "icon": "wine", "threshold_metric": "traceback_events", "tiers": tiers([300, 1000, 3000, 8000, 20000])},
    {"id": "actually_read_the_logs", "name": "Actually Read The Logs", "description": "Inspect logs repeatedly instead of guessing.", "category": "Debugging Chaos", "rarity": "Uncommon", "kind": "lifetime", "icon": "scroll", "threshold_metric": "log_read_events", "tiers": tiers([1000, 3000, 8000, 20000, 50000])},
    {"id": "port_3000_taken", "name": "Port 3000 Is Taken", "description": "Discover dev-server port conflict patterns enough times to become numb.", "category": "Debugging Chaos", "rarity": "Cursed", "kind": "lifetime", "icon": "plug", "secret": True, "threshold_metric": "port_conflict_events", "tiers": tiers([1000, 3000, 8000, 20000, 50000])},
    {"id": "permission_denied_any_percent", "name": "Permission Denied Any%", "description": "Speedrun into permission walls.", "category": "Debugging Chaos", "rarity": "Cursed", "kind": "lifetime", "icon": "lock", "secret": True, "threshold_metric": "permission_denied_events", "tiers": tiers([25, 75, 200, 600, 1500])},
    {"id": "dependency_hell_tourist", "name": "Dependency Hell Tourist", "description": "Package installs fail, then somehow life continues.", "category": "Debugging Chaos", "rarity": "Cursed", "kind": "multi_condition", "icon": "package_skull", "requirements": [req("install_error_events", 25), req("install_success_events", 10)]},
    {"id": "the_fix_was_restarting", "name": "The Fix Was Restarting It", "description": "Restart after enough error clusters to call it a technique.", "category": "Debugging Chaos", "rarity": "Rare", "kind": "multi_condition", "icon": "restart", "requirements": [req("restart_after_error_events", 50), req("total_errors", 4000)]},
    {"id": "forgot_the_env_var", "name": "Forgot The Env Var", "description": "Auth or configuration failed because an environment variable was missing.", "category": "Debugging Chaos", "rarity": "Cursed", "kind": "lifetime", "icon": "key", "secret": True, "threshold_metric": "env_var_error_events", "tiers": tiers([5000, 15000, 40000, 100000, 250000])},
    {"id": "yaml_colon_incident", "name": "YAML Colon Incident", "description": "Configuration syntax bites back.", "category": "Debugging Chaos", "rarity": "Cursed", "kind": "lifetime", "icon": "colon", "secret": True, "threshold_metric": "yaml_error_events", "tiers": tiers([1000, 3000, 8000, 20000, 50000])},
    {"id": "docker_name_collision", "name": "Docker Name Collision", "description": "A container name already exists. Of course it does.", "category": "Debugging Chaos", "rarity": "Cursed", "kind": "lifetime", "icon": "container", "secret": True, "threshold_metric": "docker_conflict_events", "tiers": tiers([75, 200, 600, 1500, 4000])},

    # Vibe Coding
    {"id": "supposed_to_be_quick", "name": "This Was Supposed To Be Quick", "description": "A tiny ask becomes an entire expedition.", "category": "Vibe Coding", "rarity": "Cursed", "kind": "best_session", "icon": "melting_clock", "threshold_metric": "max_messages_in_session", "tiers": tiers([300, 600, 1200, 2500, 6000])},
    {"id": "one_more_small_change", "name": "One More Small Change", "description": "Make enough file edits in one session to invalidate the phrase small change.", "category": "Vibe Coding", "rarity": "Rare", "kind": "best_session", "icon": "pencil", "threshold_metric": "max_file_tool_calls_in_session", "tiers": tiers([150, 400, 1000, 3000, 8000])},
    {"id": "vibe_architect", "name": "Vibe Architect", "description": "Touch a broad surface area in one project session.", "category": "Vibe Coding", "rarity": "Epic", "kind": "best_session", "icon": "blueprint", "threshold_metric": "max_files_touched_in_session", "tiers": tiers([300, 700, 1500, 4000, 10000])},
    {"id": "pixel_goblin", "name": "Pixel Goblin", "description": "Do sustained frontend, CSS, SVG, or visual tuning.", "category": "Vibe Coding", "rarity": "Uncommon", "kind": "lifetime", "icon": "pixel", "threshold_metric": "frontend_activity_events", "tiers": tiers([20000, 50000, 120000, 300000, 800000])},
    {"id": "ship_first_ask_later", "name": "Ship First, Ask Later", "description": "Git activity after a serious tool chain.", "category": "Vibe Coding", "rarity": "Legendary", "kind": "multi_condition", "icon": "ship", "requirements": [req("git_events", 50), req("max_tool_calls_in_session", 500)]},
    {"id": "css_exorcist", "name": "CSS Exorcist", "description": "Cast repeated styling demons out of the interface.", "category": "Vibe Coding", "rarity": "Rare", "kind": "lifetime", "icon": "spark_cursor", "threshold_metric": "css_activity_events", "tiers": tiers([10000, 30000, 80000, 200000, 500000])},
    {"id": "one_character_fix", "name": "One Character Fix", "description": "A tiny edit after a pile of errors. Painful. Beautiful.", "category": "Vibe Coding", "rarity": "Legendary", "kind": "multi_condition", "icon": "needle", "secret": True, "requirements": [req("tiny_patch_after_errors_events", 5), req("total_errors", 4000)]},

    # Hermes Native
    {"id": "skillsmith", "name": "Skillsmith", "description": "Work with Hermes skills enough to leave fingerprints.", "category": "Hermes Native", "rarity": "Rare", "kind": "lifetime", "icon": "hammer_scroll", "threshold_metric": "skill_events", "tiers": tiers([5000, 15000, 40000, 100000, 250000])},
    {"id": "skill_issue_skill_created", "name": "Skill Issue? Skill Created.", "description": "Create or patch durable procedures instead of repeating yourself.", "category": "Hermes Native", "rarity": "Legendary", "kind": "lifetime", "icon": "anvil", "threshold_metric": "skill_manage_events", "tiers": tiers([25, 75, 200, 600, 1500])},
    {"id": "memory_keeper", "name": "Memory Keeper", "description": "Persist durable knowledge with memory or Mnemosyne.", "category": "Hermes Native", "rarity": "Rare", "kind": "lifetime", "icon": "crystal", "threshold_metric": "memory_events", "tiers": tiers([100, 300, 1000, 3000, 8000])},
    {"id": "memory_palace", "name": "Memory Palace", "description": "Build a serious durable-memory trail.", "category": "Hermes Native", "rarity": "Legendary", "kind": "lifetime", "icon": "palace", "threshold_metric": "memory_write_events", "tiers": tiers([100, 300, 1000, 3000, 8000])},
    {"id": "context_dragon", "name": "Context Dragon", "description": "Brush against compression, huge context, or token pressure repeatedly.", "category": "Hermes Native", "rarity": "Legendary", "kind": "lifetime", "icon": "dragon", "threshold_metric": "context_events", "tiers": tiers([5000, 15000, 40000, 100000, 250000])},
    {"id": "gateway_dweller", "name": "Gateway Dweller", "description": "Live through gateway-connected Hermes workflows.", "category": "Hermes Native", "rarity": "Uncommon", "kind": "lifetime", "icon": "antenna", "threshold_metric": "gateway_events", "tiers": tiers([5000, 15000, 40000, 100000, 250000])},
    {"id": "plugin_goblin", "name": "Plugin Goblin", "description": "Use or develop plugins enough that the dashboard notices.", "category": "Hermes Native", "rarity": "Epic", "kind": "lifetime", "icon": "puzzle", "threshold_metric": "plugin_events", "tiers": tiers([1000, 3000, 8000, 20000, 50000])},
    {"id": "rollback_wizard", "name": "Rollback Wizard", "description": "Invoke rollback/checkpoint recovery magic.", "category": "Hermes Native", "rarity": "Legendary", "kind": "lifetime", "icon": "rewind", "secret": True, "threshold_metric": "rollback_events", "tiers": tiers([500, 1500, 4000, 10000, 25000])},

    # Research/Web
    {"id": "rabbit_hole_certified", "name": "Rabbit Hole Certified", "description": "Search or extract enough web content to qualify as a research spiral.", "category": "Research/Web", "rarity": "Rare", "kind": "lifetime", "icon": "spiral", "threshold_metric": "total_web_calls", "tiers": tiers([400, 1200, 3000, 8000, 20000])},
    {"id": "citation_goblin", "name": "Citation Goblin", "description": "Extract enough web pages to become a tiny librarian.", "category": "Research/Web", "rarity": "Rare", "kind": "lifetime", "icon": "quote", "threshold_metric": "total_web_extract_calls", "tiers": tiers([100, 300, 1000, 3000, 8000])},
    {"id": "docs_archaeologist", "name": "Docs Archaeologist", "description": "Dig through documentation sources over and over.", "category": "Research/Web", "rarity": "Uncommon", "kind": "lifetime", "icon": "compass", "threshold_metric": "docs_activity_events", "tiers": tiers([5000, 15000, 40000, 100000, 250000])},
    {"id": "browser_possession", "name": "Browser Possession", "description": "Possess a browser through automation repeatedly.", "category": "Research/Web", "rarity": "Rare", "kind": "lifetime", "icon": "browser", "threshold_metric": "browser_calls", "tiers": tiers([75, 200, 600, 1500, 4000])},

    # Tool Mastery
    {"id": "terminal_goblin", "name": "Terminal Goblin", "description": "Spend serious time in shell-land.", "category": "Tool Mastery", "rarity": "Uncommon", "kind": "lifetime", "icon": "terminal", "threshold_metric": "total_terminal_calls", "tiers": tiers([750, 2000, 6000, 15000, 50000])},
    {"id": "patch_wizard", "name": "Patch Wizard", "description": "Bend files to your will with targeted patches.", "category": "Tool Mastery", "rarity": "Rare", "kind": "lifetime", "icon": "wand", "threshold_metric": "total_patch_calls", "tiers": tiers([250, 750, 2000, 6000, 15000])},
    {"id": "file_archaeologist", "name": "File Archaeologist", "description": "Dig through the filesystem with reads and searches.", "category": "Tool Mastery", "rarity": "Uncommon", "kind": "lifetime", "icon": "folder", "threshold_metric": "total_file_reads_searches", "tiers": tiers([750, 2000, 6000, 15000, 50000])},
    {"id": "image_whisperer", "name": "Image Whisperer", "description": "Use image generation or vision tools enough for visual work.", "category": "Tool Mastery", "rarity": "Rare", "kind": "lifetime", "icon": "eye", "threshold_metric": "image_vision_calls", "tiers": tiers([100, 300, 1000, 3000, 8000])},
    {"id": "voice_of_the_machine", "name": "Voice Of The Machine", "description": "Use text-to-speech or voice tooling repeatedly.", "category": "Tool Mastery", "rarity": "Epic", "kind": "lifetime", "icon": "wave", "threshold_metric": "tts_calls", "tiers": tiers([10, 30, 100, 300, 800])},

    # Model Lore
    {"id": "model_hopper", "name": "Model Hopper", "description": "Switch or inspect providers/models enough to count as a habit.", "category": "Model Lore", "rarity": "Uncommon", "kind": "lifetime", "icon": "swap", "threshold_metric": "model_events", "tiers": tiers([10000, 30000, 80000, 200000, 500000])},
    {"id": "openrouter_enjoyer", "name": "OpenRouter Enjoyer", "description": "Route model work through OpenRouter repeatedly.", "category": "Model Lore", "rarity": "Uncommon", "kind": "lifetime", "icon": "router", "threshold_metric": "openrouter_events", "tiers": tiers([250, 750, 2000, 6000, 15000])},
    {"id": "codex_conjurer", "name": "Codex Conjurer", "description": "Summon Codex-flavored assistance often enough for a ritual.", "category": "Model Lore", "rarity": "Rare", "kind": "lifetime", "icon": "codex", "threshold_metric": "codex_events", "tiers": tiers([500, 1500, 4000, 10000, 25000])},
    {"id": "multi_model_mage", "name": "Multi-Model Mage", "description": "Use a real spread of distinct model names across Hermes history.", "category": "Model Lore", "rarity": "Epic", "kind": "lifetime", "icon": "prism", "threshold_metric": "distinct_model_count", "tiers": tiers([10, 20, 40, 80, 160])},

    # Lifestyle
    {"id": "marathon_operator", "name": "Marathon Operator", "description": "Accumulate a serious number of Hermes sessions.", "category": "Lifestyle", "rarity": "Legendary", "kind": "lifetime", "icon": "marathon", "threshold_metric": "session_count", "tiers": tiers([75, 200, 500, 1500, 5000])},
    {"id": "weekend_warrior", "name": "Weekend Warrior", "description": "Run Hermes on weekends enough times to make it a lifestyle.", "category": "Lifestyle", "rarity": "Cursed", "kind": "lifetime", "icon": "calendar", "threshold_metric": "weekend_sessions", "tiers": tiers([25, 75, 200, 600, 1500])},
    {"id": "night_shift_operator", "name": "Night Shift Operator", "description": "Run sessions during gremlin hours repeatedly.", "category": "Lifestyle", "rarity": "Cursed", "kind": "lifetime", "icon": "moon", "threshold_metric": "night_sessions", "tiers": tiers([25, 75, 200, 600, 1500])},
    {"id": "cache_hit_appreciator", "name": "Cache Hit Appreciator", "description": "Notice or benefit from prompt/cache behavior.", "category": "Lifestyle", "rarity": "Rare", "kind": "lifetime", "icon": "cache", "secret": True, "threshold_metric": "cache_events", "tiers": tiers([100, 300, 1000, 3000, 8000])},
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


def _count_tool(tool_names: List[str], *needles: str) -> int:
    lowered = [name.lower() for name in tool_names]
    return sum(1 for name in lowered if any(needle in name for needle in needles))


def analyze_messages(session_id: str, title: str, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    tool_names: Set[str] = set()
    tool_sequence: List[str] = []
    files_touched: Set[str] = set()
    full_text_parts: List[str] = []
    error_count = 0

    for msg in messages:
        text = _content(msg)
        full_text_parts.append(text)
        if msg.get("tool_name"):
            name = str(msg["tool_name"])
            tool_names.add(name)
            # Tool result rows name the tool that already appeared in the assistant tool_calls.
            # Keep it for distinct-tool detection, but do not double-count it as a new call.
            if msg.get("role") != "tool":
                tool_sequence.append(name)
        for call in msg.get("tool_calls") or []:
            name = _tool_name_from_call(call)
            if name:
                tool_names.add(name)
                tool_sequence.append(name)
        if ERROR_RE.search(text):
            error_count += 1
        blob = text
        if msg.get("tool_calls"):
            blob += " " + json.dumps(msg.get("tool_calls"), default=str)
        files_touched.update(FILE_RE.findall(blob))

    full_text = "\n".join(full_text_parts)
    lower = full_text.lower()
    terminal_calls = _count_tool(tool_sequence, "terminal")
    web_calls = _count_tool(tool_sequence, "web_search", "web_extract")
    web_extract_calls = _count_tool(tool_sequence, "web_extract")
    browser_calls = _count_tool(tool_sequence, "browser")
    web_browser_calls = web_calls + browser_calls
    patch_calls = _count_tool(tool_sequence, "patch")
    file_reads_searches = _count_tool(tool_sequence, "read_file", "search_files")
    file_tool_calls = _count_tool(tool_sequence, "read_file", "write_file", "patch", "search_files")
    delegate_calls = _count_tool(tool_sequence, "delegate_task")
    process_calls = _count_tool(tool_sequence, "process") + len(re.findall(r"background\s*=\s*true", full_text, re.I))
    cron_calls = _count_tool(tool_sequence, "cronjob")
    image_vision_calls = _count_tool(tool_sequence, "image", "vision")
    tts_calls = _count_tool(tool_sequence, "tts", "text_to_speech")
    skill_events = _count_tool(tool_sequence, "skill") + len(re.findall(r"\bskill", lower))
    skill_manage_events = _count_tool(tool_sequence, "skill_manage")
    memory_events = _count_tool(tool_sequence, "memory", "mnemosyne")
    memory_write_events = _count_tool(tool_sequence, "mnemosyne_remember", "memory")

    return {
        "session_id": session_id,
        "title": title or "Untitled session",
        "message_count": len(messages),
        "tool_call_count": len(tool_sequence),
        "tool_names": tool_names,
        "distinct_tool_count": len(tool_names),
        "error_count": error_count,
        "terminal_calls": terminal_calls,
        "web_calls": web_calls,
        "web_extract_calls": web_extract_calls,
        "browser_calls": browser_calls,
        "web_browser_calls": web_browser_calls,
        "patch_calls": patch_calls,
        "file_reads_searches": file_reads_searches,
        "file_tool_calls": file_tool_calls,
        "files_touched_count": len(files_touched),
        "delegate_calls": delegate_calls,
        "process_calls": process_calls,
        "cron_calls": cron_calls,
        "image_vision_calls": image_vision_calls,
        "tts_calls": tts_calls,
        "skill_events": skill_events,
        "skill_manage_events": skill_manage_events,
        "memory_events": memory_events,
        "memory_write_events": memory_write_events,
        "port_conflict": bool(PORT_RE.search(full_text)),
        "port_conflict_events": 1 if PORT_RE.search(full_text) else 0,
        "traceback_events": len(re.findall(r"traceback|exception", full_text, re.I)),
        "log_read_events": len(re.findall(r"gateway\.log|errors\.log|agent\.log|/api/logs|\blogs\b", full_text, re.I)),
        "permission_denied_events": len(re.findall(r"permission denied|eacces|operation not permitted", full_text, re.I)),
        "install_error_events": 1 if INSTALL_RE.search(full_text) and ERROR_RE.search(full_text) else 0,
        "install_success_events": 1 if INSTALL_RE.search(full_text) and SUCCESS_RE.search(full_text) else 0,
        "restart_after_error_events": 1 if error_count and re.search(r"\brestart|reload|kill|start\b", full_text, re.I) else 0,
        "env_var_error_events": len(re.findall(r"missing .*env|api key|environment variable|not configured|unauthorized|auth", full_text, re.I)),
        "yaml_error_events": len(re.findall(r"yaml|yml|colon|parse error", full_text, re.I)) if ERROR_RE.search(full_text) else 0,
        "docker_conflict_events": len(re.findall(r"docker.*(name|container).*already|container name conflict|Conflict\. The container", full_text, re.I)),
        "frontend_activity_events": len(re.findall(r"\.(css|svg|tsx|jsx)|frontend|tailwind|react", full_text, re.I)),
        "css_activity_events": len(re.findall(r"\.css|tailwind|style|className|visual", full_text, re.I)),
        "git_events": len(re.findall(r"\bgit\s+(commit|push|merge|rebase|status|diff)", full_text, re.I)),
        "tiny_patch_after_errors_events": 1 if error_count >= 5 and re.search(r"one character|single character|typo", full_text, re.I) else 0,
        "context_events": len(re.findall(r"compress|context window|token|cache", full_text, re.I)),
        "gateway_events": len(re.findall(r"gateway|discord|telegram|slack|api_server", full_text, re.I)),
        "plugin_events": len(re.findall(r"plugin|dashboard-plugins|__HERMES_PLUGIN|manifest\.json", full_text, re.I)),
        "rollback_events": len(re.findall(r"rollback|checkpoint", full_text, re.I)),
        "docs_activity_events": len(re.findall(r"docs|documentation|docusaurus|README", full_text, re.I)),
        "model_events": len(re.findall(r"model|provider|openrouter|codex|gemini|claude", full_text, re.I)),
        "openrouter_events": len(re.findall(r"openrouter", full_text, re.I)),
        "codex_events": len(re.findall(r"codex", full_text, re.I)),
        "cache_events": len(re.findall(r"cache hit|prompt caching|cache_read", full_text, re.I)),
        "model_names": set(),
    }


def evaluate_tiered(definition: Dict[str, Any], aggregate: Dict[str, Any]) -> Dict[str, Any]:
    metric = definition["threshold_metric"]
    progress = int(aggregate.get(metric, 0) or 0)
    tiers_list = sorted(definition.get("tiers", []), key=lambda t: t["threshold"])
    achieved = [t for t in tiers_list if progress >= t["threshold"]]
    next_tiers = [t for t in tiers_list if progress < t["threshold"]]
    tier = achieved[-1]["name"] if achieved else None
    next_tier = next_tiers[0]["name"] if next_tiers else None
    next_threshold = next_tiers[0]["threshold"] if next_tiers else (tiers_list[-1]["threshold"] if tiers_list else 1)
    current_threshold = achieved[-1]["threshold"] if achieved else 0
    denom = max(1, next_threshold - current_threshold)
    pct = 100 if not next_tiers and achieved else max(0, min(99, math.floor(((progress - current_threshold) / denom) * 100)))
    unlocked = bool(achieved)
    discovered = bool(progress > 0)
    state = "unlocked" if unlocked else ("discovered" if discovered else ("secret" if definition.get("secret") else "locked"))
    return {"unlocked": unlocked, "discovered": discovered, "state": state, "tier": tier, "progress": progress, "next_tier": next_tier, "next_threshold": next_threshold, "progress_pct": pct}


def evaluate_requirements(definition: Dict[str, Any], aggregate: Dict[str, Any]) -> Dict[str, Any]:
    requirements = definition.get("requirements", [])
    if not requirements:
        return {"unlocked": False, "discovered": False, "state": "secret" if definition.get("secret") else "locked", "tier": None, "progress": 0, "next_tier": None, "next_threshold": 1, "progress_pct": 0}
    parts = []
    any_progress = False
    complete = True
    for requirement in requirements:
        value = int(aggregate.get(requirement["metric"], 0) or 0)
        threshold = int(requirement.get("gte", 1))
        any_progress = any_progress or value > 0
        complete = complete and value >= threshold
        parts.append(min(1.0, value / max(1, threshold)))
    pct = math.floor((sum(parts) / len(parts)) * 100)
    state = "unlocked" if complete else ("discovered" if any_progress else ("secret" if definition.get("secret") else "locked"))
    return {"unlocked": complete, "discovered": any_progress, "state": state, "tier": None, "progress": pct, "next_tier": None, "next_threshold": 100, "progress_pct": 100 if complete else min(99, pct)}


def evaluate_boolean(definition: Dict[str, Any], aggregate: Dict[str, Any]) -> Dict[str, Any]:
    # Backward-compatible helper for old tests/definitions. New catalog avoids simple booleans.
    unlocked = bool(aggregate.get(definition["metric"]))
    return {"unlocked": unlocked, "discovered": unlocked, "state": "unlocked" if unlocked else "locked", "tier": None, "progress": 1 if unlocked else 0, "next_tier": None, "next_threshold": 1, "progress_pct": 100 if unlocked else 0}


def display_achievement(item: Dict[str, Any]) -> Dict[str, Any]:
    if item.get("state") == "secret":
        return {**item, "name": "???", "description": "A secret achievement waits in the logs.", "icon": "secret"}
    return item


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
    return {"sessions": sessions, "aggregate": aggregate_stats(sessions)}


def aggregate_stats(sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    agg: Dict[str, Any] = {
        "session_count": len(sessions),
        "max_tool_calls_in_session": 0,
        "max_distinct_tools_in_session": 0,
        "max_messages_in_session": 0,
        "max_terminal_calls_in_session": 0,
        "max_file_tool_calls_in_session": 0,
        "max_web_calls_in_session": 0,
        "max_web_browser_calls_in_session": 0,
        "max_files_touched_in_session": 0,
        "total_errors": 0,
        "total_terminal_calls": 0,
        "total_web_calls": 0,
        "total_web_extract_calls": 0,
        "total_patch_calls": 0,
        "total_file_reads_searches": 0,
        "total_delegate_calls": 0,
        "total_process_calls": 0,
        "total_cron_calls": 0,
        "browser_calls": 0,
        "image_vision_calls": 0,
        "tts_calls": 0,
        "distinct_model_count": 0,
        "weekend_sessions": 0,
        "night_sessions": 0,
    }
    sum_keys = [
        "traceback_events", "log_read_events", "port_conflict_events", "permission_denied_events", "install_error_events", "install_success_events", "restart_after_error_events", "env_var_error_events", "yaml_error_events", "docker_conflict_events", "frontend_activity_events", "css_activity_events", "git_events", "tiny_patch_after_errors_events", "skill_events", "skill_manage_events", "memory_events", "memory_write_events", "context_events", "gateway_events", "plugin_events", "rollback_events", "docs_activity_events", "model_events", "openrouter_events", "codex_events", "cache_events",
    ]
    for key in sum_keys:
        agg[key] = 0

    model_names: Set[str] = set()
    for s in sessions:
        agg["max_tool_calls_in_session"] = max(agg["max_tool_calls_in_session"], s.get("tool_call_count", 0))
        agg["max_distinct_tools_in_session"] = max(agg["max_distinct_tools_in_session"], s.get("distinct_tool_count", 0))
        agg["max_messages_in_session"] = max(agg["max_messages_in_session"], s.get("message_count", 0))
        agg["max_terminal_calls_in_session"] = max(agg["max_terminal_calls_in_session"], s.get("terminal_calls", 0))
        agg["max_file_tool_calls_in_session"] = max(agg["max_file_tool_calls_in_session"], s.get("file_tool_calls", 0))
        agg["max_web_calls_in_session"] = max(agg["max_web_calls_in_session"], s.get("web_calls", 0))
        agg["max_web_browser_calls_in_session"] = max(agg["max_web_browser_calls_in_session"], s.get("web_browser_calls", 0))
        agg["max_files_touched_in_session"] = max(agg["max_files_touched_in_session"], s.get("files_touched_count", 0))
        agg["total_errors"] += s.get("error_count", 0)
        agg["total_terminal_calls"] += s.get("terminal_calls", 0)
        agg["total_web_calls"] += s.get("web_calls", 0)
        agg["total_web_extract_calls"] += s.get("web_extract_calls", 0)
        agg["total_patch_calls"] += s.get("patch_calls", 0)
        agg["total_file_reads_searches"] += s.get("file_reads_searches", 0)
        agg["total_delegate_calls"] += s.get("delegate_calls", 0)
        agg["total_process_calls"] += s.get("process_calls", 0)
        agg["total_cron_calls"] += s.get("cron_calls", 0)
        agg["browser_calls"] += s.get("browser_calls", 0)
        agg["image_vision_calls"] += s.get("image_vision_calls", 0)
        agg["tts_calls"] += s.get("tts_calls", 0)
        for key in sum_keys:
            agg[key] += s.get(key, 0)
        model_names.update(s.get("model_names") or set())
        if s.get("started_at"):
            try:
                lt = time.localtime(float(s.get("started_at")))
                if lt.tm_wday >= 5:
                    agg["weekend_sessions"] += 1
                if lt.tm_hour < 6 or lt.tm_hour >= 23:
                    agg["night_sessions"] += 1
            except Exception:
                pass
    agg["distinct_model_count"] = len({m for m in model_names if m and m != "None"})
    return agg


def evaluate_definition(definition: Dict[str, Any], aggregate: Dict[str, Any]) -> Dict[str, Any]:
    if "threshold_metric" in definition:
        return evaluate_tiered(definition, aggregate)
    if "requirements" in definition:
        return evaluate_requirements(definition, aggregate)
    return evaluate_boolean(definition, aggregate)


def evidence_for(definition: Dict[str, Any], sessions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not sessions:
        return None
    metric = definition.get("threshold_metric")
    metric_to_session_key = {
        "max_tool_calls_in_session": "tool_call_count",
        "max_distinct_tools_in_session": "distinct_tool_count",
        "max_messages_in_session": "message_count",
        "max_terminal_calls_in_session": "terminal_calls",
        "max_file_tool_calls_in_session": "file_tool_calls",
        "max_web_calls_in_session": "web_calls",
        "max_web_browser_calls_in_session": "web_browser_calls",
        "max_files_touched_in_session": "files_touched_count",
    }
    if metric in metric_to_session_key:
        key = metric_to_session_key[metric]
        s = max(sessions, key=lambda x: x.get(key, 0))
        return {"session_id": s.get("session_id"), "title": s.get("title"), "value": s.get(key, 0)}
    return None


def evaluate_all() -> Dict[str, Any]:
    scan = scan_sessions()
    aggregate = scan.get("aggregate", {})
    state = load_state()
    unlocks = state.setdefault("unlocks", {})
    now = int(time.time())
    evaluated = []
    for definition in ACHIEVEMENTS:
        result = evaluate_definition(definition, aggregate)
        unlock_id = definition["id"]
        if result["unlocked"] and unlock_id not in unlocks:
            unlocks[unlock_id] = {"unlocked_at": now, "first_tier": result.get("tier"), "evidence": evidence_for(definition, scan.get("sessions", []))}
        item = {**definition, **result}
        if result["unlocked"]:
            item["unlocked_at"] = unlocks.get(unlock_id, {}).get("unlocked_at")
            item["evidence"] = unlocks.get(unlock_id, {}).get("evidence") or evidence_for(definition, scan.get("sessions", []))
        evaluated.append(display_achievement(item))
    save_state(state)
    unlocked = [a for a in evaluated if a["unlocked"]]
    discovered = [a for a in evaluated if a.get("state") == "discovered"]
    secret = [a for a in evaluated if a.get("state") == "secret"]
    return {"achievements": evaluated, "sessions": scan.get("sessions", []), "aggregate": aggregate, "error": scan.get("error"), "unlocked_count": len(unlocked), "discovered_count": len(discovered), "secret_count": len(secret), "total_count": len(evaluated)}


@router.get("/achievements")
async def achievements():
    data = evaluate_all()
    return {k: data[k] for k in ["achievements", "unlocked_count", "discovered_count", "secret_count", "total_count", "error"] if k in data}


@router.get("/overview")
async def overview():
    data = evaluate_all()
    unlocked = [a for a in data["achievements"] if a["unlocked"]]
    latest = sorted(unlocked, key=lambda a: a.get("unlocked_at") or 0, reverse=True)[:5]
    categories = sorted({a["category"] for a in data["achievements"]})
    return {"unlocked_count": data["unlocked_count"], "discovered_count": data["discovered_count"], "secret_count": data["secret_count"], "total_count": data["total_count"], "aggregate": data["aggregate"], "latest": latest, "categories": categories, "error": data.get("error")}


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
        result = evaluate_definition(definition, aggregate)
        if result["unlocked"]:
            badges.append(display_achievement({**definition, **result}))
    return {"session_id": session_id, "badges": badges}


@router.post("/rescan")
async def rescan():
    return {"ok": True, **evaluate_all()}


@router.post("/reset-state")
async def reset_state():
    save_state({"unlocks": {}})
    return {"ok": True}
