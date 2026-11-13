"""Arithmetic on the player's real numbers, for Claude to ask for while it plans (see tools.py).

Claude answers a plan in about ten seconds and does not multiply in that time. Given item
text with numbers it still reached for the items it knew by name: critical strikes for a
Garen whose spin scales with attack speed, Rylai's for a Zilean who gives up a third of his
damage for it, Force of Nature where Unending Despair was worth twice as much. The numbers
were in front of it; working them out was the missing step. itemworth.py did that step for
one question, a front-line champion's next defensive item, and the plans changed. This
module does it for the rest, as calculations Claude can call with the builds it is weighing.

Four calculations, each on the player's stats as the game reports them plus the items of a
candidate build:

- sheet: the stats a build would give. Everything else starts here.
- attacks: basic attacks on one target for a few seconds, with on-hit item effects.
- abilities: every number of the champion's kit at the build's stats, after resistances.
- evaluate: a formula Claude writes, for a rule no model here covers.

Survival of a set of items is in itemworth.together.

What a calculation does not count is part of its answer, and the tool text says it every
time. The limits that matter most:

- A hypothetical build is the real stats plus the stat lines of the added items, and the
  item effects named in EFFECTS. Augments the player holds are in the real stats only as far
  as the game adds them to a stat. What an augment does beyond stats is not modelled.
- Enemy stats are estimates from their champion, level and items (live.estimate_stats), so
  they are a floor: runes and augments add to them.
- Where the data gives no number for an effect (Stormrazor's charged attack), it is listed
  as not counted, never guessed.
- Item numbers are the standard game's. This mode changes a few.

Each formula below is pinned to the words of the item text it was written from (EFFECTS),
and a test checks the words are still there, so a patch that changes an item is noticed.
"""
from __future__ import annotations

import ast
import math
import re

from .static_data import catalog_family_for, norm

ATTACK_SECONDS = 6.0      # how long the basic-attack comparison runs
BESIDE = 2                # other enemies standing by the target, for bolts, cleaves and chains
SPELLBLADE_EVERY = 3.0    # seconds between abilities that charge an "after using an ability" attack
SPEED_CAP = 2.5           # attacks a second in the standard game; a player already above it keeps their own figure
CRIT_DAMAGE = 2.0         # what the game reported for every champion in 37 recorded matches, before items
MAX_BUILDS = 4

# Item -> words its catalog text must contain for the formulas in this module to be right (checked by a test).
EFFECTS = {
    "Rabadon's Deathcap": ("ability power by 30%",),
    "Sterak's Gage": ("45% base AD",),
    "Overlord's Bloodmail": ("2.5% bonus health",),
    "Riftmaker": ("ability power equal to 2% bonus health", "up to 4 times for a total of 8%"),
    "Warmog's Armor": ("12% bonus health from items",),
    "Yun Tal Wildarrows": ("capped at 25% critical strike chance", "30% bonus attack speed for 6 seconds"),
    "Blade of The Ruined King": ("9% (melee) / 6% (ranged) of the target's current health",),
    "Wit's End": ("45 bonus magic damage on-hit",),
    "Nashor's Tooth": ("15 + 15% AP bonus magic damage on-hit",),
    "Guinsoo's Rageblade": ("30 bonus magic damage on-hit", "8% bonus attack speed", "up to 4 times", "Phantom Hit"),
    "Terminus": ("30 bonus magic damage on-hit", "10% armor penetration and magic penetration", "30% resistances penetration"),
    "Titanic Hydra": ("1% (melee) / 0.5% (ranged) maximum health bonus physical damage",
                      "3% (melee) / 1.5% (ranged) maximum health physical damage to other enemies"),
    "Runaan's Hurricane": ("up to 2 enemies", "55% AD physical damage", "apply on-hit effects"),
    "Statikk Shiv": ("next 3 basic attacks", "60 bonus magic damage", "up to 5 targets"),
    "Rapid Firecannon": ("40 bonus magic damage on-hit",),
    "Voltaic Cyclosword": ("100 bonus physical damage on-hit",),
    "Trinity Force": ("200% base AD bonus physical damage on-hit", "1.5 second cooldown"),
    "Iceborn Gauntlet": ("150% base AD bonus physical damage on-hit", "1.5 second cooldown"),
    "Lich Bane": ("75% base AD + 40% AP bonus magic damage on-hit", "1.5 second cooldown"),
    "Dusk and Dawn": ("75% base AD + 10% AP bonus magic damage on-hit", "applies on-hit effects to the target again"),
    "Essence Reaver": ("125% base AD + 0 to 50 based on critical strike chance", "1.5 second cooldown"),
    "Black Cleaver": ("6% armor reduction, up to 30% at 5 stacks",),
    "Ravenous Hydra": ("40% AD (melee) / 20% AD (ranged) physical damage to other enemies",),
    "Stridebreaker": ("40% AD (melee) / 20% AD (ranged) physical damage to other enemies",),
    "Profane Hydra": ("40% AD (melee) / 20% AD (ranged) physical damage to other enemies",),
    "Heartsteel": ("70 + 6% maximum health bonus physical damage on-hit",),
    "Hullbreaker": ("stacking up to 5 times", "120% (melee) / 84% (ranged) base AD", "5% (melee) / 3.5% (ranged) maximum health"),
    "Dead Man's Plate": ("0 to 40 + 0 to 100% base AD bonus physical damage on-hit",),
    "Kraken Slayer": ("up to 2 stacks", "150 to 200 (melee) / 120 to 160 (ranged) bonus physical damage on-hit",
                      "increased by 0 to 75% (by target's missing health, 0 to 100)"),
    "Lord Dominik's Regards": ("0 to 15% (by target's bonus health, 0 to 1500)",),
    "Sundered Sky": ("critically strike for 60% bonus damage",),
    "Eclipse": ("6% (melee) / 4% (ranged) of target's maximum health",),
    "The Collector": ("below 5% of their maximum health, execute",),
    "Liandry's Torment": ("1% of the target's maximum health magic damage every 0.5 seconds over 3 seconds",
                          "up to 3 times for a total of 6%"),
    "Blackfire Torch": ("for a total of 60 + 6% AP", "increase your ability power by 4%"),
    "Luden's Echo": ("75 + 5% AP bonus magic damage",),
    "Stormsurge": ("25% of their maximum health within 2.5 seconds", "125 + 10% AP magic damage"),
    "Malignance": ("20 ultimate haste", "15 + 1.25% AP magic damage every 0.25 seconds", "magic resistance by 10"),
    "Shadowflame": ("120% damage against enemies below 40% maximum health",),
    "Spear of Shojin": ("25 basic ability haste", "total increase of 12%"),
    "Horizon Focus": ("600 or more units away", "by 10%"),
    "Bloodletter's Curse": ("7.5% magic resistance reduction, up to 30% at 4 stacks",),
    "Abyssal Mask": ("12% increased magic damage",),
    "Imperial Mandate": ("7% Vulnerable for 4 seconds",),
    "Experimental Hexplate": ("30 ultimate haste",),
    "Fiendhunter Bolts": ("30 ultimate haste",),
    "Hextech Rocketbelt": ("100 + 10% AP magic damage",),
    "Hextech Gunblade": ("175 to 253 + 30% AP magic damage",),
}
CLEAVERS = ("Ravenous Hydra", "Stridebreaker", "Profane Hydra")
SPELLBLADES = ("Trinity Force", "Lich Bane", "Iceborn Gauntlet", "Essence Reaver", "Dusk and Dawn")   # one works at a time
ULT_HASTE = {"Malignance": 20, "Experimental Hexplate": 30, "Fiendhunter Bolts": 30}

