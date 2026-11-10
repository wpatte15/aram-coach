"""Settings.

Each named setting is read from the environment first, then from the `.env` file in the
project folder (one NAME=value per line).
"""
import os
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
ROOT = PKG_DIR.parent


def _read_dotenv() -> dict:
    values = {}
    try:
        for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                name, value = line.split("=", 1)
                values[name.strip()] = value.strip().strip("\"'")
    except OSError:
        pass
    return values


_DOTENV = _read_dotenv()


def _setting(name: str, default: str = "") -> str:
    return os.environ.get(name) or _DOTENV.get(name) or default


CACHE_DIR = ROOT / "cache"        # downloaded game data and generated prompt files
CAPTURE_DIR = ROOT / "captures"   # raw game API payloads, one folder per game
LOG_FILE = ROOT / "logs" / "coach.log"
PLAYER_FILE = ROOT / "player.txt"   # the player's own description of their skill; see player.example.txt

_DEFAULT_PLAYER = ("I am new to League of Legends. The number of items and augments is overwhelming, and I do not "
                   "know what most items do or why one is better than another.")


def player_profile() -> str:
    """What the player says about themselves. Read on every request, so edits apply without a restart."""
    try:
        text = PLAYER_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        text = ""
    return text[:2000] or _DEFAULT_PLAYER


WEB_DIR = PKG_DIR / "web"

# The game serves this on loopback only while a match is running.
LIVE_URL = "https://127.0.0.1:2999/liveclientdata/allgamedata"

HOST = _setting("ARAMCOACH_HOST", "127.0.0.1")
PORT = int(_setting("ARAMCOACH_PORT", "8777"))

# The key is kept out of os.environ on purpose. A machine-wide ANTHROPIC_API_KEY would also
# switch Claude Code itself from the subscription to paid API billing.
API_KEY = _setting("ANTHROPIC_API_KEY")
BACKEND = _setting("ARAMCOACH_BACKEND") or ("api" if API_KEY else "cli")   # api | cli

MODEL = _setting("ARAMCOACH_MODEL", "claude-opus-5-5")
# Effort trades answer speed for depth: low | medium | high | xhigh | max.
EFFORT = _setting("ARAMCOACH_EFFORT", "low")
# "fast" runs the same model at higher output speed for twice the price (API backend only).
SPEED = _setting("ARAMCOACH_SPEED", "standard")          # standard | fast
# Key that makes the coach read the game screen (augment choices). F1 to F12.
HOTKEY = _setting("ARAMCOACH_HOTKEY", "F9").upper()
LLM_TIMEOUT = 120            # seconds before a Claude call is abandoned

POLL_SECONDS = 1.0           # how often the game API is read
# A real 20-minute 5v5 made 36 plans for $2.32, and 21 of them were triggered by enemy purchases
# that changed the build only five times. The three values below cut that down.
# Plans are made when the player dies, not while they are alive: they cannot shop or read the
# panel mid-fight. Set ARAMCOACH_UPDATE_WHILE_ALIVE=1 to also update on enemy purchases while
# alive, which keeps the plan fresher at the moment of death for about 50% more plans.
UPDATE_WHILE_ALIVE = _setting("ARAMCOACH_UPDATE_WHILE_ALIVE") == "1"
MIN_ADVICE_INTERVAL = 60.0   # minimum gap between routine plan updates (deaths and manual refreshes skip it)
DEATH_REFRESH_AFTER = 45.0   # a death asks for a new plan only when the current one is older than this
DEATH_PLAN_WAIT = 2.0        # in Mayhem, hold a death's plan this long to see whether an augment offer opens
PERIODIC_REFRESH = 150.0     # refresh the plan this often when the game has moved on
RETRY_AFTER_ERROR = 30.0     # wait this long after a failed Claude call before trying again
CAPTURE_EVERY = 30.0         # seconds between raw payload captures
BIG_ITEM_GOLD = 2000         # an enemy purchase at or above this price (a finished item) triggers a plan update
