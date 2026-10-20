import html
import os
import statistics
from collections import Counter, defaultdict

from .core import NOW, STATE, pct, short_model, tier
from .reports import _git_output, findings, task_table

TIERS = [("opus", "Opus"), ("sonnet", "Sonnet"), ("haiku", "Haiku"), ("other", "Other")]
BUILD = ("implement", "fix")
REVIEW = ("review", "final-review", "re-review")


def esc(s):
    return html.escape(str(s), quote=True)


def fmt_k(n):
    return "%dk" % round(n / 1000) if n < 1e6 else "%.2fM" % (n / 1e6)


def collect(ps, cwds, with_git=True):
    nrepos, commits, lines = _git_output(cwds, ps) if with_git else (0, defaultdict(set), Counter())
    tasks, final = task_table(ps)
    out = {"generated": NOW.astimezone().strftime("%Y-%m-%d %H:%M"), "repos": nrepos, "git": with_git, "periods": []}
    for p in ps:
        act = max(1e-9, p.active_hours)
        by_tier = Counter()
        by_role = Counter()
        for s in p.subs:
            t = tier(s["model"]) or "other"
            if t == "fable":
                t = "other"
            by_tier[t] += s["cost"]
            group = "build" if s["role"] in BUILD else ("review" if s["role"] in REVIEW else "other")
            by_role[(group, t)] += s["cost"]
        q = defaultdict(list)
        for t in tasks.values():
            if t["impl"] and t["reviews"] and t["period"] == p.key:
                q[t["impl"]].append(t)
        quality = []
        for model, xs in sorted(q.items()):
            first = [t["reviews"][0] for t in xs]
            n = len(xs)
            quality.append({
                "model": model, "tasks": n,
                "approved": sum(ok for _, ok in first) / n,
                "critical": sum(c["Critical"] for c, _ in first) / n,
                "important": sum(c["Important"] for c, _ in first) / n,
                "minor": sum(c["Minor"] for c, _ in first) / n,
                "rounds": sum(t["rounds"] for t in xs) / n,
                "cost": pct([t["cost"] for t in xs], 0.5),
            })
        esc_n = esc_c = esc_i = 0
        for run, c in final.items():
            pks = {t["period"] for (r, _), t in tasks.items() if r == run and t["impl"]}
            if pks == {p.key}:
                esc_n += sum(1 for (r, _), t in tasks.items() if r == run and t["impl"])
                esc_c += c["Critical"]
                esc_i += c["Important"]
        br = [s for s in p.subs if s["agent"].endswith("bulk-reader")]
        out["periods"].append({
            "key": p.key, "label": p.label,
            "start": p.a.astimezone().strftime("%d %b %H:%M"), "end": p.b.astimezone().strftime("%d %b %H:%M"),
            "hours": p.hours, "active": p.active_hours, "session_hours": p.session_hours,
            "cost": p.cost, "cost_main": p.cost_main, "cost_sub": p.cost_sub,
            "per_active": p.cost / act, "per_wall": p.cost / p.hours, "per_turn": p.cost / max(1, p.turns),
            "turns": p.turns, "sessions": len(p.peaks),
            "mean_ctx": statistics.mean(p.ctx) if p.ctx else 0, "p90_ctx": pct(p.ctx, 0.9),
            "over500": sum(c > 500000 for c in p.ctx) / max(1, p.turns),
            "auto": sum(t == "auto" for t, _ in p.compactions), "manual": sum(t == "manual" for t, _ in p.compactions),
            "commits": len(commits[p.key]), "lines": lines[p.key],
            "sub_tier": {t: by_tier[t] / act for t, _ in TIERS},
            "sub_role": {"%s/%s" % kv: v / act for kv, v in by_role.items()},
            "quality": quality,
            "escapes": {"tasks": esc_n, "critical": esc_c / max(1, esc_n), "important": esc_i / max(1, esc_n)},
            "bulk": {"calls": len(br), "bullets": sum(_bullets(s["reply"]) for s in br), "reply": pct([len(s["reply"]) / 4 for s in br], 0.5), "latency": pct([s["seconds"] for s in br], 0.5)},
            "gate": {"blocks": p.gate_blocks, "big_reads": p.full_big_reads, "tools": p.tool_calls, "followups": dict(p.followups)},
        })
    out["routing"] = _routing()
    return out


def _bullets(reply):
    lines = [ln for ln in reply.strip().splitlines() if ln.strip()]
    return bool(lines) and all(ln.lstrip().startswith("- ") for ln in lines)


