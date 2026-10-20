import json
import statistics
from collections import Counter, defaultdict

from .core import NOW, config, pct, tier
from .reports import task_table

SCHEMA = 1


def _round(x, n=3):
    return round(x, n) if isinstance(x, float) else x


def aggregate(ps, label):
    """Numbers only. No project names, run names, paths, prompts or descriptions leave the machine."""
    tasks, final = task_table(ps)
    out = {"schema": SCHEMA, "label": label, "generated": NOW.date().isoformat(), "prices": config()["prices"], "periods": []}
    for p in ps:
        act = max(1e-9, p.active_hours)
        role_tier = Counter()
        for s in p.subs:
            role_tier["%s/%s" % (s["role"], tier(s["model"]) or "other")] += s["cost"]
        br = [s for s in p.subs if s["agent"].endswith("bulk-reader")]
        q = defaultdict(list)
        for t in tasks.values():
            if t["impl"] and t["reviews"] and t["period"] == p.key:
                q[t["impl"]].append(t)
        quality = {}
        for model, xs in q.items():
            first = [t["reviews"][0] for t in xs]
            n = len(xs)
            quality[model] = {
                "tasks": n,
                "approved_first_pass": _round(sum(ok for _, ok in first) / n),
                "critical_per_task": _round(sum(c["Critical"] for c, _ in first) / n),
                "important_per_task": _round(sum(c["Important"] for c, _ in first) / n),
                "minor_per_task": _round(sum(c["Minor"] for c, _ in first) / n),
                "fix_rounds_per_task": _round(sum(t["rounds"] for t in xs) / n),
                "median_cost_per_task": _round(pct([t["cost"] for t in xs], 0.5), 2),
            }
        esc_tasks = esc_c = esc_i = 0
        for run, c in final.items():
            pks = {t["period"] for (r, _), t in tasks.items() if r == run and t["impl"]}
            if pks == {p.key}:
                esc_tasks += sum(1 for (r, _), t in tasks.items() if r == run and t["impl"])
                esc_c += c["Critical"]
                esc_i += c["Important"]
        out["periods"].append({
            "key": p.key,
            "label": p.label,
            "days": _round(p.hours / 24, 1),
            "sessions": len(p.peaks),
            "turns": p.turns,
            "active_hours": _round(p.active_hours, 1),
            "cost_per_active_hour": _round(p.cost / act, 2),
            "cost_per_wall_hour": _round(p.cost / p.hours, 2),
            "cost_per_turn": _round(p.cost / max(1, p.turns), 3),
            "turns_per_active_hour": _round(p.turns / act, 1),
            "subagent_cost_share": _round(p.cost_sub / max(1e-9, p.cost)),
            "opus_share_of_subagent_cost": _round(sum(s["cost"] for s in p.subs if tier(s["model"]) == "opus") / max(1e-9, p.cost_sub)),
            "subagent_cost_per_active_hour": {key: _round(v / act, 2) for key, v in role_tier.most_common()},
            "mean_context": round(statistics.mean(p.ctx)) if p.ctx else 0,
            "p90_context": pct(p.ctx, 0.9),
            "share_turns_over_500k": _round(sum(c > 500000 for c in p.ctx) / max(1, p.turns)),
            "compactions_per_active_hour": _round(len(p.compactions) / act),
            "advisor_cost_per_active_hour": _round(p.advisor_cost / act, 2),
            "gate_blocks_per_1k_tool_calls": _round(1000 * p.gate_blocks / max(1, p.tool_calls), 2),
            "bulk_reader": {
                "calls": len(br),
                "median_reply_tokens": round(pct([len(s["reply"]) / 4 for s in br], 0.5)),
                "median_latency_s": round(pct([s["seconds"] for s in br], 0.5)),
            },
            "quality": quality,
            "escapes": {"tasks": esc_tasks, "critical_per_task": _round(esc_c / max(1, esc_tasks)), "important_per_task": _round(esc_i / max(1, esc_tasks))},
        })
    return out


METRICS = [
    ("$ per active hour", "cost_per_active_hour", "%.2f"),
    ("$ per turn", "cost_per_turn", "%.3f"),
    ("turns per active hour", "turns_per_active_hour", "%.0f"),
    ("mean context", "mean_context", "%d"),
    ("p90 context", "p90_context", "%d"),
    ("turns over 500k", "share_turns_over_500k", "%.2f"),
    ("subagent share of $", "subagent_cost_share", "%.2f"),
    ("Opus share of subagent $", "opus_share_of_subagent_cost", "%.2f"),
    ("compactions / active hour", "compactions_per_active_hour", "%.2f"),
]


def compare(mine, theirs):
    cols = [("you:" + p["key"], p) for p in mine["periods"]] + [("ref:" + p["key"], p) for p in theirs["periods"]]
    out = ["COMPARISON with %s (%s)" % (theirs.get("label", "reference"), theirs.get("generated", "?"))]
    out.append("  %-28s" % "" + "".join("%15s" % c[:14] for c, _ in cols))
    for label, key, fmt in METRICS:
        out.append("  %-28s" % label + "".join("%15s" % (fmt % p.get(key, 0)) for _, p in cols))
    out.append("")
    out.append("  Implementer quality (first per-task review):")
    for c, p in cols:
        for model, q in sorted(p.get("quality", {}).items()):
            out.append("    %-16s %-14s tasks %4d  approved %3.0f%%  critical %.2f  important %.2f  $/task %.2f" % (c[:16], model[:14], q["tasks"], 100 * q["approved_first_pass"], q["critical_per_task"], q["important_per_task"], q["median_cost_per_task"]))
    out.append("  Prices are list-price estimates from each side's config; compare shapes and ratios, not cents.")
    return out


def load(fp):
    with open(fp) as fh:
        data = json.load(fh)
    if data.get("schema") != SCHEMA:
        raise SystemExit("unsupported baseline schema in %s" % fp)
    return data
