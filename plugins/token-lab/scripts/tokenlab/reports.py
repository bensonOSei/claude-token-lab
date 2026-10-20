import os
import re
import statistics
import subprocess
from collections import Counter, defaultdict

from .core import STATE, k, pct, short_model, tier

HEAD_RE = re.compile(r"^#+\s*(Critical|Important|Minor)\b", re.I)
NOISE = re.compile(r"(^|/)(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|poetry\.lock|uv\.lock|go\.sum|Cargo\.lock)$|\.snap$|(^|/)(dist|build|coverage|node_modules|\.superpowers)/|\.min\.(js|css)$|\.(png|jpe?g|gif|svg|glb|gltf|bin|ico|woff2?)$")


def table(ps, rows, width=13):
    out = ["  %-34s" % "" + "".join(("%" + str(width) + "s") % p.key[:width - 1] for p in ps)]
    for label, fn, fmt in rows:
        out.append("  %-34s" % label + "".join(fmt % fn(p) for p in ps))
    return out


def period_header(ps):
    out = ["PERIODS (local time)"]
    for p in ps:
        out.append("  %-14s %s -> %s  (%.0fh)  %s" % (p.key[:14], p.a.astimezone().strftime("%m-%d %H:%M"), p.b.astimezone().strftime("%m-%d %H:%M"), p.hours, p.label))
    return out


def sessions(ps):
    rows = [
        ("sessions active", lambda p: len(p.peaks), "%13d"),
        ("assistant turns (unique)", lambda p: p.turns, "%13d"),
        ("turns per active hour", lambda p: p.turns / max(1e-9, p.active_hours), "%13.0f"),
        ("mean context per turn", lambda p: k(statistics.mean(p.ctx)) if p.ctx else "-", "%13s"),
        ("median context per turn", lambda p: k(pct(p.ctx, 0.5)), "%13s"),
        ("p90 context per turn", lambda p: k(pct(p.ctx, 0.9)), "%13s"),
        ("turns above 500k", lambda p: "%.0f%%" % (100 * sum(c > 500000 for c in p.ctx) / max(1, p.turns)), "%13s"),
        ("sessions that passed 500k", lambda p: "%d/%d" % (sum(v > 500000 for v in p.peaks.values()), len(p.peaks)), "%13s"),
        ("auto / manual compactions", lambda p: "%d/%d" % (sum(t == "auto" for t, _ in p.compactions), sum(t == "manual" for t, _ in p.compactions)), "%13s"),
        ("median size when compacted", lambda p: k(pct([n for _, n in p.compactions], 0.5)), "%13s"),
    ]
    return ["MAIN SESSIONS"] + table(ps, rows)


def _git_output(cwds, ps):
    roots = set(cwds)
    base = os.path.expanduser(os.environ.get("TOKEN_LAB_REPOS", "~"))
    for dirpath, dirnames, _ in os.walk(base):
        depth = dirpath[len(base):].count(os.sep)
        if ".git" in dirnames:
            roots.add(dirpath)
        dirnames[:] = [d for d in dirnames if depth < 3 and not d.startswith(".") and d not in ("node_modules", "vendor", "dist", "build", "Library", "Applications")]
    repos = {}
    for c in roots:
        if not os.path.isdir(c):
            continue
        try:
            common = subprocess.run(["git", "-C", c, "rev-parse", "--path-format=absolute", "--git-common-dir"], capture_output=True, text=True, timeout=10).stdout.strip()
            email = subprocess.run(["git", "-C", c, "config", "user.email"], capture_output=True, text=True, timeout=10).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            continue
        if common and email:
            repos[common] = (c, email)
    commits = defaultdict(set)
    lines = Counter()
    since = min(p.a for p in ps)
    for c, email in repos.values():
        try:
            out = subprocess.run(["git", "-C", c, "log", "--all", "--no-merges", "--author=" + email, "--since=" + since.isoformat(), "--format=@%H %ct", "--numstat"], capture_output=True, text=True, timeout=120).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        cur = None
        for ln in out.splitlines():
            if ln.startswith("@"):
                h, ct = ln[1:].split()
                cur = None
                for p in ps:
                    if p.a.timestamp() <= int(ct) < p.b.timestamp() and h not in commits[p.key]:
                        commits[p.key].add(h)
                        cur = p.key
                continue
            parts = ln.split("\t")
            if cur and len(parts) == 3 and parts[0].isdigit() and not NOISE.search(parts[2]):
                lines[cur] += int(parts[0]) + int(parts[1])
    return len(repos), commits, lines


