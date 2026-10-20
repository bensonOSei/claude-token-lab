import os
import re
from collections import Counter, defaultdict

from .core import config, meta_of, period_of, periods, records, text_of, transcripts, ts, turn

BUCKET = 300
GATE_BLOCK = "check-file-size.sh]: Blocked:"
BLOCK_RE = re.compile(r"Blocked: (\S+) is (\d+) lines")
RUN_RE = re.compile(r"\.superpowers/sdd/([^/\s`'\"]+)/")
TASK_RE = re.compile(r"\btasks?[ -]?(\d+)\b", re.I)


def role(desc):
    d = (desc or "").lower()
    if re.search(r"re-?review", d):
        return "re-review"
    if "review" in d and re.search(r"final|whole|branch|wave", d) and not re.search(r"\bfix", d):
        return "final-review"
    if re.search(r"review|audit|verif", d):
        return "review"
    if re.search(r"\bfix(es|er)?\b|fix round|fix wave", d):
        return "fix"
    if re.search(r"implement|^tasks? [a-z0-9.+ ]*:", d):
        return "implement"
    if re.search(r"\bplan\b|design|architect|pre-?flight|scan|research|investigat|debug", d):
        return "judgment"
    return "other"


class Period:
    def __init__(self, key, label, a, b):
        self.key, self.label, self.a, self.b = key, label, a, b
        self.hours = max(1e-9, (b - a).total_seconds() / 3600)
        self.ctx = []
        self.peaks = {}
        self.cost_main = 0.0
        self.cost_sub = 0.0
        self.advisor_calls = 0
        self.advisor_cost = 0.0
        self.buckets = set()
        self.session_buckets = set()
        self.compactions = []
        self.gate_blocks = 0
        self.followups = Counter()
        self.full_big_reads = 0
        self.tool_calls = 0
        self.dispatches = []
        self.subs = []

    @property
    def turns(self):
        return len(self.ctx)

    @property
    def active_hours(self):
        return len(self.buckets) * BUCKET / 3600

    @property
    def session_hours(self):
        return len(self.session_buckets) * BUCKET / 3600

    @property
    def cost(self):
        return self.cost_main + self.cost_sub


def scan(ps=None):
    cfg = config()
    ps = ps or periods()
    out = {key: Period(key, label, a, b) for key, label, a, b in ps}
    since = min(a for _, _, a, _ in ps)
    seen = set()
    cwds = set()
    for fp, is_sub in transcripts(since):
        if is_sub:
            _scan_sub(fp, ps, out, seen, cfg)
        else:
            _scan_main(fp, ps, out, seen, cfg, cwds)
    return [out[key] for key, _, _, _ in ps], cwds


def _scan_main(fp, ps, out, seen, cfg, cwds):
    sid = os.path.basename(fp)[:-6]
    uses = {}
    pending = None
    threshold = cfg["read_line_threshold"]
    for r in records(fp):
        t = ts(r)
        if t is None:
            continue
        key = period_of(t, ps)
        p = out.get(key)
        if p is None:
            continue
        if r.get("cwd"):
            cwds.add(r["cwd"])
        if r.get("subtype") == "compact_boundary":
            cm = r.get("compactMetadata") or {}
            p.compactions.append(("auto" if cm.get("trigger") == "auto" else "manual", cm.get("preTokens") or 0))
        tu = turn(r, seen, "", cfg)
        if tu:
            p.ctx.append(tu["ctx"])
            p.peaks[sid] = max(p.peaks.get(sid, 0), tu["ctx"])
            p.cost_main += tu["cost"]
            p.advisor_calls += tu["advisor_calls"]
            p.advisor_cost += tu["advisor_cost"]
            b = int(t.timestamp()) // BUCKET
            p.buckets.add(b)
            p.session_buckets.add((sid, b))
        content = (r.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for blk in content:
            if not isinstance(blk, dict):
                continue
            if blk.get("type") == "tool_use":
                name, inp = blk.get("name"), blk.get("input") or {}
                uses[blk.get("id")] = (name, inp)
                p.tool_calls += 1
                if name == "Agent":
                    p.dispatches.append({"type": inp.get("subagent_type") or "general-purpose", "model": inp.get("model") or "", "description": inp.get("description") or ""})
                if pending is not None:
                    p.followups[_followup(pending, name, inp)] += 1
                    pending = None
            elif blk.get("type") == "tool_result":
                tx = text_of(blk.get("content"))
                name, inp = uses.get(blk.get("tool_use_id"), (None, {}))
                if GATE_BLOCK in tx:
                    p.gate_blocks += 1
                    mm = BLOCK_RE.search(tx)
                    pending = mm.group(1) if mm else None
                    continue
                if name == "Read" and not inp.get("limit"):
                    tur = r.get("toolUseResult")
                    fl = tur.get("file") if isinstance(tur, dict) else None
                    if isinstance(fl, dict) and (fl.get("totalLines") or 0) > threshold:
                        p.full_big_reads += 1


def _followup(pending, name, inp):
    base = os.path.basename(pending)
    cmd = inp.get("command", "") if name == "Bash" else ""
    if name == "Agent" and (inp.get("subagent_type") or "").endswith("bulk-reader"):
        return "delegated to bulk-reader"
    if name == "Agent":
        return "delegated to another agent"
    if name == "Read" and inp.get("file_path") == pending and inp.get("limit"):
        return "targeted read of the same file"
    if name in ("Grep", "Glob") or (base in cmd and re.search(r"\b(grep|rg|wc)\b", cmd)):
        return "searched the file instead"
    if base in cmd:
        return "dumped it another way"
    return "moved on"


def _scan_sub(fp, ps, out, seen, cfg):
    meta = meta_of(fp)
    desc = meta.get("description") or ""
    first = last = None
    models = Counter()
    usd = 0.0
    tokens = 0
    tools = 0
    prompt = ""
    reply = ""
    for r in records(fp):
        t = ts(r)
        if t is None:
            continue
        m = r.get("message") or {}
        if not prompt and r.get("type") == "user":
            prompt = text_of(m.get("content"))
        tu = turn(r, seen, fp, cfg)
        if tu:
            first = first or t
            last = t
            models[tu["model"] or "?"] += 1
            usd += tu["cost"]
            tokens += tu["processed"]
        if r.get("type") == "assistant" and isinstance(m.get("content"), list):
            for b in m["content"]:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use":
                    if b.get("name") == "SubagentHandback":
                        reply = (b.get("input") or {}).get("message", "") or reply
                    else:
                        tools += 1
                elif b.get("type") == "text" and b.get("text", "").strip():
                    if not reply or "Assessment" in b["text"]:
                        reply = b["text"]
    if first is None:
        return
    p = out.get(period_of(first, ps))
    if p is None:
        return
    run = RUN_RE.search(prompt)
    task = TASK_RE.search(desc)
    p.cost_sub += usd
    p.subs.append({
        "agent": meta.get("agentType") or "unknown",
        "model": models.most_common(1)[0][0],
        "cost": usd,
        "tokens": tokens,
        "tools": tools,
        "seconds": (last - first).total_seconds(),
        "description": desc,
        "role": role(desc),
        "run": run.group(1) if run else None,
        "task": int(task.group(1)) if task else None,
        "at": first,
        "reply": reply,
    })
