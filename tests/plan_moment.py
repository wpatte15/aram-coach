"""Ask for the plan at one moment of a recorded match, with and without the calculations, and compare.

    .venv\\Scripts\\python.exe tests\\plan_moment.py captures\\20261113-000816 420 [--runs 3] [--augments "Deft,Goliath"]

This costs money: one plan request per run and setting, about $0.05 to $0.10 each, and more
for the first one when the system prompt has gone cold.

It shows what a whole-match replay cannot isolate: at the same moment, with the same
request, how long a plan with calculations takes against one without, what it costs, which
calculations Claude called with which inputs, and whether the build came out different.
Each plan is made fresh, without the plan that was in force, so the two settings are
compared on the choice itself and not on how firmly each holds on to an earlier plan.

What it cannot show: how the plans behave over a match (tests/replay_match.py --tools plan
does), and whether a different build would have won.

Nothing here touches the League client, the coach's own log or its captures.
"""
import argparse
import io
import json
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aramcoach import advisor, config, lcu  # noqa: E402
from aramcoach.coach import Coach  # noqa: E402
from aramcoach.static_data import StaticData  # noqa: E402


def state_at(sd, folder: Path, seconds: int, augments: list) -> dict:
    """The match state the coach had at that game time, from the saved snapshots."""
    class NoSource:
        capture = False

    coach = Coach(sd, NoSource())
    for shot in sorted(folder.glob("t[0-9]*.json"), key=lambda p: int(p.stem[1:])):
        if int(shot.stem[1:]) > seconds:
            break
        coach._on_snapshot(json.loads(shot.read_text(encoding="utf-8")), "live")
    if coach.state is None or coach.state.get("me") is None:
        raise SystemExit(f"No snapshot with the player in it at or before {seconds}s in {folder}")
    state = dict(coach.state)
    state["my_augments"], state["assumed_augments"] = list(augments), []
    return state


def main():
    parser = argparse.ArgumentParser(description="Compare a plan made with the calculations against one made without.")
    parser.add_argument("folder", help="a match folder under captures")
    parser.add_argument("seconds", type=int, help="game time of the moment, in seconds")
    parser.add_argument("--runs", type=int, default=2, help="plans to make with each setting")
    parser.add_argument("--augments", default="", help="augments the player held at that moment, separated by commas")
    parser.add_argument("--only", choices=("plan", "0"), default=None, help="make plans with one setting only")
    parser.add_argument("--show", action="store_true", help="print what each calculation returned")
    args = parser.parse_args()
    folder = Path(args.folder) if Path(args.folder).is_absolute() else ROOT / args.folder

    work = Path(tempfile.mkdtemp(prefix="aramcoach-moment-"))
    config.CAPTURE_DIR, config.LOG_FILE = work / "captures", work / "logs" / "coach.log"
    lcu.queue_info = lambda: {"description": "ARAM: Mayhem", "mapId": 12, "mode": "KIWI"}
    lcu.current_game_id = lambda: None
    sd = StaticData()
    state = state_at(sd, folder, args.seconds, [a.strip() for a in args.augments.split(",") if a.strip()])
    me = state["me"]
    print(f"{me['champion']} level {me['level']} at {int(state['time']) // 60}:{int(state['time']) % 60:02d} | holds "
          f"{[i['name'] for i in me['items']]} | augments {state['my_augments'] or 'none given'}")

    if args.show:                                # print each calculation's answer as it is made
        from aramcoach import tools
        plain_call = tools.Toolbox.call

        def shown_call(self, name, inputs):
            text, failed = plain_call(self, name, inputs)
            print(f"      >>> {name} {json.dumps(inputs)}\n" + "\n".join("      | " + line for line in text.splitlines()))
            return text, failed

        tools.Toolbox.call = shown_call

    totals = {}
    for run in range(args.runs):
        for setting in ([args.only] if args.only else ["0", "plan"]):
            config.TOOLS = setting
            label = "with calculations" if setting == "plan" else "without"
            try:
                advice, meta = advisor.get_advice(sd, state, "", "the player asked for a fresh plan")
            except Exception as exc:
                print(f"  run {run + 1} {label}: FAILED {exc}")
                continue
            build = [b["name"] for b in advice["build_order"]]
            calls = meta.get("tool_calls") or []
            print(f"  run {run + 1} {label}: {meta['latency']}s" + (f" (answers took {meta['turns']})" if meta.get("turns") else "")
                  + f" | ${meta['cost']} | {meta['output_tokens']} output tokens | {' > '.join(build)}")
            for call in calls:
                print(f"      called {call['name']} {json.dumps(call['input'])}" + (" FAILED" if call["failed"] else ""))
            print(f"      next: {advice['build_order'][0]['why'][:260] if advice['build_order'] else ''}")
            if advice.get("changed"):
                print(f"      changed: {advice['changed'][:260]}")
            entry = totals.setdefault(label, {"wait": [], "cost": [], "calls": 0, "plans": 0, "called": 0})
            entry["wait"].append(meta["latency"])
            entry["cost"].append(meta["cost"] or 0)
            entry["calls"] += len(calls)
            entry["called"] += bool(calls)
            entry["plans"] += 1
    print("\nSUMMARY")
    for label, entry in totals.items():
        waits = sorted(entry["wait"])
        print(f"  {label}: {entry['plans']} plans | median wait {waits[len(waits) // 2]}s, longest {waits[-1]}s | "
              f"mean cost ${sum(entry['cost']) / len(entry['cost']):.3f} | plans that called a calculation: {entry['called']} "
              f"({entry['calls']} calls)")


if __name__ == "__main__":
    main()
