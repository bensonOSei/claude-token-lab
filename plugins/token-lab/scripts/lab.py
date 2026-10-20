#!/usr/bin/env python3
import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tokenlab import baseline, page, reports, train  # noqa: E402
from tokenlab.core import DEFAULT_CONFIG, NOW, STATE, config, experiments, load_json, parse_time, periods, save_json  # noqa: E402
from tokenlab.scan import scan  # noqa: E402

PRETRAINED = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "baseline", "pretrained.json")


def cmd_report(a):
    ps, cwds = scan()
    if a.html is not None:
        fp = a.html or os.path.join(STATE, "reports", "report-%s.html" % NOW.astimezone().strftime("%Y-%m-%d"))
        print(page.write(ps, cwds, os.path.expanduser(fp), with_git=not a.no_git, conclusion_file=a.conclusion))
        if not a.save:
            return
    text = reports.full(ps, cwds, with_git=not a.no_git)
    if a.save:
        d = os.path.join(STATE, "reports")
        os.makedirs(d, exist_ok=True)
        fp = os.path.join(d, "report-%s.txt" % NOW.astimezone().strftime("%Y-%m-%d"))
        with open(fp, "w") as fh:
            fh.write(text + "\n")
        print(fp)
    else:
        print(text)


def cmd_section(a):
    ps, cwds = scan()
    fn = {
        "normalised": lambda: reports.normalised(ps, cwds, not a.no_git),
        "sessions": lambda: reports.sessions(ps),
        "subagents": lambda: reports.subagents(ps),
        "quality": lambda: reports.quality(ps),
        "bulk-reader": lambda: reports.bulk_reader(ps),
        "gate": lambda: reports.gate(ps),
    }[a.name]
    print("\n".join(reports.period_header(ps) + [""] + fn()))


def cmd_routing(_):
    print("\n".join(reports.routing()))


def cmd_start(a):
    xs = experiments()
    when = parse_time(a.at) if a.at else datetime.now().astimezone()
    if any(x["name"] == a.name for x in xs):
        raise SystemExit("an experiment named %r already exists" % a.name)
    xs.append({"name": a.name, "start": when.isoformat(timespec="minutes"), "note": a.note or ""})
    save_json("experiments.json", sorted(xs, key=lambda x: x["start"]))
    print("started %s at %s" % (a.name, when.strftime("%Y-%m-%d %H:%M")))


def cmd_stop(a):
    xs = experiments()
    open_ = [x for x in xs if not x.get("end")]
    target = next((x for x in xs if x["name"] == a.name), None) if a.name else (open_[-1] if open_ else None)
    if not target:
        raise SystemExit("no open experiment to stop")
    target["end"] = datetime.now().astimezone().isoformat(timespec="minutes")
    save_json("experiments.json", xs)
    print("stopped %s" % target["name"])


def cmd_list(_):
    xs = experiments()
    if not xs:
        print("no experiments yet. Start one with: lab.py start NAME --note 'what changed'")
    for x in xs:
        print("%-24s %s -> %s  %s" % (x["name"], x["start"], x.get("end") or "open", x.get("note", "")))
    print("")
    for key, label, a, b in periods():
        print("period %-20s %s -> %s  %s" % (key, a.astimezone().strftime("%m-%d %H:%M"), b.astimezone().strftime("%m-%d %H:%M"), label))


def cmd_baseline(a):
    ps, _ = scan()
    data = baseline.aggregate(ps, a.label)
    fp = a.out or os.path.join(STATE, "baseline-%s.json" % NOW.astimezone().strftime("%Y-%m-%d"))
    with open(fp, "w") as fh:
        json.dump(data, fh, indent=1)
        fh.write("\n")
    print(fp)


def cmd_compare(a):
    ps, _ = scan()
    mine = baseline.aggregate(ps, "you")
    ref = baseline.load(a.ref or PRETRAINED)
    print("\n".join(baseline.compare(mine, ref)))


def cmd_train(a):
    print("\n".join(train.run(days=a.days)))


def cmd_config(a):
    cfg = load_json("config.json", {})
    if a.set:
        key, _, val = a.set.partition("=")
        if key not in DEFAULT_CONFIG:
            raise SystemExit("unknown key %r; known: %s" % (key, ", ".join(sorted(DEFAULT_CONFIG))))
        try:
            cfg[key] = json.loads(val)
        except ValueError:
            cfg[key] = val
        save_json("config.json", cfg)
    print(json.dumps(config(), indent=2))


def main():
    ap = argparse.ArgumentParser(prog="lab.py", description="token-lab: measure Claude Code token use and run experiments")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("report", help="full report across baseline and experiment periods")
    s.add_argument("--save", action="store_true", help="write to ~/.claude/token-lab/reports/")
    s.add_argument("--no-git", action="store_true", help="skip commit and line counts")
    s.add_argument("--html", nargs="?", const="", default=None, metavar="PATH", help="write the report as a self-contained HTML page (default ~/.claude/token-lab/reports/report-DATE.html)")
    s.add_argument("--conclusion", metavar="FILE", help="with --html: use these 'Topic: sentence' lines as the In conclusion section instead of the generated one")
    s.set_defaults(fn=cmd_report)
    s = sub.add_parser("section", help="one report section")
    s.add_argument("name", choices=["normalised", "sessions", "subagents", "quality", "bulk-reader", "gate"])
    s.add_argument("--no-git", action="store_true")
    s.set_defaults(fn=cmd_section)
    sub.add_parser("routing", help="model-routing hook decisions").set_defaults(fn=cmd_routing)
    s = sub.add_parser("start", help="mark the start of an experiment (a change you made)")
    s.add_argument("name")
    s.add_argument("--note")
    s.add_argument("--at", help="ISO time, default now")
    s.set_defaults(fn=cmd_start)
    s = sub.add_parser("stop", help="close an experiment")
    s.add_argument("name", nargs="?")
    s.set_defaults(fn=cmd_stop)
    sub.add_parser("list", help="experiments and the periods they define").set_defaults(fn=cmd_list)
    s = sub.add_parser("baseline", help="export your aggregate numbers (no names, paths or prompts)")
    s.add_argument("--label", default="my baseline")
    s.add_argument("--out")
    s.set_defaults(fn=cmd_baseline)
    s = sub.add_parser("compare", help="compare your periods with the pretrained baseline or another export")
    s.add_argument("--ref")
    s.set_defaults(fn=cmd_compare)
    s = sub.add_parser("train", help="calibrate the routing classifier, mine review findings, check the gate")
    s.add_argument("--days", type=int, default=28)
    s.set_defaults(fn=cmd_train)
    s = sub.add_parser("config", help="show or set config (KEY=JSON)")
    s.add_argument("--set")
    s.set_defaults(fn=cmd_config)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
