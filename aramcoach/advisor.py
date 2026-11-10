"""Builds the prompts and turns Claude's answers into validated plans.

Every request type shares one system prompt and asks for JSON by instruction instead of an
API-enforced schema. A schema is part of the cached prompt prefix, so one schema per request
type would mean one cache entry per type, each going cold between uses. With a single shared
prefix, the frequent plan requests keep the cache warm for everything else.
"""
from __future__ import annotations

import json
import re

from . import llm
from .static_data import catalog_family_for, norm

SYSTEM_PROMPT = """\
You are the in-game coach for one League of Legends player in ARAM and ARAM: Mayhem (Howling Abyss: one lane, constant team fights).

# The player
The player is new to the game and says the number of items and augments is overwhelming. They do not know what most items do, or why one is better than another in a given game. They read your advice on a small panel beside the game, mostly while dead or between fights, so it has to be understood at a glance. Tell them exactly what to build and how to play this champion against these specific enemies. Use plain words. When a game term is unavoidable, add a few words saying what it means.

# What you receive
Each request is a snapshot from the game's local API: the player's champion, level, gold, items and stats; every ally and enemy with champion, level, score and items; recent kills; a whole-game count of which enemies have killed the player; reference notes on the champions' abilities; and the plan you gave earlier, when there is one. The item and champion data in the request and in the catalog below is current for this patch. Trust it over what you remember, because items change between patches.

Limits of the data:
- Enemy items are what the scoreboard shows.
- Real stats exist for the player only. Each enemy's "estimated minimum stats" line is computed from base stats, level and item stat lines. It leaves out champion passives, augments, item passives and anything the line itself says is missing, so the real values are higher, sometimes by hundreds of health. Use these numbers for your own reasoning only. Never show one to the player as a fact: a figure like "his 2259 health" is wrong on their screen and costs their trust. Describe the enemy in words instead, such as "he has built a lot of health", or say "at least about 2,300".
- There are no damage or healing totals, no enemy health and no cooldowns.
- The "numbers by rank" in the champion notes are base values per ability rank from a community dataset. They come before the per-champion adjustments ARAM applies and can lag a patch. Use them in preference to memory when you estimate damage or healing, and still treat the result as an estimate.
- Augments are not reported by the game. The coach learns them in three ways: an augment that replaces a summoner spell shows in that player's spell slot; the player's own augments are read from the offer on their screen; and other players' augments are read when the player points at them on the scoreboard. These are listed under "augments seen". The list is usually incomplete, so never assume a player has no others.

Games are normally five against five, but custom games can be smaller, down to one against one. The snapshot states the team sizes. Plan only around the allies and enemies it lists. With no allies, items and advice that depend on a teammate do not apply, and the player has to deal the damage and survive alone.

ARAM facts that shape the advice: players can shop only at the start and while dead, nobody can return to base to heal, gold and levels come quickly, and every fight happens in one narrow lane.

# Request types
The first line of a request names its type. Answer in the format given for that type.

## REQUEST: plan
Asks for the full plan. The player is in a live match and is waiting on this answer, often with a death timer running, so speed matters: decide from what is in front of you and start writing. A good plan now beats a perfect plan ten seconds late, and the duels are quick judgments, not calculations.
Answer with one JSON object and nothing else: no Markdown fence and no text before or after it. Use exactly these keys, in this order:
{"headline": string, "build_order": [{"item_id": integer, "name": string, "why": string}], "next_item_why": string, "how_to_play": [string], "threats": [{"champion": string, "danger": string, "answer": string}], "duels": [{"champion": string, "verdict": "favored" or "even" or "avoid", "fight_when": string, "why": string}], "scaling": {"goal": string, "power_spikes": [string], "augments_to_look_for": [string]}, "skill_order": string, "changed": string}

build_order is the list of finished items the player should end the game with, in the order to complete them. Six items fill the inventory, and one of them is normally boots. Include items the player already owns so the panel can mark them as done. List finished items only: a program works out which components the player can afford with their current gold, so components are not your job. Every item_id must come from the catalog below, which lists every item that can be finished in this mode. Give each item a `why` of at most 15 words that is specific to this game.

Choose the build for this game, not a generic one for the champion. What matters is what kind of damage the enemy team deals and who deals most of it, which enemies are ahead, how much they heal or shield, how tanky they are, how much crowd control they have, what the player's own team is missing, and what this champion needs in order to function. Reorder or swap items when the snapshot gives a reason, such as an enemy pulling ahead or stacking resistances.

The snapshot may list the items in the player's in-game item set, which was written before the match. The player buys those with one click; any other item they have to search for by name. When two items are close in value, choose the one in the set. Do not pass over a clearly better item because it is missing from the set.

Keep the plan steady. The player follows it purchase by purchase, and a build that shifts on every update is confusing. When you do change it, say what changed and why in `changed`, in one sentence. Otherwise leave `changed` empty.

The other fields:
- headline: one short sentence on the player's job in this game.
- next_item_why: one or two sentences on why the next unfinished item comes next, tied to something visible in this game.
- how_to_play: three to five short instructions for this champion against these enemies: where to stand, which ability to use on whom, who to stay away from, when to commit. Concrete beats general. "Stay behind Garen and throw Q at whoever walks at you" helps; "position well" does not.
- threats: up to three enemies who are most dangerous to this player right now, each with what they do to the player and what to do about it.
- duels: one entry for every enemy listed. It answers the question "could I win a fight against this enemy alone, right now?" at the current levels and items, with both starting the fight at the health stated. `verdict` is "favored", "even" or "avoid" for a fight where both are at full health. `fight_when` says how low that enemy's health must be before a one-on-one is worth taking, as a rough share of their health bar, such as "below about 40% health", or "any time" or "never alone". `why` gives the deciding factor in at most 15 words, such as an ability to dodge or wait out. The player can see enemy health bars but you cannot, which is why the threshold is the useful form. These are your estimates from the kits, levels, items and stats, so lean cautious.
- scaling: how this player grows strong enough to take over fights as the game goes on. The build order, the augments and the ability order should all pull toward one identity, and this field names it. `goal` is one sentence on what the finished combination turns the champion into and what that lets the player do, such as "with three items your E removes their back line in one cast". `power_spikes` is two or three moments when the player becomes noticeably stronger and should start forcing fights, each one short sentence that names the level or item. `augments_to_look_for` is up to four augments from the augment list below that multiply what this build already does, each followed by a few words on why. Prefer augments that stack with ones the player already took. Shape all of it around what the enemies are building: scaling into something they have already countered is not scaling. In a mode without augments, leave `augments_to_look_for` empty.
- skill_order: which ability to rank up first, in one line, with the reason in a few words.

When the snapshot includes augments, for the player or anyone else, take them into account in the build, the play advice and the duels, and mention them where they change what you would otherwise say.

When the snapshot carries a focus from the review of the player's last game, work it into how_to_play where it fits this champion and this game. Leave it out where it does not fit.

## REQUEST: pregame
Comes from champion select or the loading screen, before the match. When no enemies are listed, the enemy team is not known yet. Answer with one JSON object like a plan, with two more keys at the end:
"title": a name for the build in at most 22 characters, such as "Tank Thresh".
"situational": up to five groups of finished items for enemy teams you cannot see yet, as [{"title": string, "item_ids": [integer]}]. Give each group a title the player can check by looking at the enemy team, such as "If they heal a lot" or "If most of their damage is magic", and up to six item ids from the catalog: the items you would swap into the build in that case, including a different first item if that case calls for one.
"pool": up to ten more finished item ids that could be right for this champion in some game and are not already listed above.
All of this is written into the in-game shop as an item set before the match loads, and the game may not let it change afterwards. Later plans are made with the enemy team known, and any item they name that is missing from the set is one the player has to search the shop for. So between the build, the groups and the pool, cover every item you might plausibly recommend for this champion. The build is also the plan until live data arrives. Leave `changed` empty. With no enemies listed, leave `threats` and `duels` empty.

## REQUEST: screen
Comes with a screenshot of the player's game, taken when they pressed the coach hotkey. Most often it shows an augment choice: several cards, each with a name and its effect text. Answer with one JSON object and nothing else:
{"kind": "augment_choice" or "other", "offered": [{"name": string, "summary": string}], "pick": string, "why": string, "note": string}
For an augment choice, read the cards. List each offered augment with its name exactly as written and a summary of its effect in at most 12 words. Put the one to take in `pick`. Choose the one that best serves the scaling goal in your previous plan and stacks with the augments the player already took, unless another card is plainly stronger in this game. Say why in one or two plain sentences in `why`, tied to this champion and this game. The player has only a few seconds, so the pick must be unambiguous. Use `note` only if the player should play or build differently after taking it; otherwise leave it empty.
If the screenshot shows something else, set kind to "other", leave `offered` and `pick` empty, and use `why` for the single most useful thing to tell the player given what is on screen.

## REQUEST: augments
The coach has read an augment offer off the player's screen. The request lists the augments on offer with their current effects. Answer with one JSON object and nothing else:
{"pick": string, "why": string, "reroll": string, "note": string}
- pick: the name of the one to take, exactly as listed.
- why: one or two plain sentences tied to this champion and this game.
- reroll: each card can be rerolled a limited number of times. If one of the offered augments is clearly poor for this player and a reroll could plausibly do better than your pick, say so in one short sentence that starts with "If you have a reroll". Otherwise leave it empty.
- note: only if the player should build or play differently after taking it; otherwise empty.
Choose the one that best serves the scaling goal in your previous plan and stacks with the augments the player already has, unless another is plainly stronger in this game. The player has only seconds, so decide quickly and be unambiguous.

## REQUEST: debrief
Comes after a match, with the final scoreboard from the game's own records: every player's score, damage dealt to champions, damage taken, healing, gold, items and augments. Unlike the live snapshots, these numbers are measured. Answer with one JSON object and nothing else:
{"verdict": string, "went_well": [string], "to_fix": [string], "build_review": string, "focus_next_game": string}
- verdict: one sentence on how the game went for the player and the main reason.
- went_well: one or two things, each tied to a number from the scoreboard.
- to_fix: up to three specific things to do differently next time, each tied to a number or to a choice visible in the data, such as deaths, damage compared with similar champions in the same game, or an item or augment choice.
- build_review: two or three sentences on whether the player's items and augments fit what the enemy team turned out to have, naming a better choice where there was one.
- focus_next_game: the single habit that would help most, in one sentence that still makes sense on a different champion.
Judge the player against their champion's job, not against the top damage dealer: a healer is measured by healing, assists and staying alive. Be honest and kind. The player is learning: a review that only praises teaches nothing, and one that only criticises will not be read.

## REQUEST: question
Carries something the player typed. Answer in plain text, not JSON, in under 90 words, using the snapshot and the current plan. The panel shows your answer as plain text, so write ordinary sentences with no Markdown, asterisks or bullet symbols.

When the player asks for numbers or a cost-benefit analysis, such as whether an item is worth its gold right now, you may use up to 200 words. Start with the verdict. Then give the few numbers it rests on and the assumptions behind them, for example how many times an ability is cast in a fight. The snapshot has no measured damage or healing, so say which figures are your estimates, and do not present an estimate as a measurement.
"""