def _routing():
    c = Counter()
    reasons = []
    try:
        with open(os.path.join(STATE, "routing.log")) as fh:
            for ln in fh:
                parts = ln.rstrip("\n").split("\t")
                if len(parts) >= 5:
                    decision = parts[1].replace("+checklist", "")
                    c[(decision, parts[2])] += 1
                    if "+checklist" in parts[1]:
                        c[("checklist added", parts[2])] += 1
                    if decision == "allowed-with-reason":
                        reasons.append({"at": parts[0][5:16].replace("T", " "), "desc": parts[4], "reason": (parts[5] if len(parts) > 5 else "").replace("OPUS-REASON:", "").strip()})
    except OSError:
        pass
    return {"counts": [{"decision": d, "kind": k, "n": n} for (d, k), n in sorted(c.items())], "reasons": reasons[-8:]}


def delta_chip(value, base, lower_is_better=True, fmt="%+.0f%%"):
    if not base:
        return ""
    d = (value - base) / base
    if abs(d) < 0.02:
        cls = "flat"
    elif (d < 0) == lower_is_better:
        cls = "good"
    else:
        cls = "bad"
    return '<span class="chip %s">%s</span>' % (cls, fmt % (100 * d))


def hbars(rows, unit_fmt, ref=None, ref_label=""):
    """rows: [(label, value, tick_or_None)] drawn on one shared scale."""
    top = max([v for _, v, _ in rows] + [t or 0 for _, _, t in rows] + [ref or 0]) * 1.12 or 1
    h = 30
    W = 640
    L = 150
    R = 86
    span = W - L - R
    svg = ['<svg viewBox="0 0 %d %d" class="chart" role="img">' % (W, h * len(rows) + 26)]
    if ref:
        x = L + span * ref / top
        svg.append('<line x1="%.1f" x2="%.1f" y1="4" y2="%d" class="ref"/>' % (x, x, h * len(rows) + 4))
        svg.append('<text x="%.1f" y="%d" class="axis" text-anchor="middle">%s</text>' % (x, h * len(rows) + 20, esc(ref_label)))
    for i, (label, v, tick) in enumerate(rows):
        y = 6 + i * h
        w = max(1.5, span * v / top)
        svg.append('<text x="%d" y="%d" class="lab" text-anchor="end">%s</text>' % (L - 10, y + 15, esc(label)))
        svg.append('<rect x="%d" y="%d" width="%.1f" height="18" rx="3" class="bar%s"/>' % (L, y + 1, w, " last" if i == len(rows) - 1 else ""))
        if tick:
            tx = L + span * tick / top
            svg.append('<line x1="%.1f" x2="%.1f" y1="%d" y2="%d" class="tick"/>' % (tx, tx, y - 2, y + 22))
        svg.append('<text x="%.1f" y="%d" class="val">%s</text>' % (L + w + 8, y + 15, esc(unit_fmt(v))))
    svg.append("</svg>")
    return "".join(svg)


def stacked(rows, keys, unit_fmt):
    top = max(sum(r[1].get(k, 0) for k, _ in keys) for r in rows) * 1.12 or 1
    h = 30
    W, L, R = 640, 150, 86
    span = W - L - R
    svg = ['<svg viewBox="0 0 %d %d" class="chart" role="img">' % (W, h * len(rows) + 8)]
    for i, (label, vals) in enumerate(rows):
        y = 6 + i * h
        x = L
        svg.append('<text x="%d" y="%d" class="lab" text-anchor="end">%s</text>' % (L - 10, y + 15, esc(label)))
        for n, (k, _) in enumerate(keys):
            w = span * vals.get(k, 0) / top
            if w > 0.3:
                svg.append('<rect x="%.1f" y="%d" width="%.1f" height="18" class="seg s%d"><title>%s %s</title></rect>' % (x, y + 1, w, n, esc(k), esc(unit_fmt(vals.get(k, 0)))))
                x += w
        svg.append('<text x="%.1f" y="%d" class="val">%s</text>' % (x + 8, y + 15, esc(unit_fmt(sum(vals.values())))))
    svg.append("</svg>")
    return "".join(svg)


def _pct_change(new, old):
    return (new - old) / old if old else 0.0


def _say(ch, up="higher", down="lower"):
    if abs(ch) < 0.03:
        return "about the same"
    return "%.0f%% %s" % (abs(100 * ch), up if ch > 0 else down)


