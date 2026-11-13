"""The calculations Claude can call while it makes a plan: what it is told about them, and what it gets back.

The arithmetic is in calc.py and itemworth.py. This module is the part Claude sees: the name,
description and inputs of each calculation (DEFINITIONS), the lines added to a plan request
(PLAN_NOTE), and the text of each answer. An answer always says what was measured against,
what was counted and what was not, because a number without that is trusted too far.

Every calculation compares builds. A build is a list of item names to add to what the
player holds, and the player as they stand ("now") is always the first row, so each answer
reads as "this much more than now" and one call settles a choice between candidates. That
matters for the wait: each round of calls costs one more answer from Claude, several seconds
while the player is dead and looking at the shop. Claude may send several calls at once.

Nothing here changes anything: a calculation reads the match state and returns text.
"""
from __future__ import annotations

import time

from . import calc, itemworth, threats

ROUNDS = 2                # rounds of calls Claude may make before it must answer

# Added to a plan request that sets the build (see advisor.sets_the_build). The first wording said to use the
# calculations "when two or more candidates are close" and to answer without them otherwise. Offered that, Claude
# at low effort called none in four plans out of four: it does not judge a call close until it has the numbers.
# So the request now says to work the choice out first, and the coach offers the calculations only to the plans
# where the build is decided, not to the ones that keep it up to date.
PLAN_NOTE = (
    "THIS PLAN SETS THE BUILD, SO WORK THE CHOICE OUT BEFORE YOU ANSWER. You have calculations for it: attack_damage, "
    "ability_damage, survival where offered, and evaluate. They run on the player's real stats from the game and on the "
    "numbers of each item and ability.",
    "  - First decide which two to four items, or sets of items, are the real candidates for what the player buys next and "
    "for the core of the build. Then send one step of calls that compares them: attack_damage for a champion that fights "
    "with basic attacks, ability_damage for one that fights with abilities, survival for defensive items, and evaluate for "
    "a rule of the kit or an augment that the others do not model. Several calls in the one step are fine.",
    "  - Do not answer this request without that step. The one exception: every item still to buy is already fixed by "
    "something else, such as an item an augment needs, an instruction from the player, or an item half bought.",
    f"  - You get at most {ROUNDS} steps of calls. The player is waiting, so use one unless the first leaves the choice open.",
    "  - A result is arithmetic, and it is better evidence of what an item is worth here than the item's name or its "
    "reputation. It also says what it did not count. Weigh that part in words: a slow, a shield for a teammate, range, or "
    "an effect of the champion's own kit can still decide a close call.",
    "  - An augment or a combination that needs a particular item still comes first, and the player's instructions above "
    "hold whatever a number says.",
    "  - Then answer with the plan JSON exactly as always. `next_item_why` and `changed` may give a number from a result in "
    "plain words. Do not mention the calculations themselves.",
)

def kit_rules(sd, champ_id) -> list:
    """Lines for a plan request: the sentences of the player's kit that say how an item stat changes an ability.

    Claude writes the formula for `evaluate` before it sees any result, from what the request
    says about the kit. Asked about Garen's spin without these lines it multiplied by the full
    critical strike damage, where the spin's own rule is a smaller bonus.
    """
    kit = ((getattr(sd, "kits", None) or {}).get(champ_id) or {}).get("abilities") or {}
    found = [f"    {slot} {kit[slot]['name']}: {rule}" for slot in "PQWER" if slot in kit for rule in kit[slot].get("rules") or []]
    if not found:
        return []
    return ["  RULES OF YOUR KIT THAT ITEM STATS CHANGE (from the game data). attack_damage and ability_damage do not apply them; "
            "put them in a formula for `evaluate` when one decides the choice:"] + found


_BUILDS = {
    "type": "array",
    "description": ("One to four candidate builds to compare. Each is a list of item names to ADD to what the player holds "
                    "now, spelled as in the item catalog. The player as they stand is always included as the row `now`."),
    "items": {"type": "array", "items": {"type": "string"}},
}
_TARGET = {"type": "string", "description": ("The enemy champion to measure against, by name, for example the one who must "
                                             "die first or the one with the most health. Leave out for the enemy team's "
                                             "average.")}
_EXTRA = {
    "type": "object",
    "description": ("Stats to add to every row on top of items, for an augment or stacks the game's figures do not show "
                    "yet. Leave out normally."),
    "properties": {key: {"type": "number"} for key in ("attack_damage", "ability_power", "health", "armor", "magic_resist",
                                                       "attack_speed_percent", "crit_chance_percent", "ability_haste")},
}
_LEVEL = {"type": "integer", "description": ("Champion level to work at, to compare finished builds late in the match. "
                                             "Leave out for the current level.")}

