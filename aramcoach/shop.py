"""Turns a build order plus the player's gold and inventory into the exact purchases to make now.

Claude chooses which finished items to build. This module does the arithmetic: recipe
costs, components already owned, and inventory slots. That keeps the "buy now" answer
instant and exact when the player dies, without waiting for a model call.
"""
from __future__ import annotations

from collections import Counter

MAX_SLOTS = 6


def _remaining_cost(target: int, avail: Counter, items: dict) -> int:
    """Gold needed to finish `target`. Owned parts are taken out of `avail`."""
    if avail[target] > 0:
        avail[target] -= 1
        return 0
    item = items[target]
    parts = [p for p in item["from"] if p in items]
    if not parts:
        return item["total"]
    return item["base"] + sum(_remaining_cost(p, avail, items) for p in parts)


def _buy_toward(target: int, avail: Counter, wallet: dict, out: list, items: dict, goal: str) -> bool:
    """Buy `target` if affordable, otherwise its most expensive affordable parts.

    Returns True when `target` ends up in hand.
    """
    if avail[target] > 0:
        avail[target] -= 1
        return True
    trial = avail.copy()
    cost = _remaining_cost(target, trial, items)
    consumed = sum(avail.values()) - sum(trial.values())   # owned parts this purchase uses up
    if cost <= wallet["gold"] and wallet["slots"] + consumed >= 1:
        avail.clear()
        avail.update(trial)
        wallet["gold"] -= cost
        wallet["slots"] += consumed - 1
        out.append({"id": target, "name": items[target]["name"], "cost": cost, "toward": goal})
        return True
    for part in sorted((p for p in items[target]["from"] if p in items), key=lambda p: -items[p]["total"]):
        _buy_toward(part, avail, wallet, out, items, goal)
    return False


def plan(build_ids: list, inventory_ids: list, gold: float, items: dict) -> dict:
    """Work out what to buy right now.

    build_ids: finished items in the order to complete them.
    inventory_ids: one id per occupied inventory slot.

    Returns:
      purchases: [{id, name, cost, toward}] in the order to buy them
      spend, left: gold used and gold remaining afterwards
      statuses: one of "done" | "buy" | "next" | "todo" per build_ids entry
      next: {id, name, remaining, short} for the first item that cannot be finished yet, else None
    """
    avail = Counter(inventory_ids)
    for iid in inventory_ids:
        base = (items.get(iid) or {}).get("upgrade_of")
        if base:                      # an upgraded item (for example Muramana) satisfies its base item
            avail[base] += 1
    wallet = {"gold": int(gold), "slots": MAX_SLOTS - len(inventory_ids)}
    purchases, statuses, nxt = [], [], None

    for target in build_ids:
        if target not in items or nxt is not None:
            statuses.append("todo")
            continue
        if avail[target] > 0:
            avail[target] -= 1
            statuses.append("done")
            continue
        cost_before = _remaining_cost(target, avail.copy(), items)
        bought_before = len(purchases)
        if _buy_toward(target, avail, wallet, purchases, items, items[target]["name"]):
            statuses.append("buy")
            continue
        remaining = cost_before - sum(p["cost"] for p in purchases[bought_before:])
        nxt = {"id": target, "name": items[target]["name"], "remaining": remaining,
               "short": max(0, remaining - wallet["gold"])}
        statuses.append("next")

    return {
        "purchases": purchases,
        "spend": sum(p["cost"] for p in purchases),
        "left": wallet["gold"],
        "statuses": statuses,
        "next": nxt,
    }
