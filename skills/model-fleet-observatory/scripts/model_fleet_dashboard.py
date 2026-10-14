#!/usr/bin/env python3
"""Private, provider-neutral model fleet snapshot collector and HTML server."""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
from pathlib import Path
import shlex
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

SCHEMA = "g-skills.model-fleet-observatory.snapshot.v1"
DEFAULT_INTERVAL = 600
MODEL_FIELDS = {"model", "model_reasoning_effort", "reasoning", "effort"}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def unknown(value) -> str:
    return str(value) if value not in (None, "", []) else "UNKNOWN"


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("configuration must be a JSON object")
    return value


def session_row(raw: dict, index: int, source: dict) -> dict:
    if not isinstance(raw, dict):
        raw = {}
    model = raw.get("model")
    reasoning = raw.get("reasoning", raw.get("effort", raw.get("model_reasoning_effort")))
    profile = raw.get("profile")
    account = raw.get("account")
    return {
        "id": unknown(raw.get("id", f"session-{index + 1}")),
        "account": unknown(account),
        "profile": unknown(profile),
        "model": unknown(model),
        "reasoning": unknown(reasoning),
        "backend": unknown(raw.get("backend", "unknown")),
        "status": raw.get("status", "observed") if raw.get("status") in {"observed", "stale", "error", "unknown"} else "unknown",
        "evidence": {**source, **(raw.get("evidence") if isinstance(raw.get("evidence"), dict) else {})},
    }


def normalize_sessions(rows, source: dict) -> list[dict]:
    if not isinstance(rows, list):
        raise ValueError("adapter sessions must be an array")
    return [session_row(row, index, source) for index, row in enumerate(rows)]


def box_from_payload(raw: dict, box: dict, source: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("adapter output must be an object")
    rows = raw.get("sessions", [])
    return {
        "id": unknown(raw.get("id", box.get("id", "unknown-box"))),
        "label": unknown(raw.get("label", box.get("label", box.get("id", "Unknown box")))),
        "status": raw.get("status", "ok") if raw.get("status", "ok") in {"ok", "error", "unknown"} else "unknown",
        "source": {**source, **(raw.get("source") if isinstance(raw.get("source"), dict) else {})},
        "sessions": normalize_sessions(rows, source),
    }


def unknown_box(box: dict, source: dict, detail: str) -> dict:
    return {
        "id": unknown(box.get("id", "unknown-box")),
        "label": unknown(box.get("label", box.get("id", "Unknown box"))),
        "status": "unknown",
        "source": {**source, "detail": detail[:240]},
        "sessions": [session_row({"id": "box-status", "backend": box.get("backend", "unknown"), "status": "unknown"}, 0, source)],
    }


def run_adapter(box: dict, default_timeout: float) -> dict:
    command = box.get("command")
    source = {"kind": "adapter-command", "status": "observed", "checked_at": utc_now()}
    if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
        return unknown_box(box, {**source, "status": "unknown"}, "missing argv adapter command")
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=float(box.get("timeout_s", default_timeout)), check=False)
        if result.returncode:
            return unknown_box(box, {**source, "status": "unknown"}, f"adapter exit {result.returncode}")
        payload = json.loads(result.stdout)
        source["command"] = shlex.join(command)
        return box_from_payload(payload, box, source)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as error:
        return unknown_box(box, {**source, "status": "unknown"}, type(error).__name__)