# What an item does to basic attacks that the attack model leaves out, said in the answer when the item is in a build.
ATTACKS_LEFT_OUT = {
    "Stormrazor": "Stormrazor's bonus magic damage on a charged attack (no number in the data)",
    "Hexoptics C44": "Hexoptics C44 deals up to 10% more with attacks from far away",
    "Atma's Reckoning": "Atma's Reckoning gains up to 30% critical strike chance from bonus health",
    "Fiendhunter Bolts": "Fiendhunter Bolts empowers three attacks after the ultimate",
    "Experimental Hexplate": "Experimental Hexplate gives 50% attack speed for 8 seconds after the ultimate",
    "Navori Flickerblade": "Navori Flickerblade shortens basic ability cooldowns by 15% with each attack",
    "Hubris": "Hubris gains attack damage from kills",
    "Umbral Glaive": "Umbral Glaive's true damage on an attack from out of sight",
    "Manamune": "Manamune's attack damage from mana",
    "Ardent Censer": "Ardent Censer's attack speed and on-hit damage after healing or shielding an ally",
}
ABILITIES_LEFT_OUT = {
    "Blackfire Torch": "Blackfire Torch adds 4% ability power for each enemy it is burning",
    "Archangel's Staff": "Archangel's Staff gains ability power from mana",
    "Actualizer": "Actualizer's button (more ability damage for 8 seconds)",
    "Navori Flickerblade": "Navori Flickerblade shortens basic ability cooldowns by 15% with each attack",
    "Rite of Ruin": "Rite of Ruin's critical strike chance from casting",
    "Axiom Arc": "Axiom Arc refunds part of the ultimate's cooldown on a takedown",
    "Endless Hunger": "Endless Hunger's ability haste from bonus attack damage",
}


def _growth(level: int) -> float:
    n = max(0, level - 1)
    return n * (0.7025 + 0.0175 * n)             # the game's curve for stats that grow with level


def _base(base: dict, level: int) -> dict:
    """A champion's own stats at one level, before items."""
    g = _growth(level)
    return {"health": base.get("hp", 0) + base.get("hpperlevel", 0) * g,
            "ad": base.get("attackdamage", 0) + base.get("attackdamageperlevel", 0) * g,
            "armor": base.get("armor", 0) + base.get("armorperlevel", 0) * g,
            "resist": base.get("spellblock", 0) + base.get("spellblockperlevel", 0) * g,
            "speed_growth": base.get("attackspeedperlevel", 0) * g}      # percent of bonus attack speed from levels