def normalised(ps, cwds, with_git=True):
    nrepos, commits, lines = _git_output(cwds, ps) if with_git else (0, defaultdict(set), Counter())
    rows = [
        ("wall-clock hours", lambda p: p.hours, "%13.0f"),
        ("active hours (you working)", lambda p: p.active_hours, "%13.1f"),
        ("session-hours (parallel sum)", lambda p: p.session_hours, "%13.1f"),
        ("total $", lambda p: p.cost, "%13.0f"),
        ("  main sessions $", lambda p: p.cost_main, "%13.0f"),
        ("  subagents $", lambda p: p.cost_sub, "%13.0f"),
        ("$ per wall-clock hour", lambda p: p.cost / p.hours, "%13.2f"),
        ("$ per active hour  <- headline", lambda p: p.cost / max(1e-9, p.active_hours), "%13.2f"),
        ("$ per session-hour", lambda p: p.cost / max(1e-9, p.session_hours), "%13.2f"),
        ("$ per main turn", lambda p: p.cost / max(1, p.turns), "%13.3f"),
    ]
    if with_git:
        rows += [
            ("commits (yours)", lambda p: len(commits[p.key]), "%13d"),
            ("$ per commit", lambda p: p.cost / max(1, len(commits[p.key])), "%13.2f"),
            ("lines changed (excl. noise)", lambda p: lines[p.key], "%13d"),
            ("$ per 1k lines changed", lambda p: 1000 * p.cost / max(1, lines[p.key]), "%13.2f"),
        ]
    out = ["NORMALISED COST (list-price estimate; %s)" % ("%d git repos scanned" % nrepos if with_git else "git skipped")]
    out += table(ps, rows)
    out.append("  Active hour = a 5-minute slot with at least one main-session turn, counted once across parallel sessions.")
    out.append("  Compare periods on $ per active hour; $ per commit and per line depend on the kind of work.")
    return out


def subagents(ps):
    out = ["SUBAGENTS: $ per active hour by role and model"]
    for p in ps:
        c = Counter()
        for s in p.subs:
            c[(s["role"], short_model(s["model"]))] += s["cost"]
        rows = ", ".join("%s %s %.2f" % (r, m, v / max(1e-9, p.active_hours)) for (r, m), v in c.most_common(6))
        out.append("  %-14s %s" % (p.key[:14], rows or "-"))
    out.append("  Opus share of subagent $: " + "  ".join("%s %.0f%%" % (p.key[:14], 100 * sum(s["cost"] for s in p.subs if tier(s["model"]) == "opus") / max(1e-9, p.cost_sub)) for p in ps))
    return out


def bulk_reader(ps):
    rows = []
    def br(p):
        return [s for s in p.subs if s["agent"].endswith("bulk-reader")]
    def bullets(s):
        lines = [ln for ln in s["reply"].strip().splitlines() if ln.strip()]
        return bool(lines) and all(ln.lstrip().startswith("- ") for ln in lines)
    rows = [
        ("calls", lambda p: len(br(p)), "%13d"),
        ("bullets-only replies", lambda p: "%d/%d" % (sum(bullets(s) for s in br(p)), len(br(p))), "%13s"),
        ("median reply tokens", lambda p: pct([len(s["reply"]) / 4 for s in br(p)], 0.5), "%13.0f"),
        ("median latency (s)", lambda p: pct([s["seconds"] for s in br(p)], 0.5), "%13.0f"),
        ("median tool calls", lambda p: pct([s["tools"] for s in br(p)], 0.5), "%13d"),
    ]
    return ["BULK-READER"] + table(ps, rows)


def gate(ps):
    rows = [
        ("gate blocks", lambda p: p.gate_blocks, "%13d"),
        ("full reads of big files /1k tools", lambda p: 1000 * p.full_big_reads / max(1, p.tool_calls), "%13.2f"),
    ]
    out = ["FILE-SIZE GATE"] + table(ps, rows)
    total = Counter()
    for p in ps:
        total.update(p.followups)
    n = sum(total.values())
    if n:
        out.append("  after a block the model:")
        for kind, c in total.most_common():
            out.append("    %4d  %3.0f%%  %s" % (c, 100 * c / n, kind))
    return out


def findings(reply):
    counts = Counter()
    sect = None
    for ln in reply.splitlines():
        h = HEAD_RE.match(ln.strip())
        if h:
            sect = h.group(1).capitalize()
            continue
        if ln.startswith("#"):
            sect = None
            continue
        s = ln.strip()
        if sect and not ln.startswith(("  ", "\t")) and re.match(r"^([-*]|\d+[.)])\s+\S", s) and not re.match(r"^([-*]|\d+[.)])\s+\**(none|n/a)\b", s, re.I):
            counts[sect] += 1
    approved = bool(re.search(r"\*\*Task quality:\*\*\s*Approved", reply))
    parts = reply.split("###")
    spec_ok = "❌" not in parts[1] if len(parts) > 2 else True
    return counts, approved and spec_ok


