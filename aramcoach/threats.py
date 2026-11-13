"""What kind of damage is killing the player.

The game's local data has no damage numbers, so a plan cannot see what kind of damage the
player is dying to. It can be estimated, in two steps.

First, what the enemies aim at the player. Each enemy's damage is physical, magic or both,
read from their champion and the items they have bought; the kills on the player and the
enemies' item gold say how much each of them counts.

Second, what gets through. The player's own armor and magic resist decide that, and the game
does report those. A player with 460 armor and 70 magic resist takes 18% of the physical
damage aimed at them and 59% of the magic damage, so most of what kills them is magic even
when most of what is aimed at them is physical. The first version of this estimate left the
second step out. In one real match it told a Malphite who was stacking armor that the damage
on them was 60 to 75% physical for the whole match; the post-game record measured 32%. The
plan swapped its one magic resist item for more armor on the strength of that figure.

Checked against 42 recorded matches, where the measured split is known afterwards: the
estimate of the physical share of the damage the player takes is off by 6 points on average,
by 18 at worst, and within 12 points in 37 of the 42 (see the numbers at `mix`). Without the
second step the worst miss was 31. The constants were tuned on 34 of those matches, so expect
a little worse on new ones. Asked only which kind is the larger, it was right in 18, said
"a mix" in 24 and was wrong in none.

The estimate is information for the plan, not a rule. It exists so that a defensive item,
when the build takes one, is of the right kind: one real match moved a magic resist item up
against a physical attacker, and another stacked 8,500 health on a tank with no armor against
a team that was 70% physical. An earlier version went further and forced a defensive item
next once the player had died three times outside fights their team won. Replayed over the
player's eleven recorded matches it fired in nine, at a median of seven minutes, and in the
match this coach was designed around it would have put Randuin's Omen ahead of the Infinity
Edge that completed the combination. Nothing in the records showed a defensive item going
with fewer deaths or more wins. It was removed: the combination comes first.

The per-item figures are for champions that build defense: the ones that stand in front, and
the ones the game classes as tanks. For every other champion they did harm. The list was
sorted by survivability per gold, so a mage or a marksman who kept dying was shown Randuin's
Omen, Warmog's Armor and Jak'Sho at the top of it, and the plan took one: Randuin's Omen
entered the build in 3 of the player's 5 matches on such champions once the estimate was
given weight in plans, each time "because physical damage keeps killing you", against 0 of 4
before the estimate existed. The player's friends put it plainly: the item adds defense, the
champion is fragile anyway, and it should have been more damage. The player typed that to
the coach mid-match and the coach argued. So a champion that does not build defense is now
told the player's instruction instead (FRAGILE_NOTE), and is shown only defensive items that
also carry its own damage stat.

Healing is left out on purpose. From kits and items a program picked the heavy healers of
those matches correctly only 20 to 50% of the time: most healing in ARAM: Mayhem comes from
augments, which the game does not show. The request says only whether a teammate already
holds an item that cuts healing, which is a fact.
"""
from __future__ import annotations

PHYSICAL_STATS = ("Attack Damage", "Critical Strike Chance%", "Attack Speed%", "Lethality", "Armor Penetration%",
                  "Life Steal%")
MAGIC_STATS = ("Ability Power", "Magic Penetration", "Magic Penetration%")
LEAN_GOLD = 2000          # item gold needed before items outweigh the champion's usual kind
BUILT_GOLD = 3000         # item gold from which a build that does not lean says something about the champion
ONE_SIDED = 0.6           # physical share at or above which the damage counts as mostly physical
FRONTLINE_BIAS = 0.07     # front-line champions took this much more physical damage than the estimate said
KILL, ASSIST = 3, 1       # weight of a killing blow and of an assist when crediting the player's deaths
RESIST, HEALTH = 40, 300  # what an item needs to count as defense against the damage