def conclusion(d):
    """Plain-English reading of the numbers: (topic, sentence) pairs, latest period against the baseline."""
    ps = d["periods"]
    if len(ps) < 2:
        return [("Where you are", "There is only one period so far, so there is nothing to compare yet. Make one change and mark it with /token-lab:experiment start; the next report will show what it did.")]
    a, b = ps[0], ps[-1]
    out = []
    early = b["active"] < 20
    pa, pt, pw = _pct_change(b["per_active"], a["per_active"]), _pct_change(b["per_turn"], a["per_turn"]), _pct_change(b["per_wall"], a["per_wall"])
    s = "For each hour you actually worked, Claude Code cost %s in %s than in %s ($%.2f against $%.2f)." % (_say(pa, "more", "less"), b["key"], a["key"], b["per_active"], a["per_active"])
    if abs(pa) < 0.03:
        s = "For each hour you actually worked, Claude Code cost about the same in %s as in %s ($%.2f against $%.2f)." % (b["key"], a["key"], b["per_active"], a["per_active"])
    if pw > 0.1 and pa < 0.05:
        s += " Spend per clock hour went up %.0f%%, but only because you worked more hours, not because the work got more expensive." % (100 * pw)
    elif pw < -0.1 and pa > -0.05:
        s += " Spend per clock hour fell, but that is because you worked fewer hours, not because anything got cheaper."
    out.append(("Cost", s))
    if a["per_turn"]:
        s = "Each reply from Claude cost %s ($%.3f against $%.3f)." % (_say(pt, "more", "less"), b["per_turn"], a["per_turn"])
        if pt < -0.1 and pa > -0.05:
            s += " Replies got cheaper but you used more of them per hour, so the hourly cost barely moved. That is the expected shape when context is shorter: Claude takes smaller, faster steps."
        out.append(("Per reply", s))
    if a["mean_ctx"]:
        cc = _pct_change(b["mean_ctx"], a["mean_ctx"])
        s = "The conversation Claude re-reads on every turn averaged %s, against %s before (%s)." % (fmt_k(b["mean_ctx"]), fmt_k(a["mean_ctx"]), _say(cc, "longer", "shorter"))
        if a["over500"] > 0.1 and b["over500"] < 0.02:
            s += " Turns over 500k went from %.0f%% to almost none, so long sessions are no longer dragging a huge history along." % (100 * a["over500"])
        elif b["over500"] > 0.2:
            s += " %.0f%% of turns still carry over 500k of context; an earlier auto-compact would cut that." % (100 * b["over500"])
        out.append(("Context", s))
    sa, sb = a["cost_sub"] / max(1e-9, a["active"]), b["cost_sub"] / max(1e-9, b["active"])
    oa = a["sub_tier"]["opus"] / max(1e-9, sum(a["sub_tier"].values()))
    ob = b["sub_tier"]["opus"] / max(1e-9, sum(b["sub_tier"].values()))
    if sa or sb:
        s = "Subagents cost $%.2f per active hour against $%.2f before (%s). Opus took %.0f%% of that spend, against %.0f%%." % (sb, sa, _say(_pct_change(sb, sa), "more", "less"), 100 * ob, 100 * oa)
        build_opus = b["sub_role"].get("build/opus", 0)
        if build_opus > 1:
            s += " Opus is still doing $%.2f per hour of implementation work; moving that to Sonnet is the clearest saving left." % build_opus
        elif ob < oa - 0.05:
            s += " The shift away from Opus is visible."
        out.append(("Subagents", s))
    qa = {q["model"]: q for q in a["quality"]}
    lines = []
    for q in b["quality"]:
        ref = qa.get(q["model"])
        if q["tasks"] < 10:
            lines.append("%s built only %d reviewed tasks, too few to judge." % (q["model"], q["tasks"]))
            continue
        if not ref or ref["tasks"] < 10:
            lines.append("%s: %.0f%% approved on first review, %.2f Important findings per task (no earlier figure to compare)." % (q["model"], 100 * q["approved"], q["important"]))
            continue
        worse = q["important"] > ref["important"] * 1.25 + 0.05 or q["critical"] > ref["critical"] + 0.05
        better = not worse and q["important"] < ref["important"] * 0.8
        verdict_txt = "more problems than before" if worse else ("fewer problems than before" if better else "no sign of more bugs")
        lines.append("%s: %.0f%% approved on first review (was %.0f%%), %.2f Important findings per task (was %.2f): %s." % (q["model"], 100 * q["approved"], 100 * ref["approved"], q["important"], ref["important"], verdict_txt))
    if lines:
        out.append(("Code quality", " ".join(lines)))
    if a["escapes"]["tasks"] and b["escapes"]["tasks"]:
        ea, eb = a["escapes"]["important"], b["escapes"]["important"]
        out.append(("Bugs that slipped through", "The final whole-branch review found %.2f Important problems per task that per-task reviews had missed, against %.2f before. %s" % (eb, ea, "Fewer bugs are reaching the end." if eb < ea * 0.8 else ("More bugs are reaching the end; check whether the cheaper implementers are the cause." if eb > ea * 1.25 + 0.05 else "Roughly the same."))))
    r = d["routing"]["counts"]
    if r:
        blocked = sum(c["n"] for c in r if c["decision"] == "blocked")
        hatch = sum(c["n"] for c in r if c["decision"] == "allowed-with-reason")
        ck = sum(c["n"] for c in r if c["decision"] == "checklist added")
        s = "The router sent %d Opus requests back to Sonnet and allowed %d with a stated reason; %d implementer briefs got the ship checklist." % (blocked, hatch, ck)
        if blocked and hatch > blocked * 0.6:
            s += " The escape hatch is used for most blocks, which suggests it is becoming a bypass; read the reasons."
        out.append(("Guardrails", s))
    if early:
        nxt = "Keep working normally until %s has at least 20 active hours (it has %.0f), then read this again before changing anything else." % (b["key"], b["active"])
    elif ob > 0.5 and b["sub_role"].get("build/opus", 0) > 1:
        nxt = "Turn on implementer routing (or check why it is not catching these dispatches with /token-lab:train)."
    elif b["mean_ctx"] > 400000:
        nxt = "Try /token-lab:experiment start autocompact-50 to shorten the context Claude re-reads each turn."
    else:
        nxt = "The big levers are in place. Next, run an A/B check on one guardrail (for example checklist-off for a week) to confirm it earns its place."
    out.append(("What to do next", nxt))
    if early:
        out.append(("How sure is this", "Not very yet: %s covers %.0f active hours. Early numbers swing with whatever you happened to work on." % (b["key"], b["active"])))
    return out


