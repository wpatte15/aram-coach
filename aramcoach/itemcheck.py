"""Item rules a program can decide, applied on top of Claude's build.

Claude chooses the build. Real games showed two kinds of mistake that instructions alone did
not prevent and that are cheap to rule out here:

- an item whose only effect is behind its button, for a player who never presses item buttons
  (Locket of the Iron Solari was the first or third item on three champions);
- an item whose passive fires when the holder heals or shields a teammate, for a champion who
  does not (Moonstone Renewer as Zilean's first item: 367 healing in the whole match).

`facts` gives Claude what was worked out, as lines for a request. `rejected` lists the items a
plan must not contain; the advisor removes any that still appear.
"""
from __future__ import annotations

import re

from . import config

RARE_COOLDOWN = 40.0     # seconds. An ability slower than this is cast about once a fight.

_ALLY = re.compile(r"\b(ally|allies|allied|friendly|teammates?)\b", re.I)
_MEND = re.compile(r"\b(heal\w*|shield\w*|restor\w*)\b", re.I)
_COOLDOWN = re.compile(r"\(cooldown ([\d./]+)s\)")


def ally_support(sd, champ_id) -> list | None:
    """The abilities in a kit that heal or shield a teammate: [(slot, shortest cooldown in seconds)].

    Read from the champion notes, which hold each ability's description and its numbers by
    rank. An ability counts when its text names an ally and a heal, shield or restore. That
    errs toward counting too much, which only leaves the decision to Claude. Returns None when
    the notes cannot be read, so that missing data rules nothing out.
    """
    notes = sd.champion_notes(champ_id) if champ_id else None
    if not notes:
        return None
    found = []
    for slot, text in [("its passive", notes["passive"])] + [(s[:1], s) for s in notes["spells"]]:
        if _ALLY.search(text) and _MEND.search(text):
            cooldown = _COOLDOWN.search(text)
            values = [float(v) for v in cooldown.group(1).split("/") if v] if cooldown else []
            found.append((slot, min(values) if values else 0.0))
    return found


def _support_verdict(sd, champ_id):
    """(works, text): whether heal-or-shield items can trigger on this kit, and the reason in words."""
    support = ally_support(sd, champ_id)
    if support is None:
        return True, ""
    slots = " and ".join(slot for slot, _ in support)
    if not support:
        return False, "this kit has no ability that heals or shields an ally"
    if all(cooldown >= RARE_COOLDOWN for _, cooldown in support):
        return False, f"this kit heals or shields an ally only with {slots}, about once a fight"
    return True, f"this kit heals or shields an ally with {slots}"


def rejected(sd, champ_id, catalog: list) -> dict:
    """Catalog items a plan for this champion and this player must not contain: {item id: reason}."""
    out = {}
    if not config.presses_item_buttons():
        for item in catalog:
            if item["button_only"]:
                out[item["id"]] = "its only effect is behind a button, and the player never presses item buttons"
    works, why = _support_verdict(sd, champ_id)
    if not works:
        for item in catalog:
            if item["ally_trigger"]:
                out.setdefault(item["id"], f"its passive fires on healing or shielding an ally, and {why}")
    return out


def facts(sd, champ_id, catalog: list) -> list:
    """What the coach worked out about items for this champion and this player, as lines for a request."""
    lines = []
    if not config.presses_item_buttons():
        names = ", ".join(item["name"] for item in catalog if item["button_only"])
        lines.append("The player never presses item buttons. A BUTTON-ONLY item is its stats and nothing more "
                     f"for them and must not be listed: {names}.")
    works, why = _support_verdict(sd, champ_id)
    triggered = ", ".join(item["name"] for item in catalog if item["ally_trigger"])
    if why and not works:
        lines.append(f"{why[0].upper()}{why[1:]}. These fire only on healing or shielding an ally and must not be "
                     f"listed: {triggered}. Heal and Shield Power on any item is worth next to nothing here.")
    elif why:
        lines.append(f"{why[0].upper()}{why[1:]}. Items that fire on healing or shielding an ally ({triggered}) "
                     "trigger only when those abilities are cast on a teammate.")
    resource = (sd.champions.get(champ_id) or {}).get("resource")
    if resource and resource != "Mana":
        lines.append("This champion does not use mana: mana and mana regeneration on an item are wasted.")
    return lines