AUGMENT_HEADER = """
# Augment list (ARAM: Mayhem)
Every augment the mode can offer, with current effects. The player is offered a few at a time and cannot choose which appear.
Format: name | tier | effect
"""

CATALOG_HEADER = """
# Item catalog
Format: id | name | total gold cost | tags | stats and effects
"""

PLAN_KEYS = ("headline", "build_order", "next_item_why", "how_to_play", "threats", "duels", "skill_order", "changed")
VERDICTS = ("favored", "even", "avoid")


def _clock(seconds: float) -> str:
    return f"{int(seconds) // 60}:{int(seconds) % 60:02d}"


def system_prompt_file(sd, family: str):
    """Write the system prompt for one item set and return its path.

    The text is identical for every call in a patch, so Claude serves it from the prompt cache.
    """
    augments = [f"{a['name']} | {a['tier']} | {a['description'][:260]}"
                for a in sorted(sd.augments_described(), key=lambda a: a["name"])]
    items = [f"{it['id']} | {it['name']} | {it['total']} | {', '.join(it['tags'])} | {it['text'][:420]}"
             for it in sd.catalog(family)]
    text = SYSTEM_PROMPT + AUGMENT_HEADER + "\n".join(augments) + "\n" + CATALOG_HEADER + "\n".join(items) + "\n"
    path = sd.dir / f"system_prompt_{family}.txt"
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")
    return path