def find_item(sd, name: str, family: str = "std"):
    """An item by the name Claude wrote: the exact name, else the one finished item whose name contains it."""
    exact = sd.find_item(name, family)
    if exact or len(norm(name)) < 4:
        return exact
    close = [it for it in sd.catalog(family) if norm(name) in norm(it["name"]) or norm(it["name"]) in norm(name)]
    return close[0] if len(close) == 1 else None


def sheet(sd, state: dict, add=(), extra: dict | None = None, level: int | None = None) -> dict:
    """The stats the player would have with the items in `add` on top of what they hold.

    add: item names. extra: stats added on top of the items, for an augment or stacks the
    game's figures do not show: attack_damage, ability_power, health, armor, magic_resist,
    attack_speed_percent, crit_chance_percent, ability_haste. level: the champion level to
    work at, the current one when left out.

    During a match the start is the game's own figures for the player, which hold their
    runes, augments and stacks as far as those are stats. Before the match loads there are
    none, and the start is the champion alone plus the stat lines of the items held.

    Returns the stats (health, armor, resist, ad, ap, speed in attacks a second, crit from 0
    to 1, crit_damage as a multiple, haste, the two penetrations as the share of the
    resistance left and a flat amount), the parts some formulas need (base_ad, bonus_ad,
    bonus_health, bonus_armor, bonus_resist, bonus_speed in percent), `names` of every item
    held or added, `added`, `unknown` names, and `real`: whether the game's figures were used.
    """
    me = state["me"]
    champ = sd.champions.get(me.get("champ_id")) or {}
    base, kit = champ.get("base") or {}, (getattr(sd, "kits", None) or {}).get(me.get("champ_id")) or {}
    family = catalog_family_for(state.get("item_ids") or [])
    now_level = me.get("level") or 1
    level = max(1, min(30, int(level or now_level)))
    at, now = _base(base, level), _base(base, now_level)
    stats, more = me.get("stats") or {}, me.get("more") or {}
    ratio = kit.get("as_ratio") or base.get("attackspeed") or 0.625
    base_speed = base.get("attackspeed") or ratio
    held = [sd.items[i["id"]] for i in me.get("items") or [] if i.get("id") in sd.items]
    held_names = {it["name"] for it in held}
    real = bool(stats.get("maxHealth"))
    if real:
        s = {"health": stats["maxHealth"] + (at["health"] - now["health"]),
             "ad": stats.get("attackDamage", now["ad"]) + (at["ad"] - now["ad"]),
             "armor": stats.get("armor", now["armor"]) + (at["armor"] - now["armor"]),
             "resist": stats.get("magicResist", now["resist"]) + (at["resist"] - now["resist"]),
             "ap": stats.get("abilityPower", 0.0) / (1.3 if "Rabadon's Deathcap" in held_names else 1.0),
             "haste": stats.get("abilityHaste", 0.0),
             "speed": (stats.get("attackSpeed") or base_speed) + ratio * (at["speed_growth"] - now["speed_growth"]) / 100,
             "crit": stats.get("critChance", 0.0), "crit_damage": more.get("crit_damage", CRIT_DAMAGE),
             "armor_left": more.get("armor_left", 1.0), "lethality": more.get("lethality", 0.0),
             "resist_left": more.get("resist_left", 1.0), "magic_pen": more.get("magic_pen", 0.0), "mana": more.get("mana", 0.0)}
        fresh = []                               # items whose stat lines are still to be added
    else:
        s = {"health": at["health"], "ad": at["ad"], "armor": at["armor"], "resist": at["resist"], "ap": 0.0, "haste": 0.0,
             "speed": base_speed + ratio * at["speed_growth"] / 100, "crit": 0.0, "crit_damage": CRIT_DAMAGE,
             "armor_left": 1.0, "lethality": 0.0, "resist_left": 1.0, "magic_pen": 0.0, "mana": 0.0}
        fresh = list(held)
    cap = max(SPEED_CAP, s["speed"])
    before = dict(s)
    added, unknown = [], []
    for name in add:
        item = find_item(sd, str(name), family)
        if item is None:
            unknown.append(str(name))
        elif item["name"] not in held_names and item["name"] not in {a["name"] for a in added}:
            added.append(item)
    fresh += added
    for it in fresh:
        st = it["stats"]
        s["health"] += st.get("Health", 0)
        s["armor"] += st.get("Armor", 0)
        s["resist"] += st.get("Magic Resist", 0)
        s["ad"] += st.get("Attack Damage", 0)
        s["ap"] += st.get("Ability Power", 0)
        s["haste"] += st.get("Ability Haste", 0)
        s["mana"] += st.get("Mana", 0)
        s["lethality"] += st.get("Lethality", 0)
        s["magic_pen"] += st.get("Magic Penetration", 0)
        s["speed"] += ratio * st.get("Attack Speed%", 0) / 100
        s["crit"] += st.get("Critical Strike Chance%", 0) / 100
        s["crit_damage"] += st.get("Critical Strike Damage%", 0) / 100
        s["armor_left"] *= 1 - st.get("Armor Penetration%", 0) / 100
        s["resist_left"] *= 1 - st.get("Magic Penetration%", 0) / 100
    for key, into, scale in (("attack_damage", "ad", 1), ("ability_power", "ap", 1), ("health", "health", 1), ("armor", "armor", 1),
                             ("magic_resist", "resist", 1), ("ability_haste", "haste", 1),
                             ("attack_speed_percent", "speed", ratio / 100), ("crit_chance_percent", "crit", 0.01)):
        value = (extra or {}).get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            s[into] += value * scale
    names = held_names | {it["name"] for it in added}
    new = {it["name"] for it in fresh}
    # Effects that turn one stat into another, in the order they feed each other.
    if "Warmog's Armor" in new:
        s["health"] += 0.12 * sum(it["stats"].get("Health", 0) for it in held + added)
    elif "Warmog's Armor" in names:
        s["health"] += 0.12 * sum(it["stats"].get("Health", 0) for it in fresh)
    gained = s["health"] - before["health"]
    bonus_health = max(0.0, s["health"] - at["health"])
    if "Sterak's Gage" in new:
        s["ad"] += 0.45 * at["ad"]
    if "Overlord's Bloodmail" in names:
        s["ad"] += 0.025 * (bonus_health if "Overlord's Bloodmail" in new else gained)
    if "Riftmaker" in names:
        s["ap"] += 0.02 * (bonus_health if "Riftmaker" in new else gained)
    if "Yun Tal Wildarrows" in new:
        s["crit"] += 0.25                         # at full stacks
    if "Rabadon's Deathcap" in names:
        s["ap"] *= 1.3
    s["crit"] = max(0.0, min(1.0, s["crit"]))
    s["speed"] = max(0.1, min(cap, s["speed"]))
    melee = not kit["ranged"] if "ranged" in kit else (more.get("range") or base.get("attackrange") or 550) <= 250
    s.update(level=level, real=real, melee=melee, names=names, added=[it["name"] for it in added], unknown=unknown,
             gold=sum(it["total"] for it in added), as_ratio=ratio,
             base_ad=at["ad"], bonus_ad=max(0.0, s["ad"] - at["ad"]), base_health=at["health"], bonus_health=bonus_health,
             bonus_armor=max(0.0, s["armor"] - at["armor"]), bonus_resist=max(0.0, s["resist"] - at["resist"]),
             bonus_speed=max(0.0, (s["speed"] - base_speed) / ratio * 100),
             ult_haste=sum(v for k, v in ULT_HASTE.items() if k in names),
             basic_haste=25 if "Spear of Shojin" in names else 0)
    return s