DEFINITIONS = [
    {
        "name": "attack_damage",
        "description": (
            "Works out what the player's basic attacks do with each candidate build: attacks a second, the damage of one "
            "attack, the damage on one enemy over six seconds with every on-hit item effect counted (critical strikes, "
            "attack speed, Blade of The Ruined King, Runaan's bolts, Black Cleaver, penetration and the rest), when that "
            "enemy dies, and what the enemies beside it take. Call it when the champion fights with basic attacks and you "
            "are choosing between attack items or their order. It does not count the champion's own abilities."),
        "input_schema": {"type": "object", "properties": {"builds": _BUILDS, "target": _TARGET, "extra": _EXTRA, "level": _LEVEL},
                         "required": ["builds"]},
    },
    {
        "name": "ability_damage",
        "description": (
            "Works out every damage, heal and shield number of the player's champion with each candidate build: each "
            "ability's numbers at the build's ability power, attack damage and health, after the enemy's resistances and "
            "the build's penetration, each cooldown at the build's ability haste, and what each added item does when an "
            "ability hits. Call it when the champion fights with abilities and you are choosing between items for them, "
            "or to see how much of the kit scales with a stat before you build that stat."),
        "input_schema": {"type": "object", "properties": {"builds": _BUILDS, "target": _TARGET, "extra": _EXTRA, "level": _LEVEL},
                         "required": ["builds"]},
    },
    {
        "name": "survival",
        "description": (
            "Works out how much longer the player lasts in a fight with each candidate set of defensive items bought "
            "together, with the items' effects counted and feeding each other (Unending Despair's heal from the health "
            "the others give, Jak'Sho on their resistances, Kaenic Rookern's shield). Call it when you are choosing "
            "between defensive items or sets of them for a champion that stands in front. The figures in the request "
            "cover single items only."),
        "input_schema": {"type": "object", "properties": {"builds": _BUILDS}, "required": ["builds"]},
    },
    {
        "name": "evaluate",
        "description": (
            "Evaluates arithmetic you write, on the real stats of each candidate build. Use it for anything the other "
            "calculations do not model: an ability with a rule of its own (Garen's spin count, a stacking passive), or "
            "what an augment adds. Names you can use: " + ", ".join(calc.VARIABLES) + ". attack_speed is attacks a second, "
            "bonus_attack_speed a percent, crit_chance 0 to 1, crit_damage a multiple such as 2.0. Functions: "
            "physical(x) and magic(x) give x after the target's armor or magic resist with the build's penetration, "
            "cooldown(x) gives x seconds at the build's ability haste, and min, max, floor, ceil, round, abs, sqrt. "
            "Example: (7 + floor(bonus_attack_speed / 25)) * physical(20 + 0.4 * AD) * (1 + crit_chance * 0.5)."),
        "input_schema": {
            "type": "object",
            "properties": {
                "formulas": {"type": "array", "description": "One to six formulas, each with a short label saying what it is.",
                             "items": {"type": "object", "properties": {"label": {"type": "string"}, "formula": {"type": "string"}},
                                       "required": ["label", "formula"]}},
                "builds": _BUILDS, "target": _TARGET, "extra": _EXTRA, "level": _LEVEL},
            "required": ["formulas"],
        },
    },
]


class BadInput(ValueError):
    """An input Claude can correct. The message is sent back to it."""


def _change(value: float, reference: float) -> str:
    if not reference or abs(value - reference) < 1e-9:
        return ""
    return f" ({100 * (value / reference - 1):+.0f}%)"