# ---- rendering the snapshot ------------------------------------------------

def _player_line(p: dict, detail: bool, estimated: bool = False) -> str:
    tags = f" ({', '.join(p['tags'])})" if p["tags"] else ""
    items = ", ".join(i["name"] for i in p["items"]) or "none"
    line = (f"{p['champion']}{tags} level {p['level']} | K/D/A {'/'.join(map(str, p['kda']))}"
            f" | items worth {p['item_gold']} gold: {items}")
    if detail:
        if p["keystone"]:
            line += f" | main rune: {p['keystone']}"
        if p["spells"]:
            line += f" | summoner spells: {', '.join(p['spells'])}"
    if p.get("augments"):
        line += " | augments seen: " + ", ".join(a["name"] for a in p["augments"])
    if estimated and p.get("est"):
        line += " | estimated minimum stats (real values are higher): " + ", ".join(
            f"{value} {name}" for name, value in p["est"].items())
    return line


def _augment_lines(sd, fields: dict) -> list:
    """Describe whatever augment data the game API returned, resolving names or ids where possible."""
    if not fields:
        return []
    leaves = []

    def walk(node):
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, (str, int)) and not isinstance(node, bool):
            leaves.append(node)

    walk(fields)
    known = {}
    for leaf in leaves:
        entry = sd.augment(leaf)
        if entry and entry["name"]:
            known[entry["name"]] = entry
    lines = ["AUGMENT DATA FROM THE GAME API (raw fields):", "  " + json.dumps(fields, ensure_ascii=False)[:3000]]
    if known:
        lines.append("AUGMENT REFERENCE:")
        lines += [f"  {a['name']} ({a['tier']}): {a['description']}" for a in known.values()]
    return lines


