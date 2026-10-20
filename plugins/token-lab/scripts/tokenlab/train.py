import json
import os
import re
import subprocess
from collections import Counter
from datetime import timedelta

from .core import NOW, STATE, config, period_of, records, text_of, transcripts, ts, short_model, tier
from .reports import HEAD_RE, findings
from .scan import scan

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "hooks", "route-subagent-models.sh")


def classify(desc, model):
    payload = json.dumps({"tool_name": "Agent", "tool_input": {"subagent_type": "general-purpose", "model": model, "description": desc, "prompt": "x"}})
    env = dict(os.environ, TOKEN_LAB_DRY_RUN="1", TOKEN_LAB_CLASSIFY_ONLY="1")
    r = subprocess.run([HOOK], input=payload, capture_output=True, text=True, env=env, timeout=10)
    return r.stdout.strip() or "untouched"


def replay(days):
    since = NOW - timedelta(days=days)
    descs = Counter()
    for fp, is_sub in transcripts(since):
        if is_sub:
            continue
        for r in records(fp):
            t = ts(r)
            if t is None or t < since:
                continue
            for b in (r.get("message") or {}).get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Agent":
                    i = b.get("input") or {}
                    if (i.get("subagent_type") or "general-purpose") in ("general-purpose", "claude"):
                        descs[(i.get("description") or "", tier(i.get("model")) or "default")] += 1
    kinds = Counter()
    by_kind = {}
    for (d, m), n in descs.items():
        kd = classify(d, m)
        kinds[(kd, m)] += n
        by_kind.setdefault(kd, Counter())[re.sub(r"\d+", "N", d)] += n
    return kinds, by_kind


def mine_findings(ps, tiers):
    lines = []
    tasks = {}
    subs = sorted((s for p in ps for s in p.subs if s["run"] and s["task"] is not None), key=lambda s: s["at"])
    for s in subs:
        key = (s["run"], s["task"])
        if s["role"] == "implement" and key not in tasks:
            tasks[key] = tier(s["model"])
        elif s["role"] == "review" and tasks.get(key) in tiers:
            sect = None
            for ln in s["reply"].splitlines():
                h = HEAD_RE.match(ln.strip())
                if h:
                    sect = h.group(1).capitalize()
                    continue
                if ln.startswith("#"):
                    sect = None
                    continue
                st = ln.strip()
                if sect in ("Critical", "Important") and not ln.startswith(("  ", "\t")) and re.match(r"^([-*]|\d+[.)])\s+\S", st) and not re.search(r"(?i)^([-*]|\d+[.)])\s+\**(none|n/a)\b", st):
                    lines.append("%s [%s] %s" % (sect.upper(), tasks[key], st[:400]))
            tasks[key] = None
    return lines


def gate_calibration(ps):
    sizes = []
    for p in ps:
        sizes.append((p.key, p.full_big_reads, p.gate_blocks, p.tool_calls))
    return sizes


def run(days=28, tiers=("sonnet", "haiku")):
    os.makedirs(os.path.join(STATE, "train"), exist_ok=True)
    out = []
    kinds, by_kind = replay(days)
    out.append("1. ROUTING CLASSIFIER REPLAY (last %d days of general-purpose dispatches)" % days)
    for (kd, m), n in sorted(kinds.items()):
        out.append("   %5d  %-12s requested %s" % (n, kd, m))
    blocked = sum(n for (kd, m), n in kinds.items() if kd in ("implementer", "re-review") and m in ("opus", "fable"))
    out.append("   With routing on, %d of these Opus dispatches would have been sent back to Sonnet." % blocked)
    with open(os.path.join(STATE, "train", "classifier.txt"), "w") as fh:
        for kd, c in sorted(by_kind.items()):
            fh.write("## %s\n" % kd)
            for d, n in c.most_common(60):
                fh.write("%5d  %s\n" % (n, d))
    out.append("   Descriptions by class: %s" % os.path.join(STATE, "train", "classifier.txt"))
    out.append("   Check the 'untouched' list for implementer work the patterns miss, and the 'implementer' list for judgment work wrongly caught.")

    ps = [("train", "training window", NOW - timedelta(days=days), NOW)]
    periods, _ = scan(ps)
    found = mine_findings(periods, set(tiers))
    fp = os.path.join(STATE, "train", "findings.md")
    with open(fp, "w") as fh:
        fh.write("# Critical and Important findings on %s-built tasks, last %d days\n\n" % ("/".join(tiers), days))
        fh.write("\n".join(found) + "\n")
    out.append("")
    out.append("2. REVIEW FINDINGS MINED: %d Critical/Important findings on %s-built tasks -> %s" % (len(found), "/".join(tiers), fp))
    out.append("   Cluster these and fold the recurring classes into %s (the hook uses it instead of the shipped checklist)." % os.path.join(STATE, "checklist.md"))

    p = periods[0]
    out.append("")
    out.append("3. FILE-SIZE GATE: %d blocks, %d full reads of files over %d lines, %d tool calls." % (p.gate_blocks, p.full_big_reads, config()["read_line_threshold"], p.tool_calls))
    if p.followups:
        out.append("   After a block: " + ", ".join("%s %d" % kv for kv in p.followups.most_common()))
    out.append("   Raise read_line_threshold if blocks are mostly answered by a targeted read of a file you were editing anyway; lower it if big full reads persist.")
    return out
