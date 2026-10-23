"""Self-contained HTML dashboard for the boost lifecycle (no network, no scripts from elsewhere)."""
import datetime as dt
import html
import json

HELD = {"held_working": "busy: switches when idle", "held_unrecognized_or_occupied_composer": "draft in composer: left alone",
        "held_picker_unavailable": "model picker did not open", "held_profile_unknown": "account unknown: left alone (exclusions active)",
        "live_unknown": "footer unreadable", "live_mismatch": "not at target (preview)", "live_readback_unknown": "switched, readback unclear",
        "error": "error"}


def esc(value):
    return html.escape("" if value is None else str(value))


def parse(value):
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")) if value else None
    except ValueError:
        return None


def ago(value, now):
    moment = parse(value)
    if not moment:
        return "-"
    seconds = (now - moment).total_seconds()
    future = seconds < 0
    seconds = abs(seconds)
    text = f"{seconds / 86400:.1f}d" if seconds >= 172800 else f"{seconds / 3600:.1f}h" if seconds >= 5400 else f"{seconds / 60:.0f}m"
    return ("in " + text) if future else (text + " ago")


def target_text(target):
    if not target:
        return "-"
    tier = target.get("tier")
    return f"{target['model']} · {target['effort']}" + (f" · {tier}" if tier and tier != "default" else "")


def footer_text(observed):
    return " ".join(observed) if isinstance(observed, (list, tuple)) and observed else "-"


def attention(state, report):
    """What a human should look at: unreached hosts, held panes, and anything still boosted after done."""
    items = []
    if not report:
        return items
    phase = state.get("phase", "idle")
    boost = state.get("boost_target") or {}
    for host, value in report.get("hosts", {}).items():
        for error in value.get("errors", []):
            items.append(("bad", host, error.get("path") or error.get("backend") or "host", error.get("error", "error")))
        if phase == "idle":
            # Outside a boost, differences from the baseline are someone's choice: summarize, don't alarm.
            differ = [row for row in value.get("configs", []) if row["status"] == "would_change"]
            if differ:
                seen = sorted({target_text(row.get("observed")) if row.get("observed") and "model" in row["observed"] else row["kind"] for row in differ})
                items.append(("info", host, f"{len(differ)} launch configs", "differ from the baseline: " + ", ".join(seen[:4])))
            panes = [row for row in value.get("terminals", []) if row["status"] != "verified"]
            if panes:
                seen = sorted({footer_text(row.get("observed")) for row in panes})
                items.append(("info", host, f"{len(panes)} live sessions", "differ from the baseline: " + ", ".join(seen[:4])))
            continue
        for row in value.get("configs", []):
            if row["status"] == "would_change":
                kind = "bad" if phase != "boosted" else "warn"
                items.append((kind, host, row["path"], f"config not at target ({target_text(row.get('target'))}); observed {row.get('observed')}"))
        for row in value.get("terminals", []):
            if row["status"] == "verified":
                continue
            observed = row.get("observed")
            still_boosted = phase != "boosted" and boost and isinstance(observed, (list, tuple)) and observed and \
                observed[0].lower() == boost.get("model", "").lower() and boost.get("model") != (state.get("baseline_target") or {}).get("model")
            kind = "bad" if still_boosted or row["status"] == "error" else "warn"
            note = HELD.get(row["status"], row["status"])
            if still_boosted:
                note = "STILL BOOSTED - " + note
            items.append((kind, host, f"{row.get('backend')} {row.get('pane')} ({row.get('profile') or 'account unknown'})",
                          f"{note}; footer {footer_text(observed)}"))
        for row in value.get("launch_overrides", []) or []:
            if row.get("status") == "explicit-mismatch":
                items.append(("warn", host, f"pid {row.get('pid')}", f"launched with explicit {row.get('model')} {row.get('effort') or ''}; takes effect on its next launch"))
    return items