def render_request(sd, state: dict, previous_plan: str, header: str) -> str:
    """Render the game snapshot as the text Claude reads."""
    me = state["me"]
    out = [header, f"MODE: {state['mode_label']}"
           + (f" (queue: {state['queue']['description']})" if state.get("queue") else "")
           + f" | game time {_clock(state['time'])}",
           f"TEAM SIZES: your side has {1 + len(state['allies'])}, the enemy side has {len(state['enemies'])}."
           + ("" if state["allies"] else " You have no allies in this game.")]
    if state.get("focus"):
        out.append(f"FOCUS FROM THE REVIEW OF THE PLAYER'S LAST GAME: {state['focus']}")
    out.append("")

    status = f"DEAD, respawns in {me['respawn']}s, shop is open" if me["dead"] else "alive"
    out.append(f"YOU: {_player_line(me, detail=True)}")
    out.append(f"  gold to spend: {me['gold']} | {status}")
    if me.get("ability_ranks"):
        out.append("  ability ranks: " + " ".join(f"{k}{me['ability_ranks'][k]}" for k in "QWER" if k in me["ability_ranks"]))
    if me.get("stats"):
        out.append("  stats: " + ", ".join(f"{k} {v:g}" for k, v in me["stats"].items()))
    for name in state.get("my_augments") or []:
        entry = sd.augment(name) or {"tier": "", "description": ""}
        how = ("assumed: it was your pick and the player did not say otherwise"
               if name in (state.get("assumed_augments") or []) else "taken, told by the player")
        out.append(f"  your augment ({how}): {name}"
                   + (f" ({entry['tier']}): {entry['description']}" if entry["description"] else ""))
    if state.get("item_set"):
        out.append("  items in your in-game item set: " + ", ".join(state["item_set"]))
    out.append("YOUR TEAM:")
    out += [f"  {_player_line(p, detail=False)}" for p in state["allies"]]
    out.append("ENEMY TEAM:")
    out += [f"  {_player_line(p, detail=True, estimated=True)}" for p in state["enemies"]]
    if not state["enemies"]:
        out.append("  not known yet")
    if state.get("killed_me"):
        ranked = sorted(state["killed_me"].items(), key=lambda kv: -(2 * kv[1]["kills"] + kv[1]["assists"]))
        out.append("WHO HAS KILLED YOU THIS GAME: "
                   + "; ".join(f"{champ}: {t['kills']} kills, {t['assists']} assists" for champ, t in ranked))

    if state["events"]:
        out.append("RECENT EVENTS:")
        out += [f"  {_clock(e['time'])} {e['text']}" for e in state["events"]]

    out += _augment_lines(sd, state.get("augment_fields") or {})
    revealed = {a["name"]: a for p in [me] + state["allies"] + state["enemies"] for a in p.get("augments") or []}
    if revealed:
        out.append("AUGMENTS OTHER PLAYERS ARE KNOWN TO HAVE (seen in a spell slot, or read from the scoreboard):")
        out += [f"  {a['name']} ({a['tier']}): {a['description']}" for a in revealed.values()]

    out.append("CHAMPION NOTES:")
    for p, role in [(me, "you")] + [(e, "enemy") for e in state["enemies"]]:
        notes = sd.champion_notes(p["champ_id"]) if p["champ_id"] else None
        if not notes:
            continue
        out.append(f"  {p['champion']} ({role}): {notes['passive']}")
        out += [f"    {s}" for s in notes["spells"]]
        tips = notes["allytips"] if role == "you" else notes["enemytips"]
        out += [f"    tip: {t}" for t in tips[:3]]

    if previous_plan:
        out += ["", previous_plan]
    return "\n".join(out)