def verdict(d):
    ps = d["periods"]
    if len(ps) < 2:
        return "Only one period so far. Start an experiment with /token-lab:experiment to get a before and after."
    a, b = ps[0], ps[-1]
    parts = []
    if a["per_active"]:
        ch = (b["per_active"] - a["per_active"]) / a["per_active"]
        parts.append("Cost per active hour is %s%.0f%% in %s against %s ($%.2f vs $%.2f)." % ("+" if ch >= 0 else "−", abs(100 * ch), b["key"], a["key"], b["per_active"], a["per_active"]))
    if a["per_turn"]:
        parts.append("Each turn costs %.0f%% %s." % (abs(100 * (b["per_turn"] - a["per_turn"]) / a["per_turn"]), "less" if b["per_turn"] < a["per_turn"] else "more"))
    if a["mean_ctx"]:
        parts.append("Mean context per turn went from %s to %s." % (fmt_k(a["mean_ctx"]), fmt_k(b["mean_ctx"])))
    if b["active"] < 20:
        parts.append("The latest period has only %.0f active hours, so treat its numbers as early." % b["active"])
    return " ".join(parts)


CSS = """
/* Layout: one reading column; periods run left to right in every table and top to bottom in every chart. */
:root {
  --paper: #f6f7f9; --panel: #ffffff; --ink: #18202b; --muted: #5d6878; --rule: #dde2e9;
  --meter: #2f5d8a; --meter-soft: #c9d8e8; --good: #2f7d4f; --bad: #b2452f; --flat: #6b7380;
  --s0: #2f5d8a; --s1: #4f9a8f; --s2: #c99a3c; --s3: #9aa3b0;
  --display: "IBM Plex Sans Condensed", "Arial Narrow", system-ui, sans-serif;
  --body: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, "SF Mono", Menlo, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --paper: #11161d; --panel: #18202a; --ink: #e6ebf1; --muted: #9aa6b5; --rule: #2a3542;
  --meter: #7fb0e0; --meter-soft: #2c4560; --good: #6cc48f; --bad: #ec8a74; --flat: #9aa3b0;
  --s0: #7fb0e0; --s1: #6fc2b6; --s2: #e0b65e; --s3: #6d7785; color-scheme: dark; } }
:root[data-theme="dark"] {
  --paper: #11161d; --panel: #18202a; --ink: #e6ebf1; --muted: #9aa6b5; --rule: #2a3542;
  --meter: #7fb0e0; --meter-soft: #2c4560; --good: #6cc48f; --bad: #ec8a74; --flat: #9aa3b0;
  --s0: #7fb0e0; --s1: #6fc2b6; --s2: #e0b65e; --s3: #6d7785; color-scheme: dark; }
body { background: var(--paper); color: var(--ink); font: 15px/1.55 var(--body); }
.wrap { max-width: 960px; margin: 0 auto; padding-block: 28px 56px; padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); display: grid; gap: 28px; }
h1, h2 { font-family: var(--display); text-wrap: balance; margin: 0; }
h1 { font-size: 34px; font-weight: 600; letter-spacing: -0.01em; }
h2 { font-size: 21px; font-weight: 600; }
.eyebrow { font: 600 11px/1 var(--mono); letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); }
header { display: grid; gap: 10px; }
.lede { max-width: 68ch; margin: 0; font-size: 16px; }
.meta { color: var(--muted); font-size: 13px; }
.timeline { display: flex; gap: 3px; margin-top: 6px; }
.timeline div { min-width: 0; background: var(--meter-soft); border-radius: 3px; padding: 6px 8px; font: 12px/1.3 var(--mono); overflow: hidden; }
.timeline div b { display: block; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.timeline div span { color: var(--muted); white-space: nowrap; }
.timeline div.cur { background: var(--meter); color: var(--panel); }
.timeline div.cur span { color: var(--panel); opacity: 0.8; }
section { background: var(--panel); border: 1px solid var(--rule); border-radius: 8px; padding: 20px; display: grid; gap: 14px; min-width: 0; }
section > p { margin: 0; color: var(--muted); max-width: 70ch; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }
.tile { border: 1px solid var(--rule); border-radius: 6px; padding: 12px 14px; display: grid; gap: 4px; }
.tile .k { font: 600 11px/1.2 var(--mono); letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }
.tile .v { font: 600 26px/1.1 var(--display); font-variant-numeric: tabular-nums; }
.tile.cur { border-color: var(--meter); }
.chip { display: inline-block; font: 600 12px/1 var(--mono); padding: 3px 6px; border-radius: 10px; margin-left: 6px; vertical-align: middle; }
.chip.good { color: var(--good); background: color-mix(in srgb, var(--good) 14%, transparent); }
.chip.bad { color: var(--bad); background: color-mix(in srgb, var(--bad) 14%, transparent); }
.chip.flat { color: var(--flat); background: color-mix(in srgb, var(--flat) 14%, transparent); }
.scroll { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 14px; }
th, td { padding: 7px 10px; text-align: right; border-bottom: 1px solid var(--rule); white-space: nowrap; font-variant-numeric: tabular-nums; }
th:first-child, td:first-child { text-align: left; }
thead th { font: 600 11px/1.3 var(--mono); letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); }
tr.head td { font-weight: 600; background: color-mix(in srgb, var(--meter) 7%, transparent); }
td.num { font-family: var(--mono); font-size: 13px; }
.meterbar { display: inline-block; width: 70px; height: 7px; background: var(--meter-soft); border-radius: 4px; vertical-align: middle; margin-right: 8px; overflow: hidden; }
.meterbar i { display: block; height: 100%; background: var(--meter); }
.chart { width: 100%; height: auto; display: block; }
.chart .lab { font: 13px var(--body); fill: var(--ink); }
.chart .val { font: 12px var(--mono); fill: var(--muted); }
.chart .axis { font: 11px var(--mono); fill: var(--muted); }
.chart .bar { fill: var(--meter-soft); }
.chart .bar.last { fill: var(--meter); }
.chart .ref { stroke: var(--bad); stroke-dasharray: 4 4; stroke-width: 1.5; }
.chart .tick { stroke: var(--ink); stroke-width: 2; }
.chart .s0 { fill: var(--s0); } .chart .s1 { fill: var(--s1); } .chart .s2 { fill: var(--s2); } .chart .s3 { fill: var(--s3); }
.legend { display: flex; flex-wrap: wrap; gap: 14px; font-size: 13px; color: var(--muted); }
.legend i { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 6px; vertical-align: -1px; }
.two { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; }
.two > div { min-width: 0; display: grid; gap: 10px; align-content: start; }
h3 { margin: 0; font: 600 15px/1.3 var(--body); }
.reasons { margin: 0; padding: 0; list-style: none; display: grid; gap: 8px; font-size: 13px; }
.reasons li { border-left: 3px solid var(--meter-soft); padding-left: 10px; }
.reasons b { font-weight: 600; }
.conclusion { border-color: var(--meter); }
.conclusion dl { margin: 0; display: grid; gap: 12px; }
.conclusion dl > div { display: grid; grid-template-columns: 150px 1fr; gap: 16px; padding-top: 12px; border-top: 1px solid var(--rule); }
.conclusion dl > div:first-child { border-top: 0; padding-top: 0; }
.conclusion dt { font: 600 12px/1.6 var(--mono); letter-spacing: 0.06em; text-transform: uppercase; color: var(--meter); }
.conclusion dd { margin: 0; max-width: 70ch; font-size: 15.5px; }
@media (max-width: 520px) { .conclusion dl > div { grid-template-columns: 1fr; gap: 4px; } }
footer { color: var(--muted); font-size: 13px; display: grid; gap: 6px; max-width: 75ch; }
footer p { margin: 0; }
@media (max-width: 520px) { h1 { font-size: 27px; } .timeline { flex-wrap: wrap; } .timeline div { flex: 1 1 45% !important; } }
"""