def host_rows(report):
    rows = []
    for host, value in (report or {}).get("hosts", {}).items():
        configs = [row["status"] for row in value.get("configs", [])]
        live = [row["status"] for row in value.get("terminals", [])]
        rows.append({"host": host, "configs": len(configs), "at_target": configs.count("matches") + configs.count("changed"),
                     "changed": configs.count("changed"), "pending": configs.count("would_change"), "live": len(live),
                     "verified": live.count("verified"), "held": sum(status.startswith("held") for status in live),
                     "errors": len(value.get("errors", [])) + live.count("error"), "panes": value.get("terminals", []),
                     "desktop": value.get("desktop_task_overrides")})
    return rows


def bar(value, tone=""):
    if value is None:
        return '<span class="muted">-</span>'
    width = max(0, min(100, value))
    return f'<span class="bar {tone}"><span style="width:{width:.0f}%"></span></span><span class="num">{value:.0f}%</span>'


def render(state, usage, report, events, rows, presets, config):
    now = dt.datetime.now(dt.timezone.utc)
    phase = state.get("phase", "idle")
    items = attention(state, report)
    bad = sum(kind == "bad" for kind, *_ in items)
    warn = sum(kind == "warn" for kind, *_ in items)
    hosts = host_rows(report)
    accounts = (usage or {}).get("accounts") or {}
    rules = state.get("auto_down") or {}

    def section(title, body, extra=""):
        return f'<section class="card {extra}"><h2>{esc(title)}</h2>{body}</section>'

    if phase == "boosted":
        headline = f"Boosted to {esc(target_text(state.get('boost_target')))}"
        sub = f"since {esc(ago(state.get('started_at'), now))} · baseline {esc(state.get('baseline_name'))} ({esc(target_text(state.get('baseline_target')))})"
    elif phase == "cooling":
        headline = f"Turning down to {esc(target_text(state.get('baseline_target')))}"
        sub = f"ended {esc(ago(state.get('ended_at'), now))}: {esc(state.get('end_reason'))} · verifying until {esc(ago(state.get('cooling_until'), now))}"
    else:
        headline = f"At baseline: {esc(target_text(state.get('baseline_target')) if state.get('baseline_target') else 'normal')}"
        sub = "no boost running"
    auto = []
    if phase == "boosted":
        if rules.get("reset") and state.get("snapshot"):
            auto.append(f"when the reset lands on {rules.get('quorum', 0.5):.0%} of accounts")
        if rules.get("ceiling") is not None:
            auto.append(f"per account at {rules['ceiling']:.0f}%")
        if rules.get("until"):
            auto.append("deadline " + ago(rules["until"], now))
    hero = f'''<div class="hero {phase}">
  <div><span class="pill {phase}">{esc(phase.upper())}</span><h1>{headline}</h1><p class="muted">{sub}</p>
  {f'<p>Note: {esc(state.get("note"))}</p>' if state.get("note") else ''}
  {f'<p>Auto-down: {esc("; ".join(auto))}</p>' if auto else ('<p>Auto-down: off; run <code>reset_boost.py done</code></p>' if phase == "boosted" else '')}
  {f'<p>Pinned at baseline: {esc(", ".join(state.get("exclude") or []))}</p>' if state.get("exclude") else ''}
  {''.join(f'<p class="warn-text">Backed down {esc(p)}: {esc(why)}</p>' for p, why in (state.get("backed_down") or {}).items())}
  </div>
  <div class="stats">
    <div><b class="{'bad-text' if bad else ''}">{bad}</b><span>need action</span></div>
    <div><b>{sum(h['verified'] for h in hosts)}/{sum(h['live'] for h in hosts)}</b><span>live sessions at target</span></div>
    <div><b>{sum(h['at_target'] for h in hosts)}/{sum(h['configs'] for h in hosts)}</b><span>launch configs at target</span></div>
  </div>
</div>'''

    if items:
        body = "<ul class='attention'>" + "".join(
            f"<li class='{kind}'><b>{esc(host)}</b> <span class='path'>{esc(where)}</span><br>{esc(what)}</li>" for kind, host, where, what in items) + "</ul>"
    else:
        body = "<p class='ok-text'>Nothing needs attention in the latest run.</p>" if report else "<p class='muted'>No run recorded yet.</p>"
    if state.get("last_report"):
        body += f"<p class='muted small'>From {esc(state.get('last_report_at'))} ({esc(ago(state.get('last_report_at'), now))}) · exit {esc(state.get('last_exit'))} · {esc(state['last_report'])}</p>"
    attention_card = section("Needs attention" if bad or warn else "Check", body, "bad-card" if bad else "")

    if rows is not None:
        table = "".join(account_row(r, now) for r in rows)
        usage_body = f"<table><thead><tr><th>Account</th><th>At boost</th><th>Now</th><th>Resets</th><th>State</th></tr></thead><tbody>{table}</tbody></table>"
    elif accounts:
        lines = []
        for account in sorted(accounts.values(), key=lambda a: a["label"]):
            weekly = (account.get("windows") or {}).get("weekly") or {}
            session = (account.get("windows") or {}).get("session") or {}
            lines.append(f"<tr class='{'dim' if account.get('disabled') else ''}'><td>{esc(account['label'])}<div class='muted small'>{esc(account.get('profile') or '')} {esc(account.get('plan') or '')}</div></td>"
                         f"<td>{bar(weekly.get('used'), 'hot' if (weekly.get('used') or 0) >= 90 else '')}</td><td>{esc(ago(weekly.get('resets_at'), now))}</td>"
                         f"<td>{bar(session.get('used'))}</td><td>{esc(ago(session.get('resets_at'), now))}</td></tr>")
        usage_body = f"<table><thead><tr><th>Account</th><th>Weekly</th><th>Resets</th><th>5-hour</th><th>Resets</th></tr></thead><tbody>{''.join(lines)}</tbody></table>"
    else:
        usage_body = f"<p class='muted'>No usage data{': ' + esc(state.get('usage_error')) if state.get('usage_error') else ''}.</p>"
    if usage and usage.get("at"):
        usage_body += f"<p class='muted small'>Usage read {esc(ago(usage['at'], now))}{' · source error: ' + esc(state.get('usage_error')) if state.get('usage_error') else ''}</p>"
    usage_card = section("Accounts and resets", usage_body)

    host_html = [host_row(h) for h in hosts]
    hosts_card = section("Hosts", f"<table><thead><tr><th>Host</th><th>Launch configs</th><th>Live sessions</th><th>Errors</th></tr></thead><tbody>{''.join(host_html)}</tbody></table>"
                         "<p class='muted small'>Desktop-app tasks cannot be read or switched; they pick up launch defaults on their next start.</p>" if hosts else "<p class='muted'>No run recorded yet.</p>")

    preset_rows = "".join(f"<tr><td><code>{esc(name)}</code></td><td>{esc(target_text(value))}</td><td class='muted'>{esc(value.get('description', ''))}</td>"
                          f"<td><button data-copy='reset_boost.py boost --preset {esc(name)}'>copy</button></td></tr>" for name, value in presets.items())
    commands = [("Turn up", "reset_boost.py boost --preset astra-ultra-fast --note 'reset window'"), ("Turn up for 6h", "reset_boost.py boost --preset sol-high --until 6h"),
                ("Turn down now", "reset_boost.py done"), ("Status", "reset_boost.py status --refresh")]
    lever = "".join(f"<div class='cmd'><span>{esc(label)}</span><code>{esc(command)}</code><button data-copy=\"{esc(command)}\">copy</button></div>" for label, command in commands)
    lever_card = section("Levers", lever + f"<details><summary>Presets</summary><table><tbody>{preset_rows}</tbody></table></details>")

    timeline = "".join(f"<li><span class='muted'>{esc(ago(e.get('at'), now))}</span> <b>{esc(e.get('event'))}</b> "
                       f"{esc(summary(e))}</li>" for e in reversed(events[-60:]))
    timeline_card = section("Timeline", f"<ul class='timeline'>{timeline}</ul>" if timeline else "<p class='muted'>No events yet.</p>")

    return PAGE.replace("{{BODY}}", hero + "<div class='grid'>" + attention_card + lever_card + "</div>" + usage_card + hosts_card + timeline_card) \
        .replace("{{GENERATED}}", esc(now.strftime("%Y-%m-%d %H:%M UTC"))).replace("{{PHASE}}", esc(phase))