def local_process_box() -> dict:
    source = {"kind": "process-argv", "status": "observed", "checked_at": utc_now(), "command": "ps"}
    rows = []
    try:
        output = subprocess.check_output(["ps", "-axo", "pid=,comm=,args="], text=True, timeout=5)
        for line in output.splitlines():
            fields = line.strip().split(None, 2)
            if len(fields) != 3 or Path(fields[1]).name not in {"codex", "codex-cli"}:
                continue
            pid, _, args = fields
            try:
                argv = shlex.split(args)
            except ValueError:
                argv = args.split()
            model = effort = profile = None
            i = 0
            while i < len(argv):
                arg = argv[i]
                if arg in {"-m", "--model", "--profile"} and i + 1 < len(argv):
                    if arg == "--profile":
                        profile = argv[i + 1]
                    else:
                        model = argv[i + 1]
                    i += 2
                    continue
                if arg.startswith("--model="):
                    model = arg.split("=", 1)[1]
                elif arg.startswith("--profile="):
                    profile = arg.split("=", 1)[1]
                elif arg.startswith("model_reasoning_effort="):
                    effort = arg.split("=", 1)[1]
                i += 1
            rows.append({"id": f"pid-{pid}", "profile": profile, "model": model, "reasoning": effort, "backend": "codex", "status": "observed", "evidence": {"pid": pid}})
    except (OSError, subprocess.SubprocessError) as error:
        return unknown_box({"id": "local", "label": "Local host"}, {**source, "status": "unknown"}, type(error).__name__)
    return box_from_payload({"sessions": rows}, {"id": "local", "label": "Local host"}, source)


def collect(config_path: Path | None = None, discover_local: bool = False) -> dict:
    config = read_json(config_path) if config_path and config_path.exists() else {}
    interval = int(config.get("refresh_interval_s", DEFAULT_INTERVAL))
    if interval < 10 or interval > 86400:
        raise ValueError("refresh_interval_s must be between 10 and 86400")
    boxes = []
    for box in config.get("boxes", []):
        if not isinstance(box, dict):
            continue
        if isinstance(box.get("payload"), dict):
            boxes.append(box_from_payload(box["payload"], box, {"kind": "static", "status": "observed", "checked_at": utc_now()}))
        else:
            boxes.append(run_adapter(box, min(interval, 30)))
    if discover_local or not boxes:
        local = local_process_box()
        if not any(item["id"] == local["id"] for item in boxes):
            boxes.insert(0, local)
    return {"schema": SCHEMA, "generated_at": utc_now(), "refresh_interval_s": interval, "boxes": boxes}


def evidence_counts(snapshot: dict) -> tuple[int, int]:
    sessions = [row for box in snapshot.get("boxes", []) for row in box.get("sessions", [])]
    aliases = {row.get("account") for row in sessions if row.get("account") not in (None, "", "UNKNOWN")}
    aliases.update(row.get("profile") for row in sessions if row.get("profile") not in (None, "", "UNKNOWN"))
    return len(snapshot.get("boxes", [])), len(aliases)


HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Model Fleet Observatory</title>
<style>
:root{color-scheme:dark;--bg:#08111f;--panel:#101d31;--line:#263a55;--text:#e6eef9;--muted:#9db0c8;--good:#59d6a1;--warn:#f4c76a;--bad:#ff8e8e}*{box-sizing:border-box}body{margin:0;background:linear-gradient(135deg,#08111f,#0e1b2d);color:var(--text);font:15px/1.45 system-ui,-apple-system,sans-serif}main{max-width:1440px;margin:auto;padding:28px}header{display:flex;justify-content:space-between;gap:18px;align-items:flex-end;margin-bottom:20px}h1{margin:0;font-size:clamp(1.6rem,3vw,2.6rem)}p{color:var(--muted)}.toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.metric{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 16px;min-width:120px}.metric b{display:block;font-size:1.6rem}.metric span{color:var(--muted);font-size:.8rem}.status{color:var(--good)}button,input{background:#172842;border:1px solid var(--line);color:var(--text);border-radius:8px;padding:9px 11px}input{min-width:240px}.box{background:rgba(16,29,49,.9);border:1px solid var(--line);border-radius:14px;margin:16px 0;overflow:hidden}.box-head{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:16px 18px;border-bottom:1px solid var(--line)}.box-head h2{margin:0;font-size:1.15rem}.badge{border-radius:999px;padding:3px 9px;font-size:.75rem}.ok{color:var(--good);background:#123b31}.unknown{color:var(--warn);background:#4a3514}.error{color:var(--bad);background:#4a2028}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;min-width:820px}th,td{text-align:left;padding:11px 14px;border-bottom:1px solid #1d3049}th{color:var(--muted);font-size:.75rem;text-transform:uppercase;letter-spacing:.06em}tr:focus{outline:2px solid var(--good);outline-offset:-2px}.empty{padding:18px;color:var(--muted)}kbd{border:1px solid var(--line);border-radius:4px;padding:1px 5px;color:var(--muted)}dialog{background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:12px;padding:22px;max-width:420px}dialog::backdrop{background:#0008}
</style></head><body><main><header><div><h1>Model Fleet Observatory</h1><p>Launch and live-readback evidence across authorized boxes. Unsupported surfaces stay visible as UNKNOWN.</p></div><div class="toolbar"><input id="filter" aria-label="Filter sessions" placeholder="Filter sessions (/)"><button id="refresh">Refresh <kbd>r</kbd></button><button id="help">Help <kbd>?</kbd></button></div></header><section class="toolbar" aria-label="Fleet counters"><div class="metric"><b id="box-count">0</b><span>boxes</span></div><div class="metric"><b id="session-count">0</b><span>sessions</span></div><div class="metric"><b id="account-count">?</b><span>observed profiles/accounts</span></div><div class="metric"><b id="last-refresh">—</b><span>last refresh</span></div><div class="metric"><b id="next-refresh">—</b><span>next refresh</span></div></section><p id="status" class="status" role="status">Loading…</p><section id="boxes" aria-live="polite"></section><dialog id="help-dialog"><h2>Keyboard controls</h2><p><kbd>r</kbd> refresh now · <kbd>/</kbd> focus filter · <kbd>j</kbd>/<kbd>k</kbd> move between session rows · <kbd>?</kbd> toggle this help</p><button id="close-help">Close</button></dialog></main><script>
const state={snapshot:null,selected:0};const $=id=>document.getElementById(id);const esc=s=>String(s??'UNKNOWN').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function rows(){return [...document.querySelectorAll('tbody tr')]}function render(s){state.snapshot=s;const boxes=s.boxes||[];let sessionTotal=0;let aliases=new Set();$('box-count').textContent=boxes.length;for(const b of boxes){for(const row of b.sessions||[]){sessionTotal++;if(row.account&&row.account!=='UNKNOWN')aliases.add(row.account);if(row.profile&&row.profile!=='UNKNOWN')aliases.add(row.profile)}}$('session-count').textContent=sessionTotal;$('account-count').textContent=aliases.size||'?';const when=new Date(s.generated_at);$('last-refresh').textContent=when.toLocaleTimeString();$('next-refresh').dataset.at=Date.now()+s.refresh_interval_s*1000;drawNext();const query=$('filter').value.toLowerCase();$('boxes').innerHTML=boxes.map(b=>{const rs=(b.sessions||[]).filter(r=>JSON.stringify(r).toLowerCase().includes(query));return `<article class="box"><div class="box-head"><div><h2>${esc(b.label)}</h2><small>${esc(b.source?.kind||'unknown')} · ${esc(b.source?.checked_at||'no timestamp')}</small></div><span class="badge ${esc(b.status)}">${esc(b.status)}</span></div><div class="table-wrap"><table><thead><tr><th>Session</th><th>Model</th><th>Reasoning</th><th>Profile</th><th>Backend</th><th>Evidence</th></tr></thead><tbody>${rs.length?rs.map(r=>`<tr tabindex="0"><td>${esc(r.id)}</td><td>${esc(r.model)}</td><td>${esc(r.reasoning)}</td><td>${esc(r.profile)}</td><td>${esc(r.backend)}</td><td>${esc(r.status)}</td></tr>`).join(''):`<tr><td colspan="6" class="empty">No matching observed sessions</td></tr>`}</tbody></table></div></article>`}).join('');$('status').textContent=`Updated ${when.toLocaleString()} · ${boxes.length} box${boxes.length===1?'':'es'}`}
function drawNext(){const at=Number($('next-refresh').dataset.at||0);if(!at)return;$('next-refresh').textContent=Math.max(0,Math.ceil((at-Date.now())/1000))+'s'}async function refresh(){try{const r=await fetch('/api/refresh',{cache:'no-store'});if(!r.ok)throw Error(r.status);render(await r.json())}catch(e){$('status').textContent='Refresh failed: '+e;$('status').style.color='var(--bad)'}}$('refresh').onclick=refresh;$('filter').oninput=()=>state.snapshot&&render(state.snapshot);$('help').onclick=()=>$('help-dialog').showModal();$('close-help').onclick=()=>$('help-dialog').close();document.onkeydown=e=>{if(e.key==='/'&&document.activeElement!==$('filter')){e.preventDefault();$('filter').focus()}else if(e.key==='r'&&document.activeElement!==$('filter'))refresh();else if(e.key==='?'&&document.activeElement!==$('filter'))$('help-dialog').open?$('help-dialog').close():$('help-dialog').showModal();else if((e.key==='j'||e.key==='k')&&document.activeElement!==$('filter')){const r=rows();if(r.length){state.selected=Math.max(0,Math.min(r.length-1,state.selected+(e.key==='j'?1:-1)));r[state.selected].focus()}}};setInterval(drawNext,1000);setInterval(refresh,600000);refresh();
</script></body></html>'''


class LiveState:
    def __init__(self, config: Path | None, discover_local: bool, interval: int):
        self.config = config
        self.discover_local = discover_local
        self.interval = interval
        self.lock = threading.Lock()
        self.snapshot = collect(config, discover_local)

    def refresh(self) -> dict:
        snapshot = collect(self.config, self.discover_local)
        with self.lock:
            self.snapshot = snapshot
            return dict(snapshot)

    def read(self) -> dict:
        with self.lock:
            return dict(self.snapshot)


def make_server(state: LiveState, bind: str, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            route = urlparse(self.path).path
            if route == "/api/snapshot":
                payload = json.dumps(state.read(), separators=(",", ":")).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload); return
            if route == "/api/refresh":
                payload = json.dumps(state.refresh(), separators=(",", ":")).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload); return
            if route == "/healthz":
                payload = b"ok\n"; self.send_response(200); self.send_header("Content-Type", "text/plain"); self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload); return
            if route in {"/", "/index.html"}:
                payload = HTML.encode(); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload); return
            self.send_error(404)

        def log_message(self, *_args):
            return

    return ThreadingHTTPServer((bind, port), Handler)


def command_doctor(config: Path | None) -> int:
    try:
        if config and config.exists():
            value = read_json(config); collect(config, False)
            print(json.dumps({"status": "ok", "config": str(config), "boxes": len(value.get("boxes", []))}, indent=2))
        else:
            print(json.dumps({"status": "ok", "config": str(config) if config else None, "boxes": 0, "detail": "local discovery is available"}, indent=2))
        return 0
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "fail", "detail": type(error).__name__ + ": " + str(error)})); return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("doctor", "snapshot", "serve"):
        p = sub.add_parser(name); p.add_argument("--config", type=Path); p.add_argument("--discover-local", action="store_true")
        if name == "snapshot": p.add_argument("--out", type=Path, required=True)
        if name == "serve": p.add_argument("--bind", default="127.0.0.1"); p.add_argument("--port", type=int, default=8765); p.add_argument("--interval", type=int, default=DEFAULT_INTERVAL)
    args = parser.parse_args(argv)
    if args.command == "doctor": return command_doctor(args.config)
    if args.command == "snapshot":
        try:
            snapshot = collect(args.config, args.discover_local); args.out.parent.mkdir(parents=True, exist_ok=True); args.out.write_text(json.dumps(snapshot, indent=2) + "\n"); print(json.dumps({"status": "ok", "out": str(args.out), "boxes": len(snapshot["boxes"])})); return 0
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
            print(f"FAIL: {type(error).__name__}: {error}", file=os.sys.stderr); return 1
    try:
        state = LiveState(args.config, args.discover_local, args.interval); server = make_server(state, args.bind, args.port)
        timer = threading.Event()
        def loop():
            while not timer.wait(max(10, args.interval)):
                try: state.refresh()
                except Exception: pass
        thread = threading.Thread(target=loop, daemon=True); thread.start(); print(f"Serving model fleet dashboard on http://{args.bind}:{server.server_port}", flush=True)
        try: server.serve_forever()
        except KeyboardInterrupt: pass
        finally: timer.set(); server.shutdown(); server.server_close()
        return 0
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        print(f"FAIL: {type(error).__name__}: {error}", file=os.sys.stderr); return 1


if __name__ == "__main__":
    raise SystemExit(main())