def plan_summary(advice: dict, game_time: float) -> str:
    """One paragraph describing the current plan, sent back to Claude so later plans stay consistent."""
    order = " > ".join(b["name"] for b in advice["build_order"])
    goal = (advice.get("scaling") or {}).get("goal")
    return (f"YOUR PREVIOUS PLAN (given at {_clock(game_time)}): {advice['headline']} "
            f"Build order: {order}. Skill order: {advice['skill_order']}"
            + (f" Scaling goal: {goal}" if goal else ""))


# ---- reading Claude's answers ----------------------------------------------

def _parse_json(text: str) -> dict:
    """Parse a JSON object from Claude's answer, tolerating a stray code fence or surrounding text."""
    start, end = text.find("{"), text.rfind("}")
    try:
        obj = json.loads(text[start: end + 1]) if start >= 0 and end > start else None
    except ValueError:
        obj = None
    if not isinstance(obj, dict):
        raise llm.LLMError("Claude's answer was not the expected JSON.")
    return obj


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _validate(advice: dict, catalog: list) -> dict:
    """Normalise a plan. Unknown items are dropped, and every field ends up with the right type."""
    by_id = {it["id"]: it for it in catalog}
    by_name = {norm(it["name"]): it for it in catalog}
    build, seen = [], set()
    for entry in advice.get("build_order") or []:
        if not isinstance(entry, dict):
            continue
        # Names win over ids when they disagree: Claude is more reliable with names than numbers.
        item = by_name.get(norm(entry.get("name", ""))) or by_id.get(entry.get("item_id"))
        if item and item["id"] not in seen:
            seen.add(item["id"])
            build.append({"item_id": item["id"], "name": item["name"], "why": _text(entry.get("why"))})
    if not build:
        raise llm.LLMError("Claude's plan contained no items from the catalog.")
    scaling = advice.get("scaling") if isinstance(advice.get("scaling"), dict) else {}
    return {
        "headline": _text(advice.get("headline")),
        "build_order": build,
        "next_item_why": _text(advice.get("next_item_why")),
        "how_to_play": [_text(s) for s in advice.get("how_to_play") or [] if _text(s)],
        "threats": [{k: _text(t.get(k)) for k in ("champion", "danger", "answer")}
                    for t in advice.get("threats") or [] if isinstance(t, dict)],
        "duels": [{"champion": _text(d.get("champion")),
                   "verdict": d.get("verdict") if d.get("verdict") in VERDICTS else "even",
                   "fight_when": _text(d.get("fight_when")), "why": _text(d.get("why"))}
                  for d in advice.get("duels") or [] if isinstance(d, dict)],
        "scaling": {
            "goal": _text(scaling.get("goal")),
            "power_spikes": [_text(s) for s in scaling.get("power_spikes") or [] if _text(s)][:4],
            "augments_to_look_for": [_text(s) for s in scaling.get("augments_to_look_for") or [] if _text(s)][:5],
        },
        "skill_order": _text(advice.get("skill_order")),
        "changed": _text(advice.get("changed")),
    }