def account_row(r, now):
    tone = "dim" if r["excluded"] or r["disabled"] else ""
    tags = ""
    if r["excluded"]:
        tags += '<span class="pill-sm">pinned</span>'
    if r["disabled"]:
        tags += '<span class="pill-sm">disabled</span>'
    if r["reset"]:
        tags += '<span class="pill-sm ok">reset: ' + esc(r["reset"]) + "</span>"
    hot = "hot" if (r["now"] or 0) >= 90 else ""
    return (f'<tr class="{tone}"><td>{esc(r["label"])}<div class="muted small">{esc(r["profile"] or "")} {esc(r["plan"] or "")}</div></td>'
            f'<td>{bar(r["before"])}</td><td>{bar(r["now"], hot)}</td><td>{esc(ago(r["resets_at"], now))}</td><td>{tags}</td></tr>')


def pane_row(p):
    verified = p["status"] == "verified"
    status = "at target" if verified else HELD.get(p["status"], p["status"])
    return (f'<tr><td>{esc(p.get("backend"))} {esc(p.get("pane"))}</td><td>{esc(p.get("profile") or "?")}</td><td>{esc(footer_text(p.get("observed")))}</td>'
            f'<td>{esc(target_text(p.get("target")))}</td><td class="{"ok-text" if verified else "warn-text"}">{esc(status)}</td></tr>')