def target(sd, state: dict, name: str | None = None, level: int | None = None) -> dict:
    """The enemy a build is measured against: {label, health, bonus_health, armor, resist, missed}.

    name: an enemy champion in the match. Without one, or with one that is not there, the
    enemy team's average. level: the level the player's build is worked out at. An enemy
    below it is taken to that level with the items they hold now, so a build for later is
    not measured against the enemies of the first minute. The figures are estimates from each
    enemy's champion, level and items, so real values are somewhat higher. With no enemy
    known, a stand-in.
    """
    from .live import estimate_stats                 # imported here: live reads the game, this module only computes
    enemies = [p for p in state.get("enemies") or [] if p.get("est")]
    wanted = norm(name or "")
    one = next((p for p in enemies if wanted and wanted in (norm(p["champion"]), norm(p.get("champ_id") or ""))), None)
    missed = bool(wanted) and one is None and wanted not in ("average", "team", "enemyteam", "all")
    rows = [one] if one else enemies
    if not rows:
        return {"label": "a stand-in enemy (none is known yet)", "health": 2000.0, "bonus_health": 600.0, "armor": 60.0,
                "resist": 45.0, "missed": missed}
    base = lambda p: (sd.champions.get(p.get("champ_id")) or {}).get("base") or {}
    at = lambda p: max(p.get("level") or 1, level or 1)
    later = any(at(p) > (p.get("level") or 1) for p in rows)
    est = lambda p: (estimate_stats(base(p), at(p), p.get("items") or [], sd) if at(p) > (p.get("level") or 1) else None) or p["est"]
    mean = lambda key: sum(est(p).get(key, 0) for p in rows) / len(rows)
    label = (f"{one['champion']} at level {at(one)}" if one else "the enemy team on average"
             + (f", taken to level {level}" if later else ""))
    if later:
        label += " with the items they hold now"
    return {"label": label, "health": float(mean("health")), "armor": float(mean("armor")), "resist": float(mean("magic resist")),
            "bonus_health": sum(max(0.0, est(p).get("health", 0) - _base(base(p), at(p))["health"]) for p in rows) / len(rows),
            "missed": missed}


