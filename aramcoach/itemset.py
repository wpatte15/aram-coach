"""Writes the plan into League's in-game shop as an item set.

The game loads item set files from Config\\Global\\Recommended and shows them in the shop's
item set dropdown. Other companion apps use the same folder.

The game reads the file once, when the match loads. A rewrite during the match does not show
in the shop (tried over several real games). The set written in champion select is therefore
built to cover what later plans might ask for: the main build, a group per enemy type, a
group per direction an augment could push the build, and a pool of other items that suit the
champion.
"""
from __future__ import annotations

import json

from . import lcu, shop

FILE_NAME = "!!!aramcoach-0.json"       # leading "!" sorts the set to the top of the list
START_GOLD = 1400                        # starting gold observed in ARAM: Mayhem


def _block(title: str, item_ids: list) -> dict:
    return {
        "type": title, "recMath": False, "minSummonerLevel": -1, "maxSummonerLevel": -1,
        "showIfSummonerSpell": "", "hideIfSummonerSpell": "",
        "items": [{"id": str(i), "count": 1} for i in item_ids],
    }


def _path():
    root = lcu.install_dir()
    return None if root is None else root / "Config" / "Global" / "Recommended" / FILE_NAME


def clear():
    """Remove the coach's item set file.

    Sets in the Global folder show for every champion, whatever `championKey` says (seen in
    a real game: a Thresh set appeared for Xayah). A set left over from an earlier game is
    therefore wrong for the next one, so it is removed whenever it is no longer current.
    """
    path = _path()
    if path is not None:
        path.unlink(missing_ok=True)


def build(sd, champ_id: str, advice: dict) -> dict:
    """Item set content for one champion.

    advice: the champion-select plan. Its build order becomes the main blocks. Its
      `situational` groups (by enemy type), `augment_builds` groups (by augment direction)
      and `pool` follow, so that items a later plan names are already in the shop.
    """
    order = [b["item_id"] for b in advice["build_order"]]
    start = [p["id"] for p in shop.plan(order, [], START_GOLD, sd.items)["purchases"]]
    blocks = [
        _block(f"1. Buy at the start ({START_GOLD} gold)", start),
        _block("2. Then finish these, left to right", order),
    ]
    listed = set(order)
    for group in (advice.get("situational") or []) + (advice.get("augment_builds") or []):
        if group.get("item_ids"):
            blocks.append(_block(group["title"], group["item_ids"]))
            listed.update(group["item_ids"])
    pool = [i for i in advice.get("pool") or [] if i not in listed]
    if pool:
        blocks.append(_block("Other items the coach may call for", pool))
    return {
        "title": f"Coach: {advice.get('title') or champ_id}",
        "championKey": champ_id,         # informational: the game shows Global sets for every champion
        "map": "any", "mode": "any", "type": "custom", "priority": True, "sortrank": 1000000001,
        "blocks": blocks,
    }


def item_ids(item_set: dict) -> list:
    """Every item id that appears anywhere in an item set, without repeats."""
    return list(dict.fromkeys(int(entry["id"]) for block in item_set["blocks"] for entry in block["items"]))


def write(sd, champ_id: str, advice: dict):
    """Write the item set file. Returns (path, item set), or (None, None) when League's folder cannot be found."""
    path = _path()
    if path is None:
        return None, None
    path.parent.mkdir(parents=True, exist_ok=True)
    item_set = build(sd, champ_id, advice)
    path.write_text(json.dumps(item_set, indent=2), encoding="utf-8")
    return path, item_set