FRAGILE_NOTE = (
    "  This champion is in the match to deal damage or to back up teammates, not to stand in front, and it stays fragile "
    "whatever it buys. The player's instruction for such champions: do not buy an item only for its armor, magic resist "
    "or health. On a champion like this it does not "
    "prevent the death, and it delays every item that makes the kit work. Answer deaths with more damage, range or speed "
    "in the build, and with where to stand in how_to_play. A plain defensive item belongs in this build only as a piece of "
    "a combination: an augment the player holds turns health, armor or magic resist into damage or healing. Then `changed` "
    "names that augment.")


def champion_kind(sd, champ_id) -> str:
    """The kind of damage a champion usually deals: "physical" or "magic", from the game's own scores."""
    champ = sd.champions.get(champ_id) or {}
    return "physical" if (champ.get("attack") or 0) >= (champ.get("magic") or 0) else "magic"


def _lean(sd, item_ids) -> tuple:
    """Gold in items that carry only attack stats, and in items that carry only ability power."""
    physical = magic = 0
    for iid in item_ids:
        item = sd.items.get(iid)
        if not item:
            continue
        p = any(k in item["stats"] for k in PHYSICAL_STATS)
        m = any(k in item["stats"] for k in MAGIC_STATS)
        if p and not m:
            physical += item["total"]
        elif m and not p:
            magic += item["total"]
    return physical, magic


def physical_share(sd, player: dict) -> float:
    """The share of one player's damage that is physical, 0 to 1.

    The numbers are the averages measured in recorded matches for players who looked the same
    during the match. A build that leans one way decides: 88% physical for attack items, 8% for
    ability power. Without one, usually a tank or a support, the champion's usual kind counts
    for less: such champions deal a good deal of both.
    """
    physical, magic = _lean(sd, [i["id"] for i in player["items"]])
    if physical + magic >= LEAN_GOLD and max(physical, magic) > 2 * min(physical, magic):
        return 0.88 if physical > magic else 0.08
    tags = (sd.champions.get(player["champ_id"]) or {}).get("tags") or []
    sturdy = tags[:1] in (["Tank"], ["Support"])
    if champion_kind(sd, player["champ_id"]) == "physical":
        if sturdy:
            return 0.5
        # A fighter who has built health and resistances instead of attack items deals much of their damage
        # with abilities and effects that are magic. Nine such players in the records averaged 59% physical
        # (Volibear 51%, Nasus 34%, Gangplank 52%, Sett 71%), where the champion's usual kind said 80%.
        built = sum((sd.items.get(i["id"]) or {}).get("total", 0) for i in player["items"]) >= BUILT_GOLD
        return 0.6 if built else 0.8
    return 0.35 if sturdy else 0.2


def damage_kind(sd, player: dict) -> str:
    """The kind of damage one player deals this match, in a word: "physical", "magic" or "mixed"."""
    share = physical_share(sd, player)
    return "physical" if share >= 0.65 else "magic" if share <= 0.35 else "mixed"


def true_damage(sd, champ_id) -> list:
    """The abilities of one champion whose text says they deal true damage, such as ["R Feast"].

    Armor and magic resist do not reduce true damage, and the estimate below divides damage
    into physical and magic only. In 37 recorded matches true damage was a median 6% of what
    the player took and 15% or more in four; against a Cho'Gath it was 30%, and the coach
    picked magic resist three times over health.
    """
    notes = sd.champion_notes(champ_id) if champ_id else None
    if not notes:
        return []
    found = ["passive"] if "true damage" in notes["passive"].lower() else []
    return found + [spell.split(":", 1)[0] for spell in notes["spells"] if "true damage" in spell.lower()]


def own_resistances(sd, me: dict | None):
    """The player's armor and magic resist, and what their champion has alone at this level.

    Returns (armor, magic resist, champion's own armor, champion's own magic resist), or None
    when the game has not reported the player's stats. The second pair is the reference the
    estimate was tuned for: a player who has bought no resistance.
    """
    stats = (me or {}).get("stats") or {}
    armor, resist = stats.get("armor"), stats.get("magicResist")
    if armor is None or resist is None or not (armor or resist):
        return None
    from .live import estimate_stats                 # imported here: this module is otherwise free of the game API
    alone = estimate_stats((sd.champions.get(me.get("champ_id")) or {}).get("base"), me.get("level") or 1, [], sd)
    if not alone:
        return None
    return armor, resist, alone["armor"], alone["magic resist"]