def render(d):
    ps = d["periods"]
    base = ps[0]
    cur = ps[-1]
    o = []
    o.append('<title>Token Lab Report</title>\n<meta name="claude:viewport-fit-sides" content="cover">')
    o.append('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>')
    o.append('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans+Condensed:wght@600&family=IBM+Plex+Sans:wght@400;600&display=swap">')
    o.append("<style>%s</style>" % CSS)
    o.append('<div class="wrap">')
    total_h = sum(max(p["hours"], 1) for p in ps)
    tl = "".join('<div class="%s" style="flex:%.3f 1 0" title="%s"><b>%s</b><span>%s → %s</span></div>' % ("cur" if p is cur else "", max(p["hours"], 1) / total_h * 10 + 1, esc(p["label"]), esc(p["key"]), esc(p["start"]), esc(p["end"])) for p in ps)
    o.append('<header><div class="eyebrow">token-lab · generated %s</div><h1>Token Lab Report</h1><p class="lede">%s</p><div class="timeline">%s</div><div class="meta">Each period runs from one experiment to the next. Costs are list-price estimates from your transcripts. They are for comparing periods, not an invoice.</div></header>' % (esc(d["generated"]), esc(verdict(d)), tl))

    tiles = []
    for p in ps:
        chip = "" if p is base else delta_chip(p["per_active"], base["per_active"])
        tiles.append('<div class="tile%s"><span class="k">%s</span><span class="v">$%.2f%s</span><span class="meta">per active hour · %.0f active h</span></div>' % (" cur" if p is cur else "", esc(p["key"]), p["per_active"], chip, p["active"]))
    concl = d.get("conclusion_override") or conclusion(d)
    o.append('<section class="conclusion"><div class="eyebrow">In conclusion</div><h2>What the numbers mean</h2><dl>%s</dl></section>' % "".join("<div><dt>%s</dt><dd>%s</dd></div>" % (esc(t), esc(x)) for t, x in concl))
    o.append('<section><div class="eyebrow">Headline</div><h2>Cost per active hour</h2><p>An active hour is a 5-minute slot with at least one turn, counted once across parallel sessions. It stays comparable when one week is busier than another.</p><div class="tiles">%s</div></section>' % "".join(tiles))

    def row(label, fn, fmt, better=None, head=False):
        cells = []
        for p in ps:
            v = fn(p)
            chip = delta_chip(v, fn(base), better) if better is not None and p is not base else ""
            cells.append('<td class="num">%s%s</td>' % (fmt % v if isinstance(v, (int, float)) else esc(v), chip))
        return '<tr%s><td>%s</td>%s</tr>' % (' class="head"' if head else "", esc(label), "".join(cells))
    thead = "<thead><tr><th>Metric</th>%s</tr></thead>" % "".join("<th>%s</th>" % esc(p["key"]) for p in ps)
    rows = [
        row("$ per active hour", lambda p: p["per_active"], "$%.2f", True, True),
        row("$ per main turn", lambda p: p["per_turn"], "$%.3f", True),
        row("$ per wall-clock hour", lambda p: p["per_wall"], "$%.2f", True),
        row("Total $", lambda p: p["cost"], "$%.0f"),
        row("  main sessions", lambda p: p["cost_main"], "$%.0f"),
        row("  subagents", lambda p: p["cost_sub"], "$%.0f"),
        row("Active hours", lambda p: p["active"], "%.1f"),
        row("Wall-clock hours", lambda p: p["hours"], "%.0f"),
        row("Turns", lambda p: p["turns"], "%d"),
        row("Sessions", lambda p: p["sessions"], "%d"),
    ]
    if d["git"]:
        rows += [row("Commits", lambda p: p["commits"], "%d"), row("$ per commit", lambda p: p["cost"] / max(1, p["commits"]), "$%.2f", True), row("$ per 1k lines changed", lambda p: 1000 * p["cost"] / max(1, p["lines"]), "$%.2f", True)]
    o.append('<section><div class="eyebrow">Normalised cost</div><h2>Every way of counting it</h2><p>Chips compare each period with %s. Green means cheaper. $ per commit and per line depend on the kind of work, so read them as context, not as the score.</p><div class="scroll"><table>%s<tbody>%s</tbody></table></div></section>' % (esc(base["key"]), thead, "".join(rows)))

    ctx_rows = [(p["key"], p["mean_ctx"], p["p90_ctx"]) for p in ps]
    comp = "".join("<tr><td>%s</td><td class='num'>%.0f%%</td><td class='num'>%d / %d</td></tr>" % (esc(p["key"]), 100 * p["over500"], p["auto"], p["manual"]) for p in ps)
    o.append('<section><div class="eyebrow">Main sessions</div><h2>Context re-sent on every turn</h2><p>Every turn re-sends the whole conversation, so context per turn drives most of the bill. Bars show the mean, the dark tick the 90th percentile, and the dashed line 500k.</p>%s<div class="scroll"><table><thead><tr><th>Period</th><th>Turns over 500k</th><th>Compactions auto / manual</th></tr></thead><tbody>%s</tbody></table></div></section>' % (hbars(ctx_rows, fmt_k, 500000, "500k"), comp))

    keys = [(t, n) for t, n in TIERS]
    st = stacked([(p["key"], {t: p["sub_tier"][t] for t, _ in TIERS}) for p in ps], keys, lambda v: "$%.2f" % v)
    legend = "".join('<span><i style="background:var(--s%d)"></i>%s</span>' % (i, n) for i, (_, n) in enumerate(TIERS))
    groups = [("build", "Implement and fix"), ("review", "Reviews"), ("other", "Planning and other")]
    srows = []
    for g, gname in groups:
        for t, tname in TIERS[:3]:
            vals = [p["sub_role"].get("%s/%s" % (g, t), 0) for p in ps]
            if any(v >= 0.01 for v in vals):
                srows.append("<tr><td>%s · %s</td>%s</tr>" % (esc(gname), esc(tname), "".join("<td class='num'>$%.2f</td>" % v for v in vals)))
    o.append('<section><div class="eyebrow">Subagents</div><h2>Subagent spend per active hour</h2><div class="legend">%s</div>%s<div class="scroll"><table>%s<tbody>%s</tbody></table></div></section>' % (legend, st, thead.replace("Metric", "Role · model"), "".join(srows)))

    qrows = []
    for p in ps:
        for q in p["quality"]:
            qrows.append("<tr><td>%s</td><td>%s</td><td class='num'>%d</td><td class='num'><span class='meterbar'><i style='width:%.0f%%'></i></span>%.0f%%</td><td class='num'>%.2f</td><td class='num'>%.2f</td><td class='num'>%.2f</td><td class='num'>%.2f</td><td class='num'>$%.2f</td></tr>" % (esc(p["key"]), esc(q["model"]), q["tasks"], 100 * q["approved"], 100 * q["approved"], q["critical"], q["important"], q["minor"], q["rounds"], q["cost"]))
    erows = "".join("<tr><td>%s</td><td class='num'>%d</td><td class='num'>%.3f</td><td class='num'>%.2f</td></tr>" % (esc(p["key"]), p["escapes"]["tasks"], p["escapes"]["critical"], p["escapes"]["important"]) for p in ps if p["escapes"]["tasks"])
    if qrows:
        o.append('<section><div class="eyebrow">Implementer quality</div><h2>Did cheaper implementers ship more bugs?</h2><p>Each task is scored by its first review. The stronger model usually gets the harder tasks, so compare a model with itself across periods rather than models with each other.</p><div class="scroll"><table><thead><tr><th>Period</th><th>Implementer</th><th>Tasks</th><th>Approved first time</th><th>Critical</th><th>Important</th><th>Minor</th><th>Fix rounds</th><th>$ per task</th></tr></thead><tbody>%s</tbody></table></div>%s</section>' % (
            "".join(qrows),
            ('<h3>Missed by per-task reviews, caught by the final review</h3><div class="scroll"><table><thead><tr><th>Period</th><th>Tasks</th><th>Critical per task</th><th>Important per task</th></tr></thead><tbody>%s</tbody></table></div>' % erows) if erows else ""))
    else:
        o.append('<section><div class="eyebrow">Implementer quality</div><h2>Implementer quality</h2><p>No reviewed subagent-driven-development tasks in these periods yet. This section fills in once you run plans with superpowers subagent-driven development.</p></section>')

    r = d["routing"]
    if r["counts"]:
        rc = "".join("<tr><td>%s</td><td>%s</td><td class='num'>%d</td></tr>" % (esc(c["decision"]), esc(c["kind"]), c["n"]) for c in r["counts"])
        rs = "".join("<li><b>%s</b> · %s<br>%s</li>" % (esc(x["desc"]), esc(x["at"]), esc(x["reason"] or "no reason logged")) for x in reversed(r["reasons"]))
        routing_html = '<div><h3>Model router</h3><div class="scroll"><table><thead><tr><th>Decision</th><th>Kind</th><th>Count</th></tr></thead><tbody>%s</tbody></table></div>%s</div>' % (rc, ('<h3>Recent Opus escape-hatch reasons</h3><ul class="reasons">%s</ul>' % rs) if rs else "")
    else:
        routing_html = '<div><h3>Model router</h3><p class="meta">No routing decisions logged yet.</p></div>'
    brows = "".join("<tr><td>%s</td><td class='num'>%d</td><td class='num'>%d/%d</td><td class='num'>%s</td><td class='num'>%ss</td></tr>" % (esc(p["key"]), p["bulk"]["calls"], p["bulk"]["bullets"], p["bulk"]["calls"], fmt_k(p["bulk"]["reply"]) if p["bulk"]["calls"] else "–", "%.0f" % p["bulk"]["latency"] if p["bulk"]["calls"] else "–") for p in ps)
    grows = "".join("<tr><td>%s</td><td class='num'>%d</td><td class='num'>%.2f</td></tr>" % (esc(p["key"]), p["gate"]["blocks"], 1000 * p["gate"]["big_reads"] / max(1, p["gate"]["tools"])) for p in ps)
    fol = Counter()
    for p in ps:
        fol.update(p["gate"]["followups"])
    fol_txt = ", ".join("%s %d" % kv for kv in fol.most_common()) or "no blocks yet"
    o.append('<section><div class="eyebrow">Guardrails</div><h2>Router, bulk-reader and file-size gate</h2><div class="two">%s<div><h3>bulk-reader</h3><div class="scroll"><table><thead><tr><th>Period</th><th>Calls</th><th>Bullets only</th><th>Median reply</th><th>Median time</th></tr></thead><tbody>%s</tbody></table></div><h3>File-size gate</h3><div class="scroll"><table><thead><tr><th>Period</th><th>Blocks</th><th>Big full reads per 1k tools</th></tr></thead><tbody>%s</tbody></table></div><p class="meta">After a block the model: %s.</p></div></div></section>' % (routing_html, brows, grows, esc(fol_txt)))

    o.append('<footer><p>Turns are counted once per assistant message. Transcripts write one record per content block, and advisor calls report context twice; both are corrected here.</p><p>Prices: cache reads 0.1×, cache writes 1.25× (5 min) or 2× (1 h), output 5×, relative to each model\'s input list price. Change them with lab.py config.</p></footer>')
    o.append("</div>")
    return "\n".join(o)


def read_conclusion(fp):
    """Lines of `Topic: sentence`, one per line; blank lines and '#' comments ignored."""
    out = []
    with open(fp) as fh:
        for ln in fh:
            ln = ln.strip().lstrip("-* ").strip()
            if not ln or ln.startswith("#"):
                continue
            topic, _, text = ln.partition(":")
            out.append((topic.strip().strip("*"), text.strip()) if text else ("", topic.strip()))
    return out


def write(ps, cwds, out_path, with_git=True, conclusion_file=None):
    d = collect(ps, cwds, with_git)
    if conclusion_file:
        d["conclusion_override"] = read_conclusion(os.path.expanduser(conclusion_file))
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as fh:
        fh.write(render(d))
    return out_path
