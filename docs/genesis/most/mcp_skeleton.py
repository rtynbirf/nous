#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ПРОТОКОЛ-МОСТ · пролёт «руки»: минимальный MCP-сервер дома rtynbirf.
Статус: ЧЕРНОВИК КОНВОЯ (дубль два, 2026-11-20) — не принят домом; для принятия
нужен тикет в tasks/README.md nous и сверка с живой спекой MCP (Linux Foundation,
09.12.2025). Stdlib-only по духу дома (офлайн-первый, без зависимостей).

Протокол: JSON-RPC 2.0 поверх stdio (фрейминг MCP-совместимый: по строке).
Методы: initialize, tools/list, tools/call.
Инструменты:
  - list_cells  : живой срез витринных клеток дома (GitHub API, без токена;
                  лимит 60/час — поэтому срез кешируется в памяти на 10 минут)
  - cell_tags   : теги клетки через git ls-remote (без лимитов API)
  - house_pulse : строка-формула дома: 80 клеток · 9493 коммита · ρ̇ > 0 (снимок 20 XI 2026)

Запуск: python3 mcp_skeleton.py   (stdio; тест: echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 mcp_skeleton.py)
"""
import json, subprocess, sys, time, urllib.request

OWNER = "rtynbirf"
SHOWCASE = ["nous", "polymath-os", "cell-swarm", "runtime-protocol", "lex-naturae",
            "karta", "singulyar", "release-vault", "khozyain", "agryp"]
PULSE = "80 клеток · 9493 коммита · 3 подписчика · ρ̇ > 0 (снимок SWARM-SYNC 2026-11-20)"
_cache = {"ts": 0.0, "cells": None}

TOOLS = [
    {"name": "list_cells", "description": "Живой срез витринных клеток дома rtynbirf: имя + описание из GitHub API (снимок кешируется 10 минут).",
     "inputSchema": {"type": "object", "properties": {}, "required": []}},
    {"name": "cell_tags", "description": "Теги клетки дома через git ls-remote — без лимитов API.",
     "inputSchema": {"type": "object", "properties": {"repo": {"type": "string", "description": "имя клетки, например nous"}}, "required": ["repo"]}},
    {"name": "house_pulse", "description": "Строка-пульс дома (снимок суточной сверки).",
     "inputSchema": {"type": "object", "properties": {}, "required": []}},
]

def list_cells():
    if _cache["cells"] and time.time() - _cache["ts"] < 600:
        return _cache["cells"]
    cells = []
    for r in SHOWCASE:
        try:
            with urllib.request.urlopen(f"https://api.github.com/repos/{OWNER}/{r}", timeout=10) as resp:
                d = json.load(resp)
            cells.append({"repo": r, "description": (d.get("description") or "")[:160],
                          "pushed_at": d.get("pushed_at")})
        except Exception as e:
            cells.append({"repo": r, "error": str(e)[:120]})
    _cache.update(ts=time.time(), cells=cells)
    return cells

def cell_tags(repo):
    res = subprocess.run(["git", "ls-remote", "--tags", f"https://github.com/{OWNER}/{repo}.git"],
                         capture_output=True, text=True, timeout=30)
    return [ln.split("refs/tags/")[-1] for ln in res.stdout.splitlines() if "refs/tags/" in ln]

def call_tool(name, args):
    if name == "list_cells":
        return list_cells()
    if name == "cell_tags":
        return cell_tags(str(args.get("repo", "nous")))  # вход чужой — только имя репо
    if name == "house_pulse":
        return {"pulse": PULSE}
    raise ValueError(f"неизвестный инструмент: {name}")

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            m = req.get("method", "")
            if m == "initialize":
                result = {"protocolVersion": req.get("params", {}).get("protocolVersion", ""),
                          "capabilities": {"tools": {}},
                          "serverInfo": {"name": "rtynbirf-house-bridge", "version": "0.1.0-draft"}}
            elif m == "tools/list":
                result = {"tools": TOOLS}
            elif m == "tools/call":
                args = (req.get("params") or {}).get("arguments") or {}
                result = {"content": [{"type": "text",
                          "text": json.dumps(call_tool((req.get("params") or {}).get("name", ""), args),
                                             ensure_ascii=False)}]}
            elif m == "ping":
                result = {}
            else:
                raise ValueError(f"метод не поддержан: {m}")
            print(json.dumps({"jsonrpc": "2.0", "id": req.get("id"), "result": result}, ensure_ascii=False), flush=True)
        except Exception as e:
            print(json.dumps({"jsonrpc": "2.0", "id": req.get("id") if isinstance(req := json.loads(line), dict) else None,
                              "error": {"code": -32603, "message": str(e)[:200]}}, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    main()
