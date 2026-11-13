"""What an item is worth to the player in a fight, worked out by a program from their real stats.

Claude answers a plan in about ten seconds. In that time it does not multiply. Asked for a
front-line champion's next item it reached for the items it knows by name, and in 35 recorded
matches it never listed Unending Despair, which heals for 2.5 times 3% of the holder's bonus
health for every enemy near them, every four seconds. On a Cho'Gath with 6,900 health and
three enemies in reach that is about 850 health every four seconds, worth more than twice any
other defensive item. The plan listed Force of Nature.

The earlier figure in the request ("how much more damage you could take with each item")
counted health, armor and magic resist and nothing else, so the items whose worth is in their
effect looked ordinary. This module counts the effect as well, for the items a front-line
champion buys.

The fight is a model, and its assumptions are the constants below and the numbers passed in
from the match: how the damage aimed at the player divides, how many enemies fight with basic
attacks, whether they build critical strikes, how much magic resist they have. The enemy is
taken to hit hard enough to kill the player in FIGHT_SECONDS as they stand now. An item then
changes their health, how much gets through, and how much they heal, and the model says how
long they last with it. Run on five real moments, the order at the top moved with the
assumptions (Unending Despair against Kaenic Rookern on a Malphite with little health) and the
bottom did not: Thornmail came last or next to last every time, and the item the coach had
named next was in the lower half every time.

The numbers of each effect are written into the formulas. EFFECTS pairs each item with the
phrases its catalog text must still contain, and a test checks them, so a patch that changes
an item is noticed. What is not counted is said in the request: effects that help teammates,
Thornmail's cut to enemy healing, and anything behind an item's button.
"""
from __future__ import annotations

FIGHT_SECONDS = 12.0      # how long the player now lasts under attack; sets how hard the enemy is taken to hit
FAR, NEAR = 3, 2          # enemy champions within 650 units (Unending Despair) and within 325 (Sunfire Aegis)
ATTACKS = 0.7             # basic attacks a second landing on the player, per enemy who fights with attacks
ATTACK_PART = 0.7         # share of an attacker's physical damage that is basic attacks
JAKSHO_AFTER, STEADFAST_AFTER = 5.0, 4.0    # seconds into a fight before Jak'Sho and Force of Nature reach full effect
CHARGED_ATTACKS = 2       # Heartsteel attacks landed in one fight
MOST = 3.0                # a gain is capped here: past it the model says only "you outlast the fight"

# Item -> phrases its catalog text must contain for the formula below to be right (checked by a test).
EFFECTS = {
    "Unending Despair": ("Every 4 seconds", "3% of your bonus health", "250%", "650 units"),
    "Sunfire Aegis": ("20 + 1% bonus health", "every second", "325"),
    "Hollow Radiance": ("15 + 1% bonus health", "every second", "325"),
    "Thornmail": ("20 + 10% bonus armor", "basic attack"),
    "Randuin's Omen": ("critical strikes by 30%",),
    "Frozen Heart": ("attack speed", "by 20%"),
    "Jak'Sho, The Protean": ("up to 5 times", "by 30%"),
    "Force of Nature": ("70 bonus magic resistance",),
    "Kaenic Rookern": ("15% of maximum health", "magic damage"),
    "Warmog's Armor": ("12% bonus health from items",),
    "Heartsteel": ("70 + 6% maximum health", "8% of that amount"),
    "Spirit Visage": ("healing and shielding received", "by 25%"),
    "Sterak's Gage": ("60% of bonus health", "below 30%"),
}


