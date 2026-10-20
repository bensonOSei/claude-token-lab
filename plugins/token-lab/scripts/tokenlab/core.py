import json
import os
from datetime import datetime, timedelta, timezone

PROJECTS = os.path.expanduser("~/.claude/projects")
STATE = os.path.expanduser(os.environ.get("TOKEN_LAB_HOME", "~/.claude/token-lab"))
LOCAL = datetime.now().astimezone().tzinfo
NOW = datetime.now(timezone.utc)

DEFAULT_CONFIG = {
    "baseline_days": 7,
    "read_line_threshold": 350,
    "gate": True,
    "routing": True,
    "checklist": True,
    "session_rules": True,
    "gate_exempt": [],
    "routing_allow_patterns": [],
    "routing_implementer_patterns": [],
    "prices": {"fable": 15.0, "opus": 5.0, "sonnet": 3.0, "haiku": 1.0},
    "multipliers": {"cache_read": 0.1, "cache_write_5m": 1.25, "cache_write_1h": 2.0, "output": 5.0},
}


def load_json(name, default):
    try:
        with open(os.path.join(STATE, name)) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def save_json(name, data):
    os.makedirs(STATE, exist_ok=True)
    fp = os.path.join(STATE, name)
    tmp = fp + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, fp)


def config():
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(load_json("config.json", {}))
    return cfg


def parse_time(s):
    t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=LOCAL)


def experiments():
    xs = load_json("experiments.json", [])
    return sorted(xs, key=lambda x: x["start"])


def periods():
    xs = experiments()
    if not xs:
        return [("last-7d", "Last 7 days (no experiments yet)", NOW - timedelta(days=7), NOW)]
    days = config()["baseline_days"]
    first = parse_time(xs[0]["start"])
    out = [("baseline", "%d days before %s" % (days, xs[0]["name"]), first - timedelta(days=days), first)]
    for i, x in enumerate(xs):
        a = parse_time(x["start"])
        b = parse_time(x["end"]) if x.get("end") else (parse_time(xs[i + 1]["start"]) if i + 1 < len(xs) else NOW)
        out.append((x["name"], x.get("note") or x["name"], a, min(b, NOW)))
    return out


def period_of(t, ps):
    for key, _, a, b in ps:
        if a <= t < b:
            return key
    return None


def records(fp):
    try:
        with open(fp, errors="replace") as fh:
            for line in fh:
                try:
                    yield json.loads(line)
                except ValueError:
                    pass
    except OSError:
        return


def ts(r):
    t = r.get("timestamp")
    if not t:
        return None
    try:
        return datetime.fromisoformat(t.replace("Z", "+00:00"))
    except ValueError:
        return None


def transcripts(since):
    for dirpath, _, files in os.walk(PROJECTS):
        is_sub = "/subagents" in dirpath
        for f in files:
            if not f.endswith(".jsonl"):
                continue
            fp = os.path.join(dirpath, f)
            try:
                if os.path.getmtime(fp) < since.timestamp():
                    continue
            except OSError:
                continue
            yield fp, is_sub


def meta_of(fp):
    try:
        with open(fp[:-6] + ".meta.json") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def text_of(c):
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "".join(b.get("text", "") for b in c if isinstance(b, dict))
    return ""


def tier(model):
    for k in ("fable", "opus", "sonnet", "haiku"):
        if k in (model or ""):
            return k
    return None


def cost(i, model, cfg):
    t = tier(model)
    p = cfg["prices"].get(t) if t else None
    if not p:
        return 0.0
    m = cfg["multipliers"]
    cc = i.get("cache_creation") or {}
    h1 = cc.get("ephemeral_1h_input_tokens", 0)
    m5 = i.get("cache_creation_input_tokens", 0) - h1
    return p * (
        i.get("input_tokens", 0)
        + m["cache_write_5m"] * m5
        + m["cache_write_1h"] * h1
        + m["cache_read"] * i.get("cache_read_input_tokens", 0)
        + m["output"] * i.get("output_tokens", 0)
    ) / 1e6


def turn(r, seen, scope, cfg):
    """One assistant message, counted once. Transcripts write a record per content block,
    and advisor calls report the executor context twice, so raw usage over-counts."""
    if r.get("type") != "assistant":
        return None
    m = r.get("message") or {}
    u = m.get("usage")
    if not u:
        return None
    key = (scope, m.get("id") or r.get("uuid"))
    if key in seen:
        return None
    seen.add(key)
    its = u.get("iterations") or [dict(u, type="message", model=m.get("model"))]
    msgs = [i for i in its if i.get("type") == "message"] or its[-1:]
    last = msgs[-1]
    ctx = last.get("input_tokens", 0) + last.get("cache_read_input_tokens", 0) + last.get("cache_creation_input_tokens", 0)
    advisor = [i for i in its if i.get("type") == "advisor_message"]
    return {
        "model": m.get("model"),
        "ctx": ctx,
        "processed": sum(i.get("input_tokens", 0) + i.get("cache_read_input_tokens", 0) + i.get("cache_creation_input_tokens", 0) + i.get("output_tokens", 0) for i in msgs),
        "output": sum(i.get("output_tokens", 0) for i in msgs),
        "cost": sum(cost(i, i.get("model") or m.get("model"), cfg) for i in its),
        "advisor_calls": len(advisor),
        "advisor_cost": sum(cost(i, i.get("model"), cfg) for i in advisor),
    }


def pct(xs, q):
    if not xs:
        return 0
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * q))]


def k(n):
    return "%dk" % round(n / 1000)


def short_model(m):
    return (m or "?").replace("claude-", "")