def host_row(h):
    detail = ""
    if h["panes"]:
        panes = "".join(pane_row(p) for p in h["panes"])
        detail = (f'<details><summary>{h["live"]} live sessions</summary><table><thead><tr><th>Pane</th><th>Account</th><th>Footer</th>'
                  f'<th>Target</th><th>Status</th></tr></thead><tbody>{panes}</tbody></table></details>')
    pending = f' <span class="warn-text">({h["pending"]} pending)</span>' if h["pending"] else ""
    held = f' · {h["held"]} held' if h["held"] else ""
    errors = "bad-text" if h["errors"] else ""
    return (f'<tr><td><b>{esc(h["host"])}</b></td><td>{h["at_target"]}/{h["configs"]}{pending}</td><td>{h["verified"]}/{h["live"]}{held}</td>'
            f'<td class="{errors}">{h["errors"]}</td></tr><tr class="sub"><td colspan="4">{detail}</td></tr>')


def summary(event):
    kind = event.get("event")
    if kind == "boost":
        return f"{event.get('name')} on {', '.join(event.get('hosts') or [])}" + (f" - {event['note']}" if event.get("note") else "")
    if kind == "done":
        return event.get("reason") or ""
    if kind in ("applied", "converged", "audited"):
        return f"{event.get('phase', '')} exit {event.get('exit')}"
    if kind == "backed_down":
        return f"{event.get('profile')}: {event.get('reason')}"
    if kind == "idle":
        return event.get("outcome") or ""
    return json.dumps({k: v for k, v in event.items() if k not in ("at", "event")})[:160]


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60"><title>Codex Clanker Cranker</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#16181d;--muted:#667085;--line:#e4e7ec;--ok:#067647;--warn:#b54708;--bad:#b42318;--accent:#5b3fd6;--boost:#efe9ff;--cool:#e6f4ff;--idle:#eef2f6;--barbg:#eaecf0}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0f1115;--card:#171a21;--ink:#e6e8ec;--muted:#98a2b3;--line:#2a2f3a;--ok:#47cd89;--warn:#fdb022;--bad:#f97066;--accent:#9e8cff;--boost:#241d3d;--cool:#14283a;--idle:#1b1f27;--barbg:#2a2f3a}}
:root[data-theme="dark"]{--bg:#0f1115;--card:#171a21;--ink:#e6e8ec;--muted:#98a2b3;--line:#2a2f3a;--ok:#47cd89;--warn:#fdb022;--bad:#f97066;--accent:#9e8cff;--boost:#241d3d;--cool:#14283a;--idle:#1b1f27;--barbg:#2a2f3a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:1100px;margin:0 auto;padding:20px 16px 48px}header{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap}
header h3{margin:0;font-size:15px}.muted{color:var(--muted)}.small{font-size:12px}
.hero{display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap;padding:20px;border-radius:14px;margin:14px 0;border:1px solid var(--line)}
.hero.boosted{background:var(--boost)}.hero.cooling{background:var(--cool)}.hero.idle{background:var(--idle)}
.hero h1{margin:8px 0 4px;font-size:22px}.hero p{margin:4px 0}
.stats{display:flex;gap:18px;flex-wrap:wrap}.stats div{display:flex;flex-direction:column;min-width:110px}.stats b{font-size:24px}.stats span{color:var(--muted);font-size:12px}
.pill{display:inline-block;padding:2px 10px;border-radius:99px;font-weight:600;font-size:12px;letter-spacing:.04em;background:var(--card);border:1px solid var(--line)}
.pill.boosted{color:var(--accent)}.pill.cooling{color:#1570ef}.pill-sm{display:inline-block;padding:1px 8px;border-radius:99px;font-size:11px;border:1px solid var(--line);margin-right:4px}.pill-sm.ok{color:var(--ok)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-bottom:14px;min-width:0;overflow-x:auto}
.card h2{margin:0 0 10px;font-size:15px}.bad-card{border-color:var(--bad)}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}th{font-size:12px;color:var(--muted);font-weight:600}
tr.dim td{opacity:.5}tr.sub td{border-bottom:none;padding-top:0}
.bar{display:inline-block;width:70px;height:6px;border-radius:3px;background:var(--barbg);vertical-align:middle;margin-right:6px;overflow:hidden}.bar span{display:block;height:100%;background:var(--accent)}.bar.hot span{background:var(--bad)}
.num{font-variant-numeric:tabular-nums}
.attention{list-style:none;padding:0;margin:0}.attention li{padding:8px 10px;border-left:3px solid var(--warn);margin-bottom:6px;background:var(--bg);border-radius:4px;word-break:break-word}.attention li.bad{border-color:var(--bad)}.attention li.info{border-color:var(--line)}
.path{color:var(--muted);font-family:ui-monospace,Menlo,monospace;font-size:12px}
.ok-text{color:var(--ok)}.warn-text{color:var(--warn)}.bad-text{color:var(--bad)}
.cmd{display:flex;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap}.cmd span{min-width:110px;color:var(--muted)}
code{font-family:ui-monospace,Menlo,monospace;font-size:12px;background:var(--bg);padding:2px 6px;border-radius:4px;word-break:break-all}
button{font:inherit;font-size:12px;padding:2px 10px;border-radius:6px;border:1px solid var(--line);background:var(--card);color:var(--ink);cursor:pointer}
.timeline{list-style:none;padding:0;margin:0}.timeline li{padding:4px 0;border-bottom:1px dashed var(--line)}
details summary{cursor:pointer;color:var(--muted);margin:4px 0}
</style></head>
<body><main data-phase="{{PHASE}}"><header><h3>Codex Clanker Cranker</h3><span class="muted small">Generated {{GENERATED}} · refreshes every minute</span></header>
{{BODY}}
</main>
<script>
document.addEventListener('click', function (event) {
  var text = event.target.getAttribute && event.target.getAttribute('data-copy');
  if (!text) return;
  navigator.clipboard.writeText(text).then(function () { event.target.textContent = 'copied'; setTimeout(function () { event.target.textContent = 'copy'; }, 1200); });
});
</script></body></html>
"""