def fight(sd, state: dict, share: float) -> dict | None:
    """The fight the player is in, from the match: None without the player's real stats.

    share: the physical share of the damage that gets through to the player (threats.mix).
    Returns the numbers the formulas need: the player's health and resistances and how much of
    each is bonus, the physical part of the damage aimed at them, the enemies in reach, how
    many fight with attacks and how much of their damage is critical strikes, the enemies'
    magic resist and armor, and `pressure`, the damage a second aimed at the player.
    """
    from .live import estimate_stats                 # imported here: live reads the game, this module only computes
    from .threats import physical_share
    me = state.get("me") or {}
    stats = me.get("stats") or {}
    health, armor, resist = stats.get("maxHealth"), stats.get("armor"), stats.get("magicResist")
    if not health or armor is None or resist is None or not state.get("enemies"):
        return None
    alone = estimate_stats((sd.champions.get(me.get("champ_id")) or {}).get("base"), me.get("level") or 1, [], sd) or {}
    a, m = 100 / (100 + armor), 100 / (100 + resist)
    aimed = share * m / (a * (1 - share) + share * m)          # physical part before the player's resistances
    enemies = state["enemies"]
    attackers = [p for p in enemies if physical_share(sd, p) >= 0.65]
    crit = []
    for p in attackers:
        chance = min(1.0, sum((sd.items.get(i["id"]) or {}).get("stats", {}).get("Critical Strike Chance%", 0) for i in p["items"]) / 100)
        crit.append(chance * 1.75 / (1 + 0.75 * chance))          # share of their attack damage that is the critical part
    est = [p.get("est") or {} for p in enemies]
    mean = lambda key, default: (sum(e.get(key, default) for e in est) / len(est)) if est else default
    owned = [sd.items.get(i["id"]) or {} for i in me.get("items") or []]
    return {
        "health": health, "armor": armor, "resist": resist,
        "bonus_health": max(0.0, health - alone.get("health", health)),
        "bonus_armor": max(0.0, armor - alone.get("armor", armor)),
        "bonus_resist": max(0.0, resist - alone.get("magic resist", resist)),
        "item_health": sum(it.get("stats", {}).get("Health", 0) for it in owned),
        "owned": {it.get("name") for it in owned},
        "aimed": aimed, "far": min(FAR, len(enemies)), "near": min(NEAR, len(enemies)),
        "attackers": len(attackers),
        "crit_part": ATTACK_PART * (sum(crit) / len(crit)) if crit else 0.0,
        "enemy_resist": max(30.0, mean("magic resist", 50)), "enemy_armor": max(30.0, mean("armor", 60)),
        "pressure": health / (FIGHT_SECONDS * (aimed * a + (1 - aimed) * m)),
    }


def worth(item: dict, f: dict) -> dict:
    """One item in that fight: {name, gold, gain, lasts, heals, dealt, grows, counted}.

    gain: how much longer the player lasts, as a fraction (0.4 is 40% longer). lasts: seconds.
    heals: health a second from the item's effect. dealt: damage the effect deals in the fight.
    grows: health gained for good per fight. counted: the effect that was counted, in words,
    or "" when only the item's health, armor and magic resist were.
    """
    return {"name": item["name"], **together([item], f)}