def gets_through(share: float, own) -> float:
    """The physical share of the damage the player takes, from the share they would take without bought resistances.

    Damage is divided by 1 + resistance / 100. So each kind is scaled by how much more of that
    resistance the player has than their champion alone, and the split follows.
    """
    armor, resist, alone_armor, alone_resist = own
    physical = share * (100 + alone_armor) / (100 + max(0, armor))
    magic = (1 - share) * (100 + alone_resist) / (100 + max(0, resist))
    return physical / (physical + magic) if physical + magic else share


def mix(sd, state: dict, frontline: bool = False):
    """How the damage on the player divides, or None before any enemy is known.

    Returns {share, aimed, side, rows, basis}. `share` is the estimated physical share of the
    damage the player takes, 0 to 1. `aimed` is the same before the player's own resistances
    are counted: what a player with only their champion's armor and magic resist would take.
    `side` is "physical", "magic" or "mixed", from `share`. `rows` lists the enemies, most
    kill credit on the player first: {champion, kind, kills, assists}.

    `aimed` is half kill credit and half the enemies' item gold, each enemy counted by how
    physical their damage is. Before the player has died twice it is the item gold alone, and
    before anyone has items a head count. A front-line champion soaks the enemy's attackers,
    so theirs is raised a little. `share` then follows from the player's armor and magic
    resist (see gets_through); without stats from the game it equals `aimed`.

    The side is physical from ONE_SIDED up, magic from the same distance down, and mixed in
    between. An earlier version let the killing blows decide a close call. Over the same 42
    matches that made 9 more calls and all 4 of the wrong ones, two of them by 9 and 14 points:
    whoever lands the last hit is not who did the damage. A mix is the honest answer there,
    and the figures per item still say which resistance is worth more.

    Measured on 42 recorded matches (8 with the player's real stats at every snapshot, 34 with
    resistances worked out from their items), as the error of `share` against the post-game
    record: 6.3 points on average, 18 at worst, within 12 points in 37. As first shipped,
    without the player's resistances: 7.3, 31 and 34. On the 16 front-line champions, the ones
    who buy resistances: 6.6 against 8.7 on average, 12 against 31 at worst.
    """
    enemies = state["enemies"]
    if not enemies:
        return None
    physical = {p["champion"]: physical_share(sd, p) for p in enemies}
    killed = state.get("killed_me") or {}
    credit = {c: KILL * t["kills"] + ASSIST * t["assists"] for c, t in killed.items() if c in physical}
    gold = {p["champion"]: p["item_gold"] for p in enemies}
    share_of = lambda weights: (sum(w * physical[c] for c, w in weights.items()) / sum(weights.values())
                                if sum(weights.values()) else None)
    by_gold, by_kills = share_of(gold), share_of(credit)
    deaths = sum(t["kills"] for c, t in killed.items() if c in physical)
    if by_gold is None:
        share, basis = share_of({c: 1 for c in physical}), "the enemy champions"
    elif by_kills is None or deaths < 2:
        share, basis = by_gold, "the enemies' items"
    else:
        share, basis = (by_gold + by_kills) / 2, "the kills on you and the enemies' items"
    rows = [{"champion": p["champion"], "kind": damage_kind(sd, p), "true": true_damage(sd, p.get("champ_id")),
             "kills": (killed.get(p["champion"]) or {}).get("kills", 0),
             "assists": (killed.get(p["champion"]) or {}).get("assists", 0)} for p in enemies]
    rows.sort(key=lambda r: -(KILL * r["kills"] + ASSIST * r["assists"]))
    if frontline:
        share = min(1.0, share + FRONTLINE_BIAS)
    own = own_resistances(sd, state.get("me"))
    aimed, share = share, gets_through(share, own) if own else share
    side = "physical" if share >= ONE_SIDED else "magic" if share <= 1 - ONE_SIDED else "mixed"
    return {"share": share, "aimed": aimed, "side": side, "rows": rows, "basis": basis}