def _through(s: dict, t: dict, cleaver: float = 0.0, dark: float = 0.0) -> tuple:
    """The share of physical and of magic damage that gets through the target's resistances with this build."""
    armor = max(0.0, t["armor"] * (1 - cleaver) * s["armor_left"] * (1 - dark) - s["lethality"])
    resist = max(0.0, t["resist"] * s["resist_left"] * (1 - dark) - s["magic_pen"])
    return 100 / (100 + armor), 100 / (100 + resist)


def attacks(s: dict, t: dict, seconds: float = ATTACK_SECONDS, beside: int = BESIDE) -> dict:
    """Basic attacks on one target for `seconds`, with the on-hit effects of the build's items.

    The first attack lands at once and the rest follow at the build's attack speed. Effects
    that build up start empty: Black Cleaver's armor cut, Terminus, Guinsoo's attack speed.
    An effect that needs an ability cast first (Trinity Force, Lich Bane) is counted on the
    first attack and then every SPELLBLADE_EVERY seconds. Nothing of the champion's own kit is
    counted beyond what its stats already show.

    Returns {rate, first, dealt, share, kills_in, others, counted}: attacks a second, the
    damage of the first plain attack, the damage on the target over the time, that as a share
    of its health, the second it dies or None, the damage each enemy beside it takes from
    bolts, cleaves and chains, and the effects counted, in words.
    """
    names, melee = s["names"], s["melee"]
    has = lambda name: name in names
    crit = 1 + s["crit"] * (s["crit_damage"] - 1)
    blade = next((n for n in SPELLBLADES if has(n)), None)
    ruined = (0.09 if melee else 0.06) if has("Blade of The Ruined King") else 0.0
    cleave = (0.40 if melee else 0.20) if any(has(n) for n in CLEAVERS) else 0.0
    spray = min(2, beside) if has("Runaan's Hurricane") else 0
    counted = [n for n in ("Blade of The Ruined King", "Kraken Slayer", "Wit's End", "Nashor's Tooth", "Guinsoo's Rageblade",
                           "Terminus", "Titanic Hydra", "Runaan's Hurricane", "Statikk Shiv", "Rapid Firecannon",
                           "Voltaic Cyclosword", "Black Cleaver", "Heartsteel", "Hullbreaker", "Dead Man's Plate", "Sundered Sky",
                           "Eclipse", "The Collector", "Lord Dominik's Regards", "Yun Tal Wildarrows") + CLEAVERS
               if has(n)] + ([blade] if blade else [])
    # Giant Slayer: 1% more damage for each 100 bonus health of the target, 15% at most.
    giant = 1 + min(0.15, t.get("bonus_health", 0.0) / 10000) if has("Lord Dominik's Regards") else 1.0
    kraken = (150 + 5 * max(0, min(10, s["level"] - 8))) * (1.0 if melee else 0.8) if has("Kraken Slayer") else 0.0
    left = t["health"]
    clock, n, dealt, others, first, kills_in, charge_at, fed = 0.0, 0, 0.0, 0.0, 0.0, None, 0.0, False
    while clock <= seconds + 1e-9 and n < 200:
        n += 1
        cleaver = min(0.30, 0.06 * (n - 1)) if has("Black Cleaver") else 0.0
        dark = min(0.30, 0.10 * ((n - 1) // 2)) if has("Terminus") else 0.0
        physical_through, magic_through = _through(s, t, cleaver, dark)
        physical, magic = s["ad"] * crit, 0.0
        if n == 1 and has("Sundered Sky"):
            physical = s["ad"] * ((1 - s["crit"]) * 1.6 + s["crit"] * max(1.6, s["crit_damage"]))
        plain = physical * physical_through
        # Effects that land with every attack, and again on a bolt or a second hit.
        hit_physical = ruined * max(0.0, left) + ((0.01 if melee else 0.005) * s["health"] if has("Titanic Hydra") else 0.0)
        hit_magic = ((45 if has("Wit's End") else 0) + (15 + 0.15 * s["ap"] if has("Nashor's Tooth") else 0)
                     + (30 if has("Guinsoo's Rageblade") else 0) + (30 if has("Terminus") else 0))
        twice = has("Guinsoo's Rageblade") and n > 4 and (n - 4) % 3 == 0          # a Phantom Hit, at full stacks
        if has("Statikk Shiv") and n <= 3:
            magic += 60
            others += 60 * min(4, beside) * magic_through / max(1, beside)
        if has("Rapid Firecannon") and n == 1:
            magic += 40
        if has("Voltaic Cyclosword") and n == 1:
            physical += 100
        if has("Dead Man's Plate") and n == 1:
            physical += 40 + s["base_ad"]
        if has("Heartsteel") and not fed and clock >= 3.0:                         # three seconds near the target to charge
            physical, fed = physical + 70 + 0.06 * s["health"], True
        if has("Hullbreaker") and n % 5 == 0:
            physical += (1.2 if melee else 0.84) * s["base_ad"] + (0.05 if melee else 0.035) * s["health"]
        if has("Eclipse") and n == 2:
            physical += (0.06 if melee else 0.04) * t["health"]
        if kraken and n % 3 == 0:                                                  # up to 75% more as the target loses health
            physical += kraken * (1 + 0.75 * max(0.0, min(1.0, 1 - left / t["health"])))
        if blade and clock >= charge_at - 1e-9:
            charge_at = clock + max(1.5, SPELLBLADE_EVERY)
            if blade == "Trinity Force":
                physical += 2.0 * s["base_ad"]
            elif blade == "Iceborn Gauntlet":
                physical += 1.5 * s["base_ad"]
            elif blade == "Essence Reaver":
                physical += 1.25 * s["base_ad"] + 50 * s["crit"]
            elif blade == "Lich Bane":
                magic += 0.75 * s["base_ad"] + 0.40 * s["ap"]
            else:                                                                  # Dusk and Dawn
                magic += 0.75 * s["base_ad"] + 0.10 * s["ap"]
                twice = True
        hit = giant * (physical * physical_through + magic * magic_through
                       + (hit_physical * physical_through + hit_magic * magic_through) * (2 if twice else 1))
        if n == 1:
            first = giant * plain
        dealt += hit
        left -= hit
        each = cleave * s["ad"] * physical_through                                  # what one enemy beside the target takes
        if has("Titanic Hydra"):
            each += (0.03 if melee else 0.015) * s["health"] * physical_through
        if spray:
            bolt = ((0.55 * s["ad"] * crit + ruined * t["health"]
                     + ((0.01 if melee else 0.005) * s["health"] if has("Titanic Hydra") else 0.0)) * physical_through
                    + hit_magic * magic_through)
            each += bolt * spray / max(1, beside)
        others += giant * each
        if kills_in is None and left <= (0.05 * t["health"] if has("The Collector") else 0.0):
            kills_in = clock
        speed = s["speed"]
        if has("Yun Tal Wildarrows") and clock < 6.0:
            speed += s["as_ratio"] * 0.30
        if has("Guinsoo's Rageblade"):
            speed += s["as_ratio"] * 0.08 * min(4, n)
        clock += 1 / max(0.1, min(max(SPEED_CAP, s["speed"]), speed))
    return {"rate": s["speed"], "first": first, "dealt": dealt, "share": dealt / t["health"] if t["health"] else 0.0,
            "kills_in": kills_in, "others": others if beside else 0.0, "counted": counted}


# ---- abilities ---------------------------------------------------------------

_SHOWN = re.compile(r"damage|heal|shield", re.I)
_SKIPPED = re.compile(r"minion|monster|non-champion|structure|turret|reduc|capped|attack damage|ability power|threshold|stored", re.I)
_OWN = {"ap": "ap", "bonus ad": "bonus_ad", "ad": "ad", "bonus health": "bonus_health", "maximum health": "health",
        "bonus armor": "bonus_armor", "armor": "armor", "bonus magic resistance": "bonus_resist", "magic resistance": "resist",
        "maximum mana": "mana"}
_OWN_UNIT = re.compile(r"% (?:of (?:his|her|its|their|(?!target)\w+'s) )?(?:of )?(" + "|".join(sorted(_OWN, key=len, reverse=True)) + ")")
_TARGET_UNIT = re.compile(r"%\s*((?:\(\+ [\d.]+% per 100 [a-z ]+\)\s*)*)of (?:the )?target's (maximum|current|missing) health")


def _term(value: float, unit: str, s: dict, t: dict) -> tuple:
    """One part of an ability's number: (amount, "") when it can be worked out, (None, words) when it cannot."""
    u = re.sub(r"\s+", " ", unit.strip().lower())
    if not u:
        return value, ""
    aimed = _TARGET_UNIT.fullmatch(u)
    if aimed:
        share = value
        for per, stat in re.findall(r"\(\+ ([\d.]+)% per 100 ([a-z ]+)\)", aimed.group(1)):
            if stat.strip() not in _OWN:
                return None, f"{value:g}{unit.strip()}"
            share += float(per) * s[_OWN[stat.strip()]] / 100
        if aimed.group(2) == "maximum":
            return share / 100 * t["health"], ""
        return None, f"{share:.3g}% of the target's {aimed.group(2)} health"
    own = _OWN_UNIT.fullmatch(u)
    if own:
        return value / 100 * s[_OWN[own.group(1)]], ""
    return None, f"{value:g}{'' if unit.strip().startswith('%') else ' '}{unit.strip()}"


def assumed_ranks(level: int) -> dict:
    """Ability ranks for a level the player has not reached: the ultimate by level, the rest spread evenly."""
    ult = (level >= 6) + (level >= 11) + (level >= 16)
    basic = min(5, max(1, round((level - ult) / 3)))
    return {"Q": basic, "W": basic, "E": basic, "R": ult}


def abilities(sd, champ_id: str, ranks: dict, s: dict, t: dict) -> list:
    """Every damage, heal and shield number of a champion's kit at one build's stats.

    ranks: {slot: rank}. An ability not learned yet is worked out at rank 1.
    Returns [{slot, name, rank, cooldown, lines}], cooldown in seconds at the build's haste
    or None, and lines [{attr, amount, after, kind, rest}]: `amount` before the target's
    resistances, `after` with them and the build's penetration (None for a heal, a shield, or
    a number of unknown kind), kind "magic", "physical", "true" or "", and `rest` the parts
    that could not be worked out, in words (a share of the target's missing health). The
    numbers are per line of the ability as the dataset lists it: a line named "per tick" or
    "per spin" is one tick, not a cast.
    """
    kit = ((getattr(sd, "kits", None) or {}).get(champ_id) or {}).get("abilities") or {}
    physical_through, magic_through = _through(s, t)
    out = []
    for slot in "PQWER":
        ability = kit.get(slot)
        if not ability:
            continue
        rank = max(1, int(ranks.get(slot) or 0))
        pick = lambda values: values[min(18, max(1, s["level"])) - 1] if len(values) == 18 else values[min(len(values), rank) - 1]
        lines = []
        for line in ability["lines"]:
            attr = line["attr"]
            if not _SHOWN.search(attr) or _SKIPPED.search(attr):
                continue
            amount, rest = 0.0, []
            for values, unit in line["mods"]:
                part, words = _term(pick(values), unit, s, t)
                if part is None:
                    rest.append(words)
                else:
                    amount += part
            low = attr.lower()
            kind = ("" if "heal" in low or "shield" in low else "magic" if "magic" in low else "physical" if "physical" in low
                    else "true" if "true" in low else {"MAGIC_DAMAGE": "magic", "PHYSICAL_DAMAGE": "physical",
                                                       "TRUE_DAMAGE": "true"}.get(ability["kind"], ""))
            through = {"magic": magic_through, "physical": physical_through, "true": 1.0}.get(kind)
            numeric = amount > 0
            lines.append({"attr": attr, "amount": amount if numeric else None,
                          "after": amount * through if numeric and through is not None else None, "kind": kind,
                          "rest": " + ".join(rest)})
        cooldown = None
        if ability["cooldown"]:
            seconds = ability["cooldown"][min(len(ability["cooldown"]), rank) - 1]
            haste = s["haste"] + (s["ult_haste"] if slot == "R" else s["basic_haste"] if slot in "QWE" else 0)
            cooldown = seconds * 100 / (100 + haste) if ability.get("haste", True) else seconds
        if lines:
            out.append({"slot": slot, "name": ability["name"], "rank": rank, "learned": bool(ranks.get(slot)),
                        "cooldown": cooldown, "lines": lines})
    return out


def on_abilities(names, s: dict, t: dict) -> list:
    """What the named items add when the player's abilities hit, each as a sentence with its number worked out."""
    _, magic = _through(s, t)
    physical, _ = _through(s, t)
    out = []
    say = lambda item, text: out.append(f"{item}: {text}") if item in names else None
    say("Liandry's Torment", f"burns for {0.06 * t['health'] * magic:.0f} over 3 seconds each time an ability hits (6% of the "
                             f"target's health, so more on enemies with much health), and up to 6% more damage as a fight goes on")
    say("Blackfire Torch", f"burns for {(60 + 0.06 * s['ap']) * magic:.0f} over 3 seconds each time an ability hits")
    say("Luden's Echo", f"adds {(75 + 0.05 * s['ap']) * magic:.0f} to the first ability hit; its charges return slowly, so about "
                        f"once a fight")
    say("Stormsurge", f"strikes for {(125 + 0.10 * s['ap']) * magic:.0f} once, after you deal a quarter of the target's health "
                      f"within 2.5 seconds")
    say("Malignance", f"the ultimate leaves a zone that deals {(60 + 0.05 * s['ap']) * magic:.0f} a second for 3 seconds to "
                      f"enemies who stay in it and cuts their magic resist by 10; the ultimate also comes back sooner")
    say("Shadowflame", "magic and true damage is 20% higher on enemies below 40% health")
    say("Spear of Shojin", "abilities deal up to 12% more after four ability hits, and basic abilities come back sooner")
    say("Riftmaker", "all damage is up to 8% higher after four seconds of fighting")
    say("Horizon Focus", "damage is 10% higher on enemies hit by an ability from 600 units or more")
    say("Abyssal Mask", "enemies within 700 units take 12% more magic damage, from your whole team")
    say("Imperial Mandate", "an enemy you immobilize takes 7% more damage for 4 seconds")
    say("Lord Dominik's Regards", f"all damage on this target is {100 * min(0.15, t.get('bonus_health', 0.0) / 10000):.0f}% higher "
                                  f"(1% for each 100 bonus health it has, 15% at most)")
    if "Bloodletter's Curse" in names:
        after = 100 / (100 + max(0.0, t["resist"] * 0.70 * s["resist_left"] - s["magic_pen"]))
        out.append(f"Bloodletter's Curse: at four stacks the target has 30% less magic resist, which raises magic damage on it "
                   f"by {100 * (after / magic - 1):.0f}%, for your whole team")
    say("Rylai's Crystal Scepter", "ability damage slows by 30% for 1 second; it adds no damage")
    say("Lich Bane", f"after an ability the next attack deals {(0.75 * s['base_ad'] + 0.40 * s['ap']) * magic:.0f} more")
    say("Trinity Force", f"after an ability the next attack deals {2.0 * s['base_ad'] * physical:.0f} more")
    say("Iceborn Gauntlet", f"after an ability the next attack deals {1.5 * s['base_ad'] * physical:.0f} more and slows")
    say("Essence Reaver", f"after an ability the next attack deals {(1.25 * s['base_ad'] + 50 * s['crit']) * physical:.0f} more")
    say("Hextech Rocketbelt", f"its button deals {(100 + 0.10 * s['ap']) * magic:.0f}")
    say("Hextech Gunblade", f"its button deals {(175 + 0.30 * s['ap']) * magic:.0f} or more")
    return out


# ---- a formula Claude writes ---------------------------------------------------

_FUNCTIONS = {"min": min, "max": max, "floor": math.floor, "ceil": math.ceil, "round": round, "abs": abs, "sqrt": math.sqrt}
VARIABLES = ("AD", "base_AD", "bonus_AD", "AP", "health", "bonus_health", "armor", "bonus_armor", "MR", "bonus_MR",
             "attack_speed", "bonus_attack_speed", "crit_chance", "crit_damage", "haste", "level", "mana",
             "target_health", "target_armor", "target_MR")


def variables(s: dict, t: dict) -> dict:
    """The names a formula may use, for one build against one target (see VARIABLES), and three functions.

    physical(x) and magic(x) give what is left of x after the target's armor or magic resist
    with the build's penetration. cooldown(x) is x seconds at the build's ability haste.
    """
    physical, magic = _through(s, t)
    values = {"ad": s["ad"], "base_ad": s["base_ad"], "bonus_ad": s["bonus_ad"], "ap": s["ap"], "health": s["health"],
              "bonus_health": s["bonus_health"], "armor": s["armor"], "bonus_armor": s["bonus_armor"], "mr": s["resist"],
              "bonus_mr": s["bonus_resist"], "attack_speed": s["speed"], "bonus_attack_speed": s["bonus_speed"],
              "crit_chance": s["crit"], "crit_damage": s["crit_damage"], "haste": s["haste"], "level": s["level"],
              "mana": s["mana"], "target_health": t["health"], "target_armor": t["armor"], "target_mr": t["resist"]}
    functions = dict(_FUNCTIONS, physical=lambda x: x * physical, magic=lambda x: x * magic,
                     cooldown=lambda x: x * 100 / (100 + s["haste"]))
    return {"values": values, "functions": functions}


def evaluate(formula: str, names: dict) -> float:
    """Work out one arithmetic formula. names: the result of `variables`. Raises ValueError with a reason Claude can read.

    Only numbers, the names, + - * / // % ** and the listed functions are accepted. Nothing
    else in Python is: the formula is read as a syntax tree and each node is checked, so no
    attribute, subscript, string or call to anything else can run.
    """
    if not isinstance(formula, str) or not formula.strip() or len(formula) > 400:
        raise ValueError("a formula is 1 to 400 characters of arithmetic")
    try:
        tree = ast.parse(formula.strip().replace("^", "**").replace("×", "*"), mode="eval")
    except SyntaxError:
        raise ValueError("not arithmetic this tool can read")
    seen = 0

    def work(node):
        nonlocal seen
        seen += 1
        if seen > 200:
            raise ValueError("formula too long")
        if isinstance(node, ast.Expression):
            return work(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.Name):
            if node.id.lower() in names["values"]:
                return names["values"][node.id.lower()]
            raise ValueError(f"unknown name {node.id}; the names are {', '.join(VARIABLES)}")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = work(node.operand)
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp):
            a, b = work(node.left), work(node.right)
            try:
                if isinstance(node.op, ast.Add):
                    return a + b
                if isinstance(node.op, ast.Sub):
                    return a - b
                if isinstance(node.op, ast.Mult):
                    return a * b
                if isinstance(node.op, ast.Div):
                    return a / b
                if isinstance(node.op, ast.FloorDiv):
                    return a // b
                if isinstance(node.op, ast.Mod):
                    return a % b
                if isinstance(node.op, ast.Pow) and abs(b) <= 8 and abs(a) <= 1e6:
                    return a ** b
            except ZeroDivisionError:
                raise ValueError("division by zero")
            raise ValueError("an operator this tool does not take")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            function = names["functions"].get(node.func.id.lower())
            if function is None:
                raise ValueError(f"unknown function {node.func.id}; the functions are {', '.join(sorted(names['functions']))}")
            try:
                return function(*[work(arg) for arg in node.args])
            except (TypeError, ValueError, ZeroDivisionError):
                raise ValueError(f"{node.func.id} could not be worked out with those values")
        raise ValueError("only numbers, the listed names, + - * / // % ** and the listed functions")

    value = work(tree)
    if isinstance(value, complex) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("the formula does not give a number")
    return float(value)
