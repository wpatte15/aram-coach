"""Effect text for augments the coach has no description of, read from arammayhem.com.

The wiki table the coach uses leaves out quests and a few other augments, which made up one
card in twenty offered. This module reads their effect text, the game's own words for what
the augment does, and nothing else.

The site also publishes how often players pick each augment and what they build on each
champion. None of that is read, kept or used. An earlier version passed it to Claude, and
the advice moved toward what most players do, which a statistics overlay already shows the
player. The coach is for reasoning about one match.

Two kinds of page are read: the augment list, for the address of each augment's own page,
and the pages of the augments that lack text. All of it is best effort: a page that cannot
be had, or that no longer reads the way this module expects, gives nothing. Set
ARAMCOACH_AUGMENT_TEXT=0 to never contact the site. The only thing a request reveals is an
augment name.
"""
from __future__ import annotations

import html
import json
import re
import threading
import time

import requests

from . import config
from .log import log
from .static_data import NO_EFFECT_TEXT, norm

SITE = "https://arammayhem.com"
_HEADERS = {"User-Agent": "Mozilla/5.0"}
RETRY_SECONDS = 2 * 86400         # an augment the site had no page for is looked for again after this long
MIN_AUGMENTS = 100                # an augment list with fewer links than this was not read properly
MAX_PAGES = 12                    # augment pages read in one go
_lock = threading.Lock()
_busy = False


def page_lines(page: str) -> list:
    """The visible text of a page, one piece per line, in reading order."""
    page = re.sub(r"<!--.*?-->|<script.*?</script>|<style.*?</style>", " ", page, flags=re.S)
    return [html.unescape(piece.strip()) for piece in re.sub(r"<[^>]+>", "\n", page).split("\n") if piece.strip()]


def key_for(name: str) -> str:
    """How an augment is looked up: the site writes quests as "Quest: Steel Your Heart"."""
    return norm(re.sub(r"^\s*quest\s*:", "", name, flags=re.I))


def parse_slugs(page: str) -> dict:
    """Read the augment list for the address of each augment's page: {key_for(name): slug}.

    Every piece of text inside a link to an augment page is taken as a possible name. The
    numbers a row also holds are not kept.
    """
    slugs = {}
    for slug, inner in re.findall(r'<a[^>]+href="/augments/([^"/#?]+)/?"[^>]*>(.*?)</a>', page, flags=re.S):
        for piece in page_lines(inner):
            if re.search(r"[A-Za-z]{2}", piece) and piece not in ("Prismatic", "Gold", "Silver"):
                slugs.setdefault(key_for(piece), slug)
    return slugs


def parse_augment_text(page: str) -> str:
    """The effect text on one augment's own page, or an empty string."""
    lines = page_lines(page)
    for i, line in enumerate(lines):
        if line.startswith("← Back to Augments") and i + 3 < len(lines) and lines[i + 2] in ("Prismatic", "Gold", "Silver"):
            # The text is split wherever the page styles a word: a quest's runs to a dozen pieces.
            end = next((j for j in range(i + 3, min(i + 45, len(lines))) if lines[j].startswith("Last updated")), None)
            return re.sub(r"\s+([,.])", r"\1", " ".join(lines[i + 3: end]))[:400] if end else ""
    return ""


def _path(sd):
    return sd.dir / "augment_text.json"


def _saved(sd) -> dict:
    try:
        data = json.loads(_path(sd).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _get(url: str) -> str:
    response = requests.get(url, headers=_HEADERS, timeout=12)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


def texts(sd, fetch: bool = False) -> dict:
    """Effect text from the site for augments the coach has no description of: {augment name: text}.

    With fetch, looks for up to a dozen missing ones and saves what it finds. An augment the
    site has no page or no text for is remembered, so it is not asked for on every start.
    """
    saved = _saved(sd)
    found, tried = saved.get("data") or {}, saved.get("tried") or {}
    if not (fetch and config.AUGMENT_TEXT):
        return found
    now = time.time()
    lacking = lambda a: not a["description"] or NO_EFFECT_TEXT in a["description"]
    wanted = [a["name"] for a in sd.augments_all() if lacking(a) and re.search(r"[A-Za-z]{2}", a["name"])
              and not found.get(a["name"]) and now - tried.get(a["name"], 0) > RETRY_SECONDS]
    if not wanted:
        return found
    try:
        slugs = parse_slugs(_get(f"{SITE}/augments/"))
    except requests.RequestException as exc:
        log("augment_text_failed", page="augment list", error=repr(exc)[:160])
        return found
    if len(set(slugs.values())) < MIN_AUGMENTS:
        log("augment_text_unreadable", page="augment list")     # the site changed its layout
        return found
    pages = 0
    for name in wanted:
        slug = slugs.get(key_for(name))
        if not slug:
            tried[name] = now                      # the site has no page for it
            continue
        if pages >= MAX_PAGES:
            continue                               # left for the next start
        pages += 1
        try:
            text = parse_augment_text(_get(f"{SITE}/augments/{slug}/"))
            time.sleep(0.5)
        except requests.RequestException as exc:
            log("augment_text_failed", page=f"augment {name}", error=repr(exc)[:160])
            break
        tried[name] = now
        if text and not text.rstrip().endswith(":"):       # the site has the same gap for a few: a heading and no effect
            found[name] = text
    _path(sd).parent.mkdir(parents=True, exist_ok=True)
    _path(sd).write_text(json.dumps({"fetched": now, "data": found, "tried": tried}, ensure_ascii=False), encoding="utf-8")
    return found


def prepare(sd):
    """Look for missing augment text in the background. Safe to call often; what it finds is used from the next start."""
    global _busy
    if not config.AUGMENT_TEXT:
        return
    with _lock:
        if _busy:
            return
        _busy = True

    def work():
        global _busy
        try:
            texts(sd, fetch=True)
        except Exception as exc:                   # nothing here may disturb the coach
            log("augment_text_failed", page="*", error=repr(exc)[:160])
        finally:
            _busy = False

    threading.Thread(target=work, name="augment-text", daemon=True).start()