def answers(item: dict, side: str, frontline: bool) -> bool:
    """Whether an item is defense of the kind this damage calls for.

    Against mostly physical damage it needs armor, against mostly magic damage magic resist,
    and against a mix either. Health counts as well for a champion who does not stand in
    front, because few resist items suit them. On a front-line champion health alone does
    not count: resistance is what makes a large health pool last. Boots never count.
    """
    stats = item["stats"]
    if "Boots" in item["tags"]:
        return False
    armor, resist, health = stats.get("Armor", 0) >= RESIST, stats.get("Magic Resist", 0) >= RESIST, stats.get("Health", 0) >= HEALTH
    if side == "physical":
        return armor or (health and not frontline)
    if side == "magic":
        return resist or (health and not frontline)
    return armor or resist or (health and not frontline)


def toughness_gain(item: dict, stats: dict, share: float):
    """How much more of this damage the player could take with the item, as a fraction, or None without stats.

    Health, armor and magic resist multiply each other: the damage a champion survives is
    their health divided by the part of each hit that gets through. `share` is the physical
    share of the damage the player is taking, after their armor and magic resist; from it and
    their current resistances the split of the damage before mitigation follows. Only the
    item's health, armor and magic resist count. Passive effects are left out.
    """
    health, armor, resist = stats.get("maxHealth"), stats.get("armor"), stats.get("magicResist")
    if not health or armor is None or resist is None:
        return None
    a, m = 100 / (100 + armor), 100 / (100 + resist)
    raw = share * m / (a * (1 - share) + share * m)          # physical share before armor and magic resist
    through = lambda arm, res: raw * 100 / (100 + arm) + (1 - raw) * 100 / (100 + res)
    added = item["stats"]
    after = (health + added.get("Health", 0)) / through(armor + added.get("Armor", 0), resist + added.get("Magic Resist", 0))
    return after / (health / through(armor, resist)) - 1


def read(sd, state: dict, catalog: list, frontline: bool, rejected: dict | None = None, sturdy: bool | None = None):
    """The damage on the player and what answers it. None before any enemy is known.

    sturdy: whether the champion builds defense (it stands in front, or the game classes it a
    tank). Taken to be `frontline` when not given. For a champion that does not, `fits` and
    `gains` hold only items that also carry its own damage stat, four at most.

    For a champion that does build defense, `worth` holds what each item is worth in a fight
    with its own effect counted (see itemworth), best value for its gold first. It is empty
    before the player's own stats are known.

    Returns {mix, held, fits, gains, worth, sturdy}. `held` names the finished items the player owns that
    are defense of the matching kind. `fits` names up to eight catalog items that would be,
    the ones that carry the champion's own damage stat first. `gains` lists, for the items
    with health, armor or magic resist that suit the champion, how much more damage the player
    could take with each: [{name, gain, gold, health_only}], most gain per gold first: the
    six best, with the two best health-only items always among them. It is empty before the
    player's own stats are known. Nothing here tells the plan to buy
    one: it says what each would be worth if it does.
    """
    found = mix(sd, state, frontline)
    me = state["me"]
    if found is None or me is None:
        return None
    sturdy = frontline if sturdy is None else sturdy
    side, rejected = found["side"], rejected or {}
    finished = {it["id"]: it for it in catalog}
    held = [i["name"] for i in me["items"] if i["id"] in finished and answers(finished[i["id"]], side, frontline)]
    magic_champion = physical_share(sd, me) <= 0.35
    own, other = (MAGIC_STATS, PHYSICAL_STATS) if magic_champion else (PHYSICAL_STATS, MAGIC_STATS)
    have = {i["id"] for i in me["items"]}

    def rank(item):          # the champion's own damage stat first, then plain defense; the other kind's items never
        mine = any(k in item["stats"] for k in own)
        theirs = any(k in item["stats"] for k in other)
        return None if theirs and not mine and not frontline else (0 if mine or frontline else 1, item["total"])

    suits = lambda it: rank(it) is not None and (sturdy or rank(it)[0] == 0)
    ranked = sorted((rank(it), it["name"]) for it in catalog if it["id"] not in rejected and it["id"] not in have
                    and answers(it, side, frontline) and suits(it))
    gains, candidates = [], []
    for it in catalog:
        tough = any(it["stats"].get(k, 0) >= least for k, least in (("Armor", RESIST), ("Magic Resist", RESIST), ("Health", HEALTH)))
        if not tough or it["id"] in rejected or it["id"] in have or "Boots" in it["tags"] or not suits(it):
            continue
        candidates.append(it)
        gain = toughness_gain(it, me.get("stats") or {}, found["share"])
        if gain is not None:
            plain = not any(it["stats"].get(k, 0) >= RESIST for k in ("Armor", "Magic Resist"))
            gains.append({"name": it["name"], "gain": gain, "gold": it["total"], "health_only": plain})
    gains.sort(key=lambda g: -g["gain"] / g["gold"])
    # The six best, and always the two best health-only items beside them: the choice that matters on a
    # champion stacking health is between more health and a resistance, so both have to be in view.
    # (With three health-only items among the six, the count below went negative and the slice returned almost
    # every item: one real request listed 27.)
    shown = gains[:6] + [g for g in gains[6:] if g["health_only"]][:max(0, 2 - sum(g["health_only"] for g in gains[:6]))]
    if not sturdy:
        shown = gains[:4]
    from . import itemworth                       # imported here: itemworth uses this module's reading of each enemy
    worth = itemworth.table(sd, state, found["share"], candidates) if sturdy else []
    return {"mix": found, "held": held, "fits": [name for _, name in ranked[:8 if sturdy else 4]], "gains": shown,
            "worth": worth, "sturdy": sturdy}