class Toolbox:
    """The calculations for one plan request, bound to the match state the request was made from.

    sturdy: whether the champion builds defense. `survival` is offered only then: a champion
    that does not is told not to buy plain defensive items at all (threats.FRAGILE_NOTE), and
    a tool that ranks them would argue with that.
    share: the physical share of the damage getting through to the player (threats.mix), which
    the survival arithmetic needs. calls: what was called, for the log.
    """

    def __init__(self, sd, state: dict, sturdy: bool = False, share: float | None = None):
        self.sd, self.state, self.sturdy, self.share = sd, state, sturdy, share
        self.rounds, self.calls, self._missing, self._extra_words = ROUNDS, [], [], ""
        self.definitions = [d for d in DEFINITIONS if d["name"] != "survival" or (sturdy and share is not None)]

    def call(self, name: str, args) -> tuple:
        """Run one calculation. Returns (text, failed); a failure's text says what to correct."""
        started = time.time()
        handler = {"attack_damage": self._attack_damage, "ability_damage": self._ability_damage,
                   "survival": self._survival, "evaluate": self._evaluate}.get(name)
        try:
            if handler is None or name not in {d["name"] for d in self.definitions}:
                raise BadInput(f"There is no calculation called {name}.")
            if not isinstance(args, dict):
                raise BadInput("The input must be a JSON object.")
            text, failed = handler(args), False
        except BadInput as exc:
            text, failed = str(exc), True
        except Exception as exc:                       # a fault in a calculation must not lose the plan
            text, failed = f"This calculation failed ({type(exc).__name__}). Answer without it.", True
        self.calls.append({"name": name, "input": args if isinstance(args, dict) else str(args)[:200], "failed": failed,
                           "ms": round(1000 * (time.time() - started)), "chars": len(text)})
        return text, failed

    # ---- inputs ----------------------------------------------------------------

    def _rows(self, args: dict, need_builds: bool = True) -> list:
        """The rows to compare: [(label, words, sheet)], `now` first, then one per candidate build."""
        builds = args.get("builds")
        if builds is None and not need_builds:
            builds = []
        if not isinstance(builds, list) or any(not isinstance(b, list) or any(not isinstance(n, str) for n in b) for b in builds):
            raise BadInput("`builds` must be a list of builds, each a list of item names, for example "
                           "[[\"Infinity Edge\"], [\"Runaan's Hurricane\", \"Infinity Edge\"]].")
        extra, level = args.get("extra"), args.get("level")
        if extra is not None and not isinstance(extra, dict):
            raise BadInput("`extra` must be an object of numbers, for example {\"ability_power\": 60}.")
        if level is not None and (isinstance(level, bool) or not isinstance(level, int) or not 1 <= level <= 30):
            raise BadInput("`level` must be a whole number from 1 to 30.")
        rows = [("now", "the items you hold" + (f", at level {level}" if level else ""),
                 calc.sheet(self.sd, self.state, (), extra, level))]
        self._missing = []
        for build in [b for b in builds if b][:calc.MAX_BUILDS]:
            s = calc.sheet(self.sd, self.state, build[:8], extra, level)
            self._missing += [n for n in s["unknown"] if n not in self._missing]
            if s["added"]:                             # else nothing in it that the player does not already hold
                rows.append(("ABCD"[len(rows) - 1], f"now + {', '.join(s['added'])} ({s['gold']} gold)", s))
        return rows

    def _target(self, args: dict) -> tuple:
        name = args.get("target")
        if name is not None and not isinstance(name, str):
            raise BadInput("`target` must be an enemy champion's name.")
        level = args.get("level")
        t = calc.target(self.sd, self.state, name, level if isinstance(level, int) and not isinstance(level, bool) else None)
        said = (f"Against {t['label']}: {t['health']:.0f} health, {t['armor']:.0f} armor, {t['resist']:.0f} magic resist. "
                f"These are estimates from champion, level and items; real values are somewhat higher.")
        if t["missed"]:
            said = (f"No enemy is called {name}; the enemies are {', '.join(p['champion'] for p in self.state['enemies'])}. "
                    + said)
        return t, said

    def _footer(self, rows: list, left_out: dict, always: str) -> list:
        names = set().union(*[s["names"] for _, _, s in rows])
        out = ["Not counted: " + "; ".join([always] + [text for item, text in left_out.items() if item in names]) + "."]
        if self._missing:
            out.append(f"Not in the item catalog, so left out: {', '.join(self._missing)}. Use the catalog's spelling.")
        if not rows[0][2]["real"]:
            out.append("The match has not loaded, so the start is the champion alone at this level plus the items held: "
                       "no runes, no augments.")
        if self._extra_words:
            out.append(f"Added to every row at your request: {self._extra_words}.")
        return out

    def _note_extra(self, args: dict):
        extra = args.get("extra") or {}
        self._extra_words = ", ".join(f"{value:g} {key.replace('_', ' ')}" for key, value in extra.items()
                                      if isinstance(value, (int, float)) and not isinstance(value, bool))

    # ---- the calculations --------------------------------------------------------

    def _attack_damage(self, args: dict) -> str:
        self._note_extra(args)
        rows, (t, said) = self._rows(args), self._target(args)
        out = [said, f"{calc.ATTACK_SECONDS:g} seconds of basic attacks on that one enemy and nothing else, with "
                     f"{calc.BESIDE} more enemies standing beside it:"]
        reference, counted = None, []
        for label, words, s in rows:
            a = calc.attacks(s, t)
            reference = reference or a
            counted += [n for n in a["counted"] if n not in counted]
            line = (f"  {label} = {words}: {a['rate']:.2f} attacks a second, {100 * s['crit']:.0f}% critical strike chance at "
                    f"{100 * s['crit_damage']:.0f}% damage, {s['ad']:.0f} attack damage | one attack {a['first']:.0f} | "
                    f"{a['dealt']:.0f} over the {calc.ATTACK_SECONDS:g} seconds{_change(a['dealt'], reference['dealt']) if a is not reference else ''}"
                    f", {100 * a['share']:.0f}% of its health")
            line += f", dead after {a['kills_in']:.1f}s" if a["kills_in"] is not None else ""
            if a["others"] >= 1:
                line += f" | each enemy beside it takes {a['others']:.0f}"
            out.append(line)
        if counted:
            out.append("Item effects counted: " + ", ".join(counted) + ". Effects that build up start empty, and an effect "
                       f"that needs an ability cast first is counted once every {calc.SPELLBLADE_EVERY:g} seconds.")
        out += self._footer(rows, calc.ATTACKS_LEFT_OUT, "the champion's own abilities and passives beyond what its stats "
                            "show now, augments beyond the stats they give, life steal, and the range or safety an item gives")
        return "\n".join(out)

    def _ability_damage(self, args: dict) -> str:
        self._note_extra(args)
        rows, (t, said) = self._rows(args), self._target(args)
        me = self.state["me"]
        level = rows[0][2]["level"]
        ranks = me.get("ability_ranks") or {}
        guessed = level != (me.get("level") or 1) or not ranks
        if guessed:
            ranks = calc.assumed_ranks(level)
        kits = [calc.abilities(self.sd, me.get("champ_id"), ranks, s, t) for _, _, s in rows]
        if not kits[0]:
            raise BadInput(f"There are no ability numbers for {me.get('champion')} in the data. Use `evaluate` with the "
                           f"numbers in the champion notes.")
        out = [said, f"{me.get('champion')}'s ability numbers at each row's stats, after that enemy's resistances and the "
                     f"row's penetration (heals and shields as they are). Each line is one line of the ability as the game "
                     f"data lists it: a line named per tick, per spin, per second or per hit is that one part, not a whole cast."
                     + (f" Ranks assumed for level {level}: " + " ".join(f"{k}{v}" for k, v in ranks.items()) + "." if guessed else "")]
        for label, words, s in rows:
            pen = []
            if s["resist_left"] < 1 or s["magic_pen"]:
                pen.append(f"magic penetration {100 * (1 - s['resist_left']):.0f}% and {s['magic_pen']:.0f}")
            if s["armor_left"] < 1 or s["lethality"]:
                pen.append(f"armor penetration {100 * (1 - s['armor_left']):.0f}% and {s['lethality']:.0f}")
            out.append(f"  {label} = {words}: {s['ap']:.0f} ability power, {s['ad']:.0f} attack damage ({s['bonus_ad']:.0f} of it "
                       f"bonus), {s['health']:.0f} health, {s['haste']:.0f} ability haste" + (", " + ", ".join(pen) if pen else ""))
        for index, ability in enumerate(kits[0]):
            out.append(f"{ability['slot']} {ability['name']} (rank {ability['rank']}"
                       + ("" if ability["learned"] or guessed else ", not learned yet") + "):")
            for row, line in enumerate(ability["lines"]):
                cells, first = [], None
                for (label, _, _), kit in zip(rows, kits):
                    mine = kit[index]["lines"][row]
                    value = mine["after"] if mine["after"] is not None else mine["amount"]
                    if value is None:
                        cells.append(f"{label} {mine['rest']}")
                        continue
                    first = value if first is None else first
                    cells.append(f"{label} {value:.0f}" + (f" + {mine['rest']}" if mine["rest"] else "")
                                 + (_change(value, first) if label != "now" else ""))
                kind = f", {line['kind']}" if line["kind"] else ""
                out.append(f"  {line['attr']}{kind}: " + " | ".join(cells))
            if ability["cooldown"] is not None:
                out.append("  cooldown: " + " | ".join(f"{label} {kit[index]['cooldown']:.1f}s" for (label, _, _), kit in zip(rows, kits)))
        held = calc.on_abilities(rows[0][2]["names"], rows[0][2], t)
        if held:
            out.append("What the items you hold do when abilities hit: " + "; ".join(held) + ".")
        for label, _, s in rows[1:]:
            adds = calc.on_abilities(set(s["added"]), s, t)
            out.append(f"What {label}'s added items do when abilities hit: " + ("; ".join(adds) if adds else
                                                                               "nothing beyond their stats, which are in the numbers above") + ".")
        out += self._footer(rows, calc.ABILITIES_LEFT_OUT, "how often each ability lands, the champion's rules that are "
                            "not a plain number (a spin count, stacks, a missing-health part shown in words), heal and "
                            "shield power, and augments beyond the stats they give")
        return "\n".join(out)

    def _survival(self, args: dict) -> str:
        builds = args.get("builds")
        if not isinstance(builds, list) or any(not isinstance(b, list) or any(not isinstance(n, str) for n in b) for b in builds):
            raise BadInput("`builds` must be a list of builds, each a list of item names.")
        f = itemworth.fight(self.sd, self.state, self.share) if self.share is not None else None
        if f is None:
            raise BadInput("This needs the player's stats from a running match and at least one known enemy. Not available now.")
        family = calc.catalog_family_for(self.state.get("item_ids") or [])
        found = threats.mix(self.sd, self.state)
        attackers = sum(1 for row in (found or {}).get("rows", []) if row["kind"] == "physical")
        out = [f"The fight assumed: {f['far']} enemies in reach of effects around you, {attackers} of them fighting with basic "
               f"attacks, and an enemy team that kills you in {itemworth.FIGHT_SECONDS:g} seconds as you stand now. "
               f"{100 * f['aimed']:.0f}% of the damage aimed at you is physical."]
        unknown = []
        for index, build in enumerate([b for b in builds if b][:calc.MAX_BUILDS]):
            items = []
            for name in build[:8]:
                item = calc.find_item(self.sd, name, family)
                if item is None:
                    unknown.append(name)
                elif item["name"] not in f["owned"] and item not in items:
                    items.append(item)
            if not items:
                continue
            r = itemworth.together(items, f)
            line = (f"  {'ABCD'[index]} = now + {', '.join(r['names'])} ({r['gold']} gold): you last {100 * r['gain']:+.0f}% longer "
                    f"({r['lasts']:.1f}s), {1000 * 100 * r['gain'] / max(1, r['gold']):.0f}% per 1000 gold")
            if r["counted"]:
                line += f" | counted: {r['counted']}"
            if r["dealt"] >= 100:
                line += f" | the effects deal about {round(r['dealt'] / 50) * 50} in the fight"
            out.append(line)
        if len(out) == 1:
            raise BadInput("None of those builds holds an item from the catalog that the player does not already own.")
        out.append("Not counted: what an item does for teammates, Thornmail's cut to the healing of enemies who attack you, "
                   "anything behind an item's button, and the damage stats of an item. An item with no note was counted for "
                   "its health, armor and magic resist alone. The order near the top changes with how many enemies stand "
                   "near you.")
        if unknown:
            out.append(f"Not in the item catalog, so left out: {', '.join(unknown)}. Use the catalog's spelling.")
        return "\n".join(out)

    def _evaluate(self, args: dict) -> str:
        self._note_extra(args)
        formulas = args.get("formulas")
        if (not isinstance(formulas, list) or not formulas
                or any(not isinstance(f, dict) or not isinstance(f.get("formula"), str) for f in formulas)):
            raise BadInput("`formulas` must be a list such as [{\"label\": \"one Q\", \"formula\": \"magic(80 + 0.9 * AP)\"}].")
        rows, (t, said) = self._rows(args, need_builds=False), self._target(args)
        names = [calc.variables(s, t) for _, _, s in rows]
        out = [said]
        for label, words, s in rows:
            out.append(f"  {label} = {words}: AD {s['ad']:.0f} (base {s['base_ad']:.0f}), AP {s['ap']:.0f}, health {s['health']:.0f} "
                       f"(bonus {s['bonus_health']:.0f}), armor {s['armor']:.0f}, MR {s['resist']:.0f}, attack_speed {s['speed']:.2f} "
                       f"(bonus {s['bonus_speed']:.0f}%), crit_chance {s['crit']:.2f}, crit_damage {s['crit_damage']:.2f}, "
                       f"haste {s['haste']:.0f}")
        for entry in formulas[:6]:
            cells, first = [], None
            for (label, _, _), build in zip(rows, names):
                try:
                    value = calc.evaluate(entry["formula"], build)
                except ValueError as exc:
                    raise BadInput(f"In \"{str(entry.get('label') or entry['formula'])[:60]}\": {exc}.")
                first = value if first is None else first
                cells.append(f"{label} {value:.4g}" + (_change(value, first) if label != "now" else ""))
            out.append(f"{str(entry.get('label') or entry['formula'])[:80]}: " + " | ".join(cells))
        out += self._footer(rows, {}, "anything the formula itself leaves out. The stats are the game's figures plus the "
                            "added items' stat lines")
        return "\n".join(out)