def together(items: list, f: dict) -> dict:
    """Several items bought together in that fight: {names, gold, gain, lasts, heals, dealt, grows, counted}.

    The same arithmetic as for one item, with the items' stats added up first, because the
    effects feed on each other: Jak'Sho raises the resistances the other items gave, Unending
    Despair heals from the health they gave, Spirit Visage raises that heal. An empty list is
    the player as they stand, a gain of zero.
    """
    names = [it["name"] for it in items]
    has = lambda name: name in names
    total = lambda key: sum(it["stats"].get(key, 0) for it in items)
    health = f["health"] + total("Health")
    if has("Warmog's Armor"):
        health += 0.12 * (f["item_health"] + total("Health"))
    elif "Warmog's Armor" in f["owned"]:
        health += 0.12 * total("Health")
    armor, resist = f["armor"] + total("Armor"), f["resist"] + total("Magic Resist")
    bonus_health = f["bonus_health"] + (health - f["health"])
    bonus_armor, bonus_resist = f["bonus_armor"] + total("Armor"), f["bonus_resist"] + total("Magic Resist")
    hits = 100 / (100 + f["enemy_resist"])                     # what the enemies take of the effect's magic damage
    physical_cut, heals, per_second, burst, shield, grows, counted = 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, []
    if has("Force of Nature") and f["aimed"] < 0.9:
        steadfast = 70 * max(0.0, 1 - STEADFAST_AFTER / FIGHT_SECONDS)
        resist, bonus_resist = resist + steadfast, bonus_resist + steadfast
        counted.append("70 more magic resist once eight magic hits have landed")
    if has("Jak'Sho, The Protean"):
        part = max(0.0, 1 - JAKSHO_AFTER / FIGHT_SECONDS)
        armor, resist = armor + 0.30 * bonus_armor * part, resist + 0.30 * bonus_resist * part
        counted.append("30% more of your bonus resistances after five seconds")
    if has("Randuin's Omen") and f["crit_part"]:
        physical_cut *= 1 - 0.30 * f["crit_part"]
        counted.append("30% off the critical strikes of their attackers")
    if has("Frozen Heart") and f["attackers"]:
        physical_cut *= 1 - 0.20 * ATTACK_PART
        counted.append("attackers near you attack 20% slower")
    despair = 0.03 * bonus_health * f["far"] * hits            # one tick of Unending Despair, every four seconds
    if has("Unending Despair"):
        more = 1.25 if has("Spirit Visage") or "Spirit Visage" in f["owned"] else 1.0
        per_second, heals = per_second + despair / 4, heals + more * 2.5 * despair / 4
        counted.append(f"heals about {round(more * 2.5 * despair / 10) * 10} every 4 seconds with {f['far']} enemies near")
    elif has("Spirit Visage") and "Unending Despair" in f["owned"]:
        heals += 0.25 * 2.5 * despair / 4
        counted.append("25% more from your Unending Despair")
    burners = [n for n in ("Sunfire Aegis", "Hollow Radiance") if has(n)]
    if burners:                                                # one Immolate works at a time: the stronger
        per_second += ((20 if burners[0] == "Sunfire Aegis" else 15) + 0.01 * bonus_health) * f["near"] * hits
        counted.append(f"burns {f['near']} enemies beside you")
    if has("Thornmail"):
        per_second += (20 + 0.10 * bonus_armor) * ATTACKS * f["attackers"] * hits
        counted.append("hurts enemies who attack you; its cut to their healing is not counted")
    if has("Heartsteel"):
        charged = 70 + 0.06 * health
        burst, grows = CHARGED_ATTACKS * charged * 100 / (100 + f["enemy_armor"]), CHARGED_ATTACKS * 0.08 * charged
        counted.append(f"about {round(grows)} health for good each fight")
    if has("Kaenic Rookern"):
        counted.append("a magic shield of 15% of your health, counted as up when the fight starts")
    if has("Sterak's Gage"):
        shield = 0.6 * 0.60 * bonus_health                      # decays over 4.5 seconds: about 60% of it is used
        counted.append("its shield when you drop below 30% health")
    if has("Warmog's Armor"):
        counted.append("12% more health from items; between fights it restores 3% of your health a second")
    through_physical = f["aimed"] * 100 / (100 + armor) * physical_cut
    through_magic = (1 - f["aimed"]) * 100 / (100 + resist)

    def lasts_with(extra_shield: float) -> float:
        drain = f["pressure"] * (through_physical + through_magic) - heals
        return (health + extra_shield) / drain if drain > 0 else FIGHT_SECONDS * (1 + MOST)

    lasts = lasts_with(shield)
    if has("Kaenic Rookern"):                                 # the shield takes magic damage only
        magic_taken = f["pressure"] * through_magic * lasts
        lasts = lasts_with(shield + min(0.15 * health, magic_taken))
    lasts = min(lasts, FIGHT_SECONDS * (1 + MOST))
    return {"names": names, "gold": sum(it["total"] for it in items), "gain": lasts / FIGHT_SECONDS - 1, "lasts": lasts,
            "heals": heals, "dealt": per_second * min(lasts, 30.0) + burst, "grows": grows, "counted": "; ".join(counted)}


def table(sd, state: dict, share: float, candidates: list) -> list:
    """Every candidate item in the fight, best survival for its gold first. Empty without the player's stats."""
    f = fight(sd, state, share)
    if f is None:
        return []
    rows = [worth(item, f) for item in candidates]
    rows.sort(key=lambda r: -r["gain"] / max(1, r["gold"]))
    return rows