def _streamed_build(text: str):
    """Return the build_order list once its array has fully arrived in the streamed JSON, else None."""
    key = text.find('"build_order"')
    start = text.find("[", key) if key >= 0 else -1
    if start < 0:
        return None
    depth, in_string, escaped = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start: i + 1])
                except ValueError:
                    return None
    return None


def _streamed_headline(text: str) -> str:
    match = re.search(r'"headline"\s*:\s*("(?:[^"\\]|\\.)*")', text)
    try:
        return json.loads(match.group(1)) if match else ""
    except ValueError:
        return ""


# ---- requests --------------------------------------------------------------

def get_advice(sd, state: dict, previous_plan: str, trigger: str, on_partial=None):
    """Ask Claude for a full plan. Returns (advice, meta).

    on_partial: optional callback. It is called once, with a plan holding only the headline
      and build order, as soon as those have streamed in. The build order is what the player
      needs first, and it arrives several seconds before the full answer.
    """
    family = catalog_family_for(state["item_ids"])
    catalog = sd.catalog(family)
    prompt = render_request(sd, state, previous_plan, f"REQUEST: plan (reason for this update: {trigger})")
    sent = False

    def on_text(received: str):
        nonlocal sent
        if sent:
            return
        build = _streamed_build(received)
        if build is None:
            return
        sent = True
        try:
            on_partial(_validate({"headline": _streamed_headline(received), "build_order": build}, catalog))
        except llm.LLMError:
            pass                      # nothing usable yet; the full answer follows

    text, meta = llm.run(system_prompt_file(sd, family), prompt, on_text=on_text if on_partial else None)
    return _validate(_parse_json(text), catalog), meta


def get_pregame(sd, state: dict):
    """Ask Claude for the plan before the match, from champion picks alone. Returns (advice, meta).

    The advice is a normal plan plus `title` and `situational`, which feed the in-game item set.
    """
    catalog = sd.catalog("std")
    prompt = render_request(sd, state, "", "REQUEST: pregame")
    text, meta = llm.run(system_prompt_file(sd, "std"), prompt)
    raw = _parse_json(text)
    advice = _validate(raw, catalog)
    ids = {it["id"] for it in catalog}
    advice["title"] = _text(raw.get("title"))[:28]
    advice["pool"] = [i for i in raw.get("pool") or [] if i in ids][:12]
    advice["situational"] = [
        {"title": _text(s.get("title"))[:60], "item_ids": [i for i in s.get("item_ids") or [] if i in ids][:6]}
        for s in raw.get("situational") or [] if isinstance(s, dict) and _text(s.get("title"))
    ][:5]
    return advice, meta


def read_screen(sd, state: dict, previous_plan: str, image: bytes):
    """Ask Claude to read a screenshot of the game, usually an augment choice. Returns (result, meta)."""
    family = catalog_family_for(state["item_ids"])
    prompt = render_request(sd, state, previous_plan, "REQUEST: screen")
    text, meta = llm.run(system_prompt_file(sd, family), prompt, image=image)
    raw = _parse_json(text)
    offered = [{"name": _text(o.get("name")), "summary": _text(o.get("summary"))}
               for o in raw.get("offered") or [] if isinstance(o, dict) and _text(o.get("name"))]
    return {
        "kind": "augment_choice" if raw.get("kind") == "augment_choice" and offered else "other",
        "offered": offered, "pick": _text(raw.get("pick")), "why": _text(raw.get("why")), "note": _text(raw.get("note")),
    }, meta