def task_table(ps):
    tasks = defaultdict(lambda: {"impl": None, "period": None, "reviews": [], "rounds": 0, "cost": 0.0})
    final = defaultdict(Counter)
    subs = sorted((s for p in ps for s in p.subs if s["run"]), key=lambda s: s["at"])
    for s in subs:
        if s["role"] == "final-review":
            final[s["run"]].update(findings(s["reply"])[0])
            continue
        if s["task"] is None:
            continue
        t = tasks[(s["run"], s["task"])]
        t["cost"] += s["cost"]
        if s["role"] == "implement" and t["impl"] is None:
            t["impl"] = short_model(s["model"])
            t["period"] = next((p.key for p in ps if p.a <= s["at"] < p.b), None)
        elif s["role"] == "re-review":
            t["rounds"] += 1
        elif s["role"] == "review":
            t["reviews"].append(findings(s["reply"]))
    return tasks, final


def quality(ps):
    tasks, final = task_table(ps)
    groups = defaultdict(list)
    for t in tasks.values():
        if t["impl"] and t["reviews"] and t["period"]:
            groups[(t["period"], t["impl"])].append(t)
    out = ["IMPLEMENTER QUALITY (superpowers subagent-driven-development runs; scored by the first per-task review)"]
    if not groups:
        out.append("  no SDD tasks with a review found in these periods")
        return out
    out.append("  %-14s %-14s %5s %9s %9s %10s %8s %7s %8s" % ("period", "implementer", "tasks", "approved", "critical", "important", "minor", "fix", "$/task"))
    order = [p.key for p in ps]
    for (pk, model), xs in sorted(groups.items(), key=lambda kv: (order.index(kv[0][0]), kv[0][1])):
        n = len(xs)
        first = [t["reviews"][0] for t in xs]
        out.append("  %-14s %-14s %5d %8.0f%% %9.2f %10.2f %8.2f %7.2f %8.2f" % (
            pk[:14], model[:14], n,
            100 * sum(ok for _, ok in first) / n,
            sum(c["Critical"] for c, _ in first) / n,
            sum(c["Important"] for c, _ in first) / n,
            sum(c["Minor"] for c, _ in first) / n,
            sum(t["rounds"] for t in xs) / n,
            pct([t["cost"] for t in xs], 0.5),
        ))
    out.append("  Columns are per task. fix = re-review rounds. $/task is the median over implement, review, fix and re-review runs.")
    out.append("  Models are not randomly assigned: a stronger model usually gets the harder tasks. Compare a model with itself across periods.")
    era = defaultdict(lambda: [0, 0, 0])
    for run, c in final.items():
        pks = {t["period"] for (r, _), t in tasks.items() if r == run and t["impl"]}
        if len(pks) != 1 or None in pks:
            continue
        e = era[pks.pop()]
        e[0] += sum(1 for (r, _), t in tasks.items() if r == run and t["impl"])
        e[1] += c["Critical"]
        e[2] += c["Important"]
    if era:
        out.append("  ESCAPES (final whole-branch review findings per task, runs built inside one period):")
        for pk in order:
            if pk in era:
                n, cr, im = era[pk]
                out.append("    %-14s tasks %4d  critical/task %.3f  important/task %.2f" % (pk[:14], n, cr / max(1, n), im / max(1, n)))
    return out


def routing():
    fp = os.path.join(STATE, "routing.log")
    c = Counter()
    reasons = []
    try:
        with open(fp) as fh:
            for ln in fh:
                parts = ln.rstrip("\n").split("\t")
                if len(parts) >= 5:
                    c[(parts[1], parts[2], parts[3])] += 1
                    if parts[1].startswith("allowed-with-reason"):
                        reasons.append("%s | %s" % (parts[4], parts[5] if len(parts) > 5 else ""))
    except OSError:
        pass
    out = ["MODEL ROUTING HOOK (decision / kind / requested model)"]
    if not c:
        return out + ["  no decisions logged yet"]
    for key, n in sorted(c.items()):
        out.append("  %5d  %-30s %-12s %s" % ((n,) + key))
    blocked = sum(n for key, n in c.items() if key[0] == "blocked")
    out.append("  escape hatch used %d times, blocks %d. If the hatch is used for most blocks, it has become a bypass." % (len(reasons), blocked))
    for r in reasons[-10:]:
        out.append("    reason: %s" % r)
    return out


def full(ps, cwds, with_git=True):
    parts = [period_header(ps), normalised(ps, cwds, with_git), sessions(ps), subagents(ps), quality(ps), routing(), bulk_reader(ps), gate(ps)]
    return "\n\n".join("\n".join(x) for x in parts)