def lines(sd, state: dict, seen) -> list:
    """The estimate as lines for a plan request. seen: the result of `read`, or None."""
    if seen is None:
        return []
    found, me = seen["mix"], state["me"]
    share = round(100 * found["share"] / 5) * 5
    summary = {"physical": f"mostly physical, about {share}%", "magic": f"mostly magic, about {100 - share}%",
               "mixed": f"a mix, about {share}% physical"}[found["side"]]
    out = ["WHAT IS KILLING YOU (an estimate by the coach: the game reports no damage. Who killed you is exact; the kind "
           "of damage comes from each enemy's champion and items, and your own armor and magic resist decide how much of "
           "each kind gets through. In recorded matches the share was off by 6 points on average and by 18 at worst):"]
    for row in found["rows"]:
        score = (f"{row['kills']} kills on you, {row['assists']} assists" if row["kills"] or row["assists"]
                 else "no part in your deaths so far")
        kind = "physical and magic" if row["kind"] == "mixed" else row["kind"]
        also = f", and true damage with {', '.join(row['true'])}" if row.get("true") else ""
        out.append(f"  {row['champion']}: deals {kind} damage{also} | {score}")
    stats = me.get("stats") or {}
    stops = lambda value: round(100 * value / (100 + value)) if value > 0 else 0
    own = (f" You have {stats['maxHealth']:g} health, {stats['armor']:g} armor, which stops {stops(stats['armor'])}% of physical "
           f"damage, and {stats['magicResist']:g} magic resist, which stops {stops(stats['magicResist'])}% of magic damage."
           if all(k in stats for k in ("armor", "magicResist", "maxHealth")) else "")
    if not seen.get("sturdy", True):
        # A champion that does not build defense: the kind of damage, the player's instruction, and nothing that
        # reads as a shopping list of armor. See the module text for what the list did.
        out.append(f"  The damage that gets through to you is {summary} (from {found['basis']}).{own}")
        out.append(FRAGILE_NOTE)
        if seen["gains"]:
            out.append("  Items that carry this champion's damage stat and some defense as well, in case the build has a use "
                       "for one. Against this damage, with how much more of it you could take: "
                       + ", ".join(f"{g['name']} +{round(100 * g['gain'])}% for {g['gold']} gold" for g in seen["gains"]) + ".")
        elif seen["fits"]:
            out.append("  Items that carry this champion's damage stat and some defense as well, in case the build has a use "
                       "for one: "
                       + ", ".join(seen["fits"]) + ".")
        team = [me] + state["allies"]
        cutters = [f"{'you' if p is me else p['champion']} ({i['name']})" for p in team for i in p["items"]
                   if "Wounds" in (sd.items.get(i["id"]) or {}).get("text", "")]
        out.append("HEALING CUTS ON YOUR TEAM: " + (", ".join(cutters) if cutters else
                                                    "nobody holds an item that applies Wounds (40% less healing)") + ".")
        return out
    out.append(f"  The damage that gets through to you is {summary} (from {found['basis']}).{own} Finished items you hold "
               f"against it: {', '.join(seen['held']) or 'none'}.")
    if abs(found["share"] - found["aimed"]) >= 0.1:
        less, more = ("armor", "magic resist") if found["share"] < found["aimed"] else ("magic resist", "armor")
        kind = "physical" if less == "armor" else "magic"
        out.append(f"  More of the damage aimed at you is {kind} than that: your {less} is already stopping most of it. Each "
                   f"further point of {less} stops less than the one before, and what is left to stop is the other kind, so "
                   f"{more} is now worth more to you per gold. The figures below show how much.")
    biters = [row["champion"] for row in found["rows"] if row.get("true") and row["kills"]]
    if biters:
        out.append(f"  True damage is not in that split, and neither armor nor magic resist reduces it. {', '.join(biters)} "
                   f"killed you and can deal it, how much is not known: against that part only health helps.")
    if seen.get("worth"):
        from . import itemworth
        attackers = sum(1 for row in found["rows"] if row["kind"] == "physical")
        near = min(itemworth.FAR, len(state["enemies"]))

        def told(r):
            extra = [r["counted"]] if r["counted"] else []
            if r["dealt"] >= 100:
                extra.append(f"its effect deals about {round(r['dealt'] / 50) * 50} in the fight")
            return f"{r['name']} +{round(100 * r['gain'])}% for {r['gold']} gold" + (f" ({'; '.join(extra)})" if extra else "")

        out.append(f"  How much longer you would last in a fight with each item, worked out by the coach from your real stats "
                   f"with the item's own effect counted. The fight assumed: {near} enemies in reach of effects around you, "
                   f"{attackers} of them fighting with basic attacks, and an enemy team that kills you in "
                   f"{itemworth.FIGHT_SECONDS:g} seconds as you stand now. Best value for its gold first: "
                   + "; ".join(told(r) for r in seen["worth"][:12]) + ".")
        out.append("  Not counted in those figures: what an item does for teammates, Thornmail's cut to the healing of enemies "
                   "who attack you, and anything behind an item's button. An item with no note was counted for its health, "
                   "armor and magic resist alone. The order near the top changes with how many enemies stand near you; an "
                   "item far down the list is a poor buy in any fight.")
    elif seen["gains"]:
        out.append("  How much more of this damage you could take with each item, from its health, armor and magic resist "
                   "alone (passive effects not counted), best value first: "
                   + ", ".join(f"{g['name']} +{round(100 * g['gain'])}% for {g['gold']} gold" for g in seen["gains"]) + ".")
    else:
        out.append(f"  If the build takes a defensive item, these are the kind that matches and suit this champion: "
                   f"{', '.join(seen['fits']) or 'none found'}.")
    team = [me] + state["allies"]
    cutters = [f"{'you' if p is me else p['champion']} ({i['name']})" for p in team for i in p["items"]
               if "Wounds" in (sd.items.get(i["id"]) or {}).get("text", "")]
    out.append("HEALING CUTS ON YOUR TEAM: " + (", ".join(cutters) if cutters else
                                                "nobody holds an item that applies Wounds (40% less healing)") + ".")
    return out