def choose_augment(sd, state: dict, previous_plan: str, offer: list):
    """Ask Claude which of the augments on offer to take. Text only: the offer was already read locally.

    offer: [{name, tier, description}] as read from the screen. Returns (result, meta), where result is
    {pick, why, reroll, note} and pick is one of the offered names or empty.
    """
    family = catalog_family_for(state["item_ids"])
    listing = "\n".join(f"  {a['name']} ({a['tier']}): {a['description']}" for a in offer)
    prompt = (render_request(sd, state, previous_plan, "REQUEST: augments")
              + "\n\nAUGMENTS ON OFFER (read from the player's screen):\n" + listing)
    text, meta = llm.run(system_prompt_file(sd, family), prompt)
    raw = _parse_json(text)
    names = {norm(a["name"]): a["name"] for a in offer}
    return {
        "pick": names.get(norm(_text(raw.get("pick"))), ""), "why": _text(raw.get("why")),
        "reroll": _text(raw.get("reroll")), "note": _text(raw.get("note")),
    }, meta


def render_debrief(summary: dict, last_plan: str) -> str:
    """Render a finished match's scoreboard as the text Claude reviews."""
    players = summary["players"]
    me = next(p for p in players if p["me"])
    mine = [p for p in players if p["team"] == me["team"]]
    theirs = [p for p in players if p["team"] != me["team"]]

    def line(p):
        return (f"  {'YOU: ' if p['me'] else ''}{p['champion']} level {p['level']} | K/D/A {'/'.join(map(str, p['kda']))}"
                f" | damage to champions {p['damage']} | damage taken {p['taken']} | healing {p['healing']}"
                f" | gold {p['gold']} | augments: {', '.join(p['augments']) or 'none'}"
                f" | items: {', '.join(p['items']) or 'none'}")

    mode = {"KIWI": "ARAM: Mayhem", "ARAM": "ARAM"}.get(summary.get("mode"), summary.get("mode") or "unknown mode")
    out = ["REQUEST: debrief",
           f"MODE: {mode} | length {summary['minutes']} minutes | result for the player: {'WIN' if me['win'] else 'LOSS'}",
           f"TEAM SIZES: your side had {len(mine)}, the enemy side had {len(theirs)}.",
           "YOUR TEAM:"] + [line(p) for p in mine] + ["ENEMY TEAM:"] + [line(p) for p in theirs]
    if last_plan:
        out += ["", "THE COACH'S LAST PLAN DURING THIS MATCH: " + last_plan]
    return "\n".join(out)


def get_debrief(sd, summary: dict, last_plan: str = ""):
    """Ask Claude to review a finished match from its post-game record. Returns (review, meta)."""
    text, meta = llm.run(system_prompt_file(sd, "std"), render_debrief(summary, last_plan))
    raw = _parse_json(text)
    strings = lambda key, limit: [_text(s) for s in raw.get(key) or [] if _text(s)][:limit]
    review = {
        "verdict": _text(raw.get("verdict")), "went_well": strings("went_well", 3), "to_fix": strings("to_fix", 4),
        "build_review": _text(raw.get("build_review")), "focus_next_game": _text(raw.get("focus_next_game")),
    }
    if not review["verdict"]:
        raise llm.LLMError("Claude's review was empty.")
    return review, meta


def _loose(text: str) -> str:
    """Lowercase, drop apostrophes, and turn other punctuation into spaces, padded for whole-word matching."""
    text = re.sub(r"[^a-z0-9]+", " ", text.lower().replace("'", "").replace("’", ""))
    return f" {text.strip()} "


def augments_mentioned(sd, text: str) -> list:
    """Augments whose names appear in the text, so Claude can be told what they do."""
    haystack = _loose(text)
    return [a for a in sd.augments_described() if len(a["name"]) >= 4 and _loose(a["name"]) in haystack]


def answer_question(sd, state: dict, previous_plan: str, question: str):
    """Ask Claude a free-form question about the current game. Returns (text, meta).

    If the question names augments, their descriptions are attached.
    """
    family = catalog_family_for(state["item_ids"])
    prompt = render_request(sd, state, previous_plan, "REQUEST: question") + f"\n\nTHE PLAYER ASKS: {question}"
    mentioned = augments_mentioned(sd, question)
    if mentioned:
        prompt += "\n\nAUGMENTS NAMED IN THE QUESTION (current descriptions):\n" + "\n".join(
            f"  {a['name']} ({a['tier']}): {a['description']}" for a in mentioned)
    text, meta = llm.run(system_prompt_file(sd, family), prompt)
    return text.strip(), meta
