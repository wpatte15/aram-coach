"""Entry point: `py -3.12 -m aramcoach`."""
from __future__ import annotations

import argparse
import threading

import uvicorn

from . import config, llm, screen
from .coach import Coach
from .demo import DemoSource
from .live import LiveSource, ReplaySource
from .log import log
from .pregame import Pregame
from .server import create_app
from .static_data import StaticData


def main():
    parser = argparse.ArgumentParser(prog="aramcoach", description="Live ARAM coach panel.")
    parser.add_argument("--demo", action="store_true", help="use a built-in sample game instead of the live client")
    parser.add_argument("--replay", metavar="PATH", help="replay a captured payload file, or a folder of them")
    parser.add_argument("--host", default=config.HOST, help=f"address to serve on (default {config.HOST})")
    parser.add_argument("--port", type=int, default=config.PORT, help=f"port to serve on (default {config.PORT})")
    args = parser.parse_args()

    print("Loading game data...")
    sd = StaticData()
    if sd.augment_error:
        print(f"Augment data is unavailable ({sd.augment_error}). Continuing without it.")
    live_mode = not (args.demo or args.replay)
    source = DemoSource(sd) if args.demo else ReplaySource(args.replay) if args.replay else LiveSource()
    threading.Thread(target=llm.warm_up, name="warm-up", daemon=True).start()
    coach = Coach(sd, source)
    coach.start(watch_screen=live_mode)      # in a live game, watch the screen for augment offers
    if live_mode:
        Pregame(sd, coach).start()           # champion select and loading screen plans, item set
    hotkey = live_mode and screen.watch_keys(config.HOTKEY, coach.read_screen, coach.capture_scoreboard)

    backend = (f"Anthropic API, {config.SPEED} speed" if config.BACKEND == "api" else "Claude Code login")
    log("startup", mode="demo" if args.demo else "replay" if args.replay else "live", model=config.MODEL,
        effort=config.EFFORT, backend=backend, hotkey=config.HOTKEY if hotkey else None, game_data=sd.version)
    print(f"ARAM Coach is running at http://{args.host}:{args.port}")
    print(f"Game data {sd.version}. Model {config.MODEL}, effort {config.EFFORT}, via {backend}.")
    if hotkey:
        print(f"Press {config.HOTKEY} in game to have the coach read your screen, for example at an augment choice.")
    uvicorn.run(create_app(coach), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
