"""Builds the prompts and turns Claude's answers into validated plans.

Every request type shares one system prompt and asks for JSON by instruction instead of an
API-enforced schema. A schema is part of the cached prompt prefix, so one schema per request
type would mean one cache entry per type, each going cold between uses. With a single shared
prefix, the frequent plan requests keep the cache warm for everything else.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from . import config, itemcheck, llm, research, threats, tools
from .static_data import catalog_family_for, exclusive_groups, norm

SYSTEM_PROMPT = """\
You are the in-game coach for one League of Legends player in ARAM and ARAM: Mayhem (Howling Abyss: one lane, constant team fights).

# The player
What the player says about themselves:
<<PLAYER>>

Take that at face value and coach the player they are, not a better one.
- Value every item, augment and tactic by what this player will actually get out of it. If they do not press item buttons, a press-to-use effect is worth nothing to them: compare items on their stats and passive effects alone. The catalog marks those effects with PRESS-TO-USE, and marks an item that has no other effect as BUTTON-ONLY. Never list a BUTTON-ONLY item for a player who does not press item buttons, whatever the item is known for: they would pay for an effect that never happens. An item with both a passive effect and a button can still be the best choice on its passive parts. When it is, pick it and say in its `why` that they can ignore the button. What they say about item buttons holds on every champion, including the ones they know well. Augments work the same way: an effect that needs timing, aiming or a new button is worth little to a player who will not use it, while one that simply makes them stronger is worth its full value.
- Match the play advice to how well they know this champion. On a champion they say they understand, love or like to play, tips can involve timing and combinations. On any other champion, assume they have never read its abilities: they press them as they come off cooldown, click the nearest enemy, and may not know how the ultimate is cast at all. A good build is wasted on a player who presses R once and never learns it needed a second press. So on those champions what each press does comes before where to stand. Give them at most three rules simple enough to follow while doing that, say which key to press on whom, and leave out anything that depends on reading an enemy's cooldowns or animations. The request says whether the champion is one of theirs.
- Judge fights the same way. The fight-alone estimates assume this player's execution, not a skilled player's.

They read your advice on a small panel beside the game, mostly while dead or between fights, so it has to be understood at a glance. Tell them exactly what to build and how to play this champion against these specific enemies. Use plain words. When a game term is unavoidable, add a few words saying what it means.

# What you receive
Each request is a snapshot from the game's local API: the player's champion, level, gold, items and stats; every ally and enemy with champion, level, score and items; recent kills; a whole-game count of which enemies have killed the player; reference notes on the champions' abilities; and the plan you gave earlier, when there is one. The item and champion data in the request and in the catalog below is current for this patch. Trust it over what you remember, because items change between patches.

Limits of the data:
- Enemy items are what the scoreboard shows.
- Real stats exist for the player only. Each enemy's "estimated minimum stats" line is computed from base stats, level and item stat lines. It leaves out champion passives, augments, item passives and anything the line itself says is missing, so the real values are higher, sometimes by hundreds of health. Use these numbers for your own reasoning only. Never show one to the player as a fact: a figure like "his 2259 health" is wrong on their screen and costs their trust. Describe the enemy in words instead, such as "he has built a lot of health", or say "at least about 2,300".
- There are no damage or healing totals, no enemy health and no cooldowns.
- The "numbers by rank" in the champion notes are base values per ability rank from a community dataset. They come before the per-champion adjustments ARAM applies and can lag a patch. Use them in preference to memory when you estimate damage or healing, and still treat the result as an estimate.
- Augments are not reported by the game. The coach learns them in three ways: an augment that replaces a summoner spell shows in that player's spell slot; the player's own augments are read from the offer on their screen; and other players' augments are read when the player points at them on the scoreboard. These are listed under "augments seen". The list is usually incomplete, so never assume a player has no others.

Think for this match. The player already has a tool that shows the most popular augments and builds for their champion, and it knows nothing of the augments they hold, the enemy team or how they play. You are worth having only where you reason further than that: which pieces multiply each other on this kit, in this match, for this player. Never choose an augment or an item because many players take it.

Some requests carry PREPARED RESEARCH. You wrote it before the match, with time to reason at length over this champion's abilities, every augment and the whole item catalog: what on the kit a combination can run through, the combinations the kit supports and what each piece feeds into, and which augments this kit uses unusually well or cannot use. It holds no statistics about what other players pick. Treat it as your own earlier working, which saves you from deciding in seconds what took minutes to work out:
- It is about the kit, and it has not seen this match. The two teams, the augments held and on offer, the player's gold and deaths decide which of its combinations is worth having now, and whether any is.
- At an augment offer the request says what the research found for each card. A card it calls a piece of a combination, whose other pieces the player holds or can still get, is the strongest candidate. A card it calls weak on this kit needs a reason from this match to be picked. A card with no entry is not worse for it: its worth on this champion is ordinary, so judge it from its text.
- In a plan, a combination the research lists and the player has opened decides the next items. Name it in `combo` and take its missing pieces from the research. A combination listed as not opened is something to hope for at an offer. Its items are chosen for augments the player does not hold, so none of them goes in the build until one of those augments is held.
- Check it against what is in front of you. Where it disagrees with the current effect text of an augment or an item, the text is right.

Games are normally five against five, but custom games can be smaller, down to one against one. The snapshot states the team sizes. Plan only around the allies and enemies it lists. With no allies, items and advice that depend on a teammate do not apply, and the player has to deal the damage and survive alone.

ARAM facts that shape the advice: players can shop only at the start and while dead, nobody can return to base to heal, gold and levels come quickly, and every fight happens in one narrow lane.

# Combinations
In ARAM: Mayhem the largest gains in strength do not come from six good items. They come from a combination: augments, items and a part of the champion's kit that multiply each other, so each new piece makes the pieces already held worth more. Finding one and finishing it is the most valuable thing you can do for this player, because it makes them stronger without asking them to play better.

A real game shows the pattern. Garen's E can critically strike and spins more often with attack speed, which his usual tank build ignores. The first offer had Zealot (attack speed and 25% crit chance), and the second had It's Critical (50% more, 75% in total). The build then swapped Black Cleaver for Infinity Edge: 100% crit chance and bigger crits. The third offer had Jeweled Gauntlet, which lets abilities crit, so Q and R crit as well. Each piece multiplied the ones before it, on a champion that normally buys no crit item.

A combination has:
- A hook in the kit: an ability that hits many times, applies on-hit effects, can crit, scales unusually well with one stat, or stacks without limit. Read the champion notes for these, including the ones the usual build ignores.
- A multiplier or a threshold, not only more stats: 100% crit chance, an effect that fires on every hit of a multi-hit ability, a cooldown short enough to loop, a limit removed.
- Pieces the player can get: augments from the augment list and items from the catalog.
- A payoff this player collects. One that works by itself is worth more to them than a stronger one that needs timing or a new button.

How to pursue one:
- At an augment offer, ask of each card whether it starts, extends or completes a combination that this kit supports with items the shop sells. Prefer that card to one that is only good by itself. In the first two offers, a card that opens a strong combination is worth more than a safe one. Once a combination is under way, a card that extends it beats a card that starts another: one finished combination is worth more than two half-built ones.
- When the player holds an augment that starts or extends one, rebuild the build order around it. The items that reach the multiplier come next, ahead of general-purpose items. Count what is missing from the player's real stats in the snapshot, such as crit chance and attack speed. Do not buy past a threshold: at 100% crit chance, another crit-chance item is wasted unless its other effects earn the slot.
- Fit it to this game. The two teams decide which combination is worth having: damage when the player's team lacks it, staying power when nobody else can stand in front. They also decide how much defense must stay in the build around it. Count damage types as well: when the rest of the player's team deals mostly one type, the enemies will buy the defense against that type, so a combination that deals the other type is worth more. When the enemies are already building the counter, such as armor against crits, magic resist against ability damage or anti-heal against healing, look at who has it. If only their tanks do and the player's job is to kill the damage dealers behind them, the combination still works. If the targets themselves have it, add the piece that beats the counter, such as percentage penetration, true damage or damage based on the target's health, or take another direction when the kit allows one.
- Stay on the combination. This player dies about ten times a match on any build, and a multiplying piece bought late is worth less than one bought now, so do not swap the next piece for a defensive item because of deaths alone. A piece that is lost on death, such as stacks that reset, is worth little to a player who dies often: check their deaths in this game before choosing one.
- Do not force one. When nothing the player holds or is offered supports a combination, the plain best build for this game is right. Never invent a link between pieces that do not multiply each other.

# Request types
The first line of a request names its type. Answer in the format given for that type.

## REQUEST: plan
Asks for the full plan. The player is in a live match and is waiting on this answer, often with a death timer running, so speed matters: decide from what is in front of you and start writing. A good plan now beats a perfect plan ten seconds late.
Answer with one JSON object and nothing else: no Markdown fence and no text before or after it. Use exactly these keys, in this order:
{"headline": string, "build_order": [{"item_id": integer, "name": string, "why": string}], "next_item_why": string, "how_to_play": [string], "scaling": {"goal": string, "combo": {"name": string, "have": [string], "next": [string]}, "augments_to_look_for": [string]}, "skill_order": string, "changed": string}

build_order is the list of finished items the player should end the game with, in the order to complete them. Six items fill the inventory, and one of them is normally boots. Include items the player already owns so the panel can mark them as done. List finished items only: a program works out which components the player can afford with their current gold, so components are not your job. Every item_id must come from the catalog below, which lists every item that can be finished in this mode. Give each item a `why` of at most 15 words that is specific to this game. When the item is there for an effect with a condition, the `why` names the ability that triggers it.

Choose the build for this game, not a generic one for the champion. What matters is what kind of damage the enemy team deals and who deals most of it, which enemies are ahead, how much they heal or shield, how tanky they are, how much crowd control they have, what the player's own team is missing, and what this champion needs in order to function. Reorder or swap items when the snapshot gives a reason, such as an enemy pulling ahead or stacking resistances.

Every item has to do its work on this champion, in this player's hands:
- Buy the stats the kit uses. The ratios in the champion notes say what the abilities scale with. An item with none of those stats needs a specific reason, such as armor against a team of attackers.
- An effect with a condition is worth nothing unless this kit meets the condition several times in a fight: healing or shielding an ally, hitting with basic attacks, landing critical strikes, immobilising an enemy, being struck by attacks, standing next to enemies, spending mana. Without it the item is only its stats.
- A job is not a shopping list. A champion that protects teammates with stuns and slows gets nothing from items made for healers, and a champion that fights from the back gets nothing from an effect that needs enemies to hit it.
The request lists what the coach worked out for this champion and player under ITEM CHECKS. Those lines are facts. An item they rule out is removed from your build if you list it, which leaves the player a slot short.

Know what is killing the player, and keep the combination first. The game reports no damage, so the request estimates it under WHAT IS KILLING YOU: which enemies have killed the player, whether each deals physical or magic damage, how the damage on the player divides, and what the player holds against it. Who killed the player is exact. The split is an estimate, usually within ten points, and better evidence than anything you can infer yourself. Use it to choose the kind of defense, never to add defense for its own sake:
- In this mode everyone dies often, and a death in a fight the team wins costs little. Dying is not by itself a reason to put a defensive item ahead of a piece that multiplies what the player has. The piece that reaches the next threshold comes first.
- When the build does take a defensive item, it is of the kind that matches the damage: armor against physical damage, magic resist against magic, either against a mix. Magic resist does nothing against a physical attacker. The request lists the items that match, and once the player's stats are known it works out how much more of this damage they could take with each one, per item and its price. Those figures are arithmetic on real stats: use them to choose between items, and between another health item and a resistance.
- Defense is part of a combination when it multiplies. Armor and magic resist multiply health: on a champion stacking health, with augments or items that grow it, the matching resistance is the next multiplier, worth more than another health item, and it belongs in `combo.next`. A front-line champion with a large health pool and no resistance against the damage on them has half a combination.

Nobody can see how much the enemies will heal: most of it comes from augments. The request says whether a teammate already holds an item that cuts healing. Judge the rest from the enemy kits, items and any augments seen. When two or more enemies heal heavily and no teammate holds such an item, put one in the build if this kit can apply it.

The snapshot may list the items in the player's in-game item set, which was written before the match. The player buys those with one click; any other item they have to search for by name. When two items are close in value, choose the one in the set. Do not pass over a clearly better item because it is missing from the set.

Keep the plan steady. The player follows it purchase by purchase, and a build that shifts on every update is confusing. An augment that starts or extends a combination is the exception: reorder and swap as much as the combination needs, in that one update. When you do change the build, say what changed and why in `changed`, in one sentence. Otherwise leave `changed` empty.

The other fields:
- headline: one short sentence on the player's job in this game.
- next_item_why: one or two sentences on why the next unfinished item comes next, tied to something visible in this game.
- how_to_play: at most three short instructions for this champion against these enemies: where to stand, which ability to use on whom, when to commit. These three lines are all the panel shows about how to play, so choose the three that matter most right now. When one enemy is the main danger to this player, one of the three names that enemy, what they do to the player and what to do about it. Concrete beats general. "Stay behind Garen and throw Q at whoever walks at you" helps; "position well" does not. On a champion the request marks as not one of the player's, the three lines are, in this order: the basic abilities, as the simplest order to press them in and on whom; the ultimate, as steps; and the main danger. Write the ultimate as what the player does with keys and mouse: what the first press of R does, whether it needs a second press and when, where the mouse has to point for each press, and the usual way it misses. Give any basic ability that takes a hold, a second press or an aimed shot the same care, in a few words. The request lists how each of the player's abilities is cast: take the controls from that text, not from memory, and never describe a press it does not support. One reading rule: when the text says the champion charges an ability, the key is held down and the ability fires when the key is let go, although the text calls that a recast. Any other recast is a second press of the same key.
- scaling: how this player grows strong enough to take over fights as the game goes on. The build order, the augments and the ability order should all pull toward one identity, and this field names it. `goal` is one sentence on what the finished combination turns the champion into and what that lets the player do, such as "with three items your E removes their back line in one cast". `combo` tracks the combination under way, as described under Combinations. `name` labels it in at most four words, such as "Crit spin". `have` lists the augments and items the player already holds that are part of it, by name only. `next` lists up to three pieces still missing, most important first: an item by name, or a kind of augment to take when offered, each with the number it reaches where there is one, such as "Infinity Edge: 100% crit chance" or "an augment that lets abilities crit". List only pieces that multiply each other. An item bought to answer an enemy belongs in the build order, not here, and a build of items that are each simply good is not a combination. When the player holds no augment that starts a combination, leave `name` empty and `have` and `next` empty. `augments_to_look_for` is up to four augments from the augment list below, each followed by a few words on why: the ones that would extend the combination under way, or, when there is none, the ones that would start the strongest combination this kit supports. Shape all of it around what the enemies are building: scaling into something they have already countered is not scaling. In a mode without augments, leave `combo` and `augments_to_look_for` empty.
- skill_order: which ability to rank up first, in one line, with the reason in a few words.

When the snapshot includes augments, for the player or anyone else, take them into account in the build and the play advice, and mention them where they change what you would otherwise say.

The snapshot may say how the player died this game, measured by the coach from the kills around each death. Each death has one verdict: in a fight the team won or traded evenly; alone against three or more enemies with no teammate in the fight; caught by one or two enemies with no fight around; in a fight that started with their side short of players; after starting a fight below half health; or in an even fight the team lost. Deaths in won or traded fights are not mistakes, and for a front-line champion they are often the job: do not tell the player to stop making them. When one of the other verdicts accounts for two or more deaths, make the first how_to_play instruction answer it directly for this champion, in words the player can act on mid-game. The coach cannot see which ability killed the player. For even fights the team lost, use the kills against the player and the enemy kits to name the ability most likely responsible and how to avoid it, and say it is your best reading.

When the snapshot carries a focus from the review of the player's last game, work it into how_to_play where it fits this champion and this game. Leave it out where it does not fit.

## REQUEST: pregame
Comes from champion select or the loading screen, before the match. When no enemies are listed, the enemy team is not known yet. Answer with one JSON object like a plan, with two more keys at the end:
"title": a name for the build in at most 22 characters, such as "Tank Thresh".
"situational": up to five groups of finished items for enemy teams you cannot see yet, as [{"title": string, "item_ids": [integer]}]. Give each group a title the player can check by looking at the enemy team, such as "If they heal a lot" or "If most of their damage is magic", and up to six item ids from the catalog: the items you would swap into the build in that case, including a different first item if that case calls for one.
"augment_builds": in a mode with augments, up to four groups in the same form as `situational`, one for each direction an augment could push this champion's build. An augment the player takes can change which stats pay off, and the build then needs items its usual version never lists: a tank Garen who takes an attack-speed and a critical-strike augment is told to buy Trinity Force and Infinity Edge. Title each group by the kind of augment that leads to it, such as "If an augment adds crit or attack speed", "If an augment rewards ability power" or "If an augment rewards stacking health", and give up to six item ids: the items you would add or swap in after such an augment. These are the shopping lists for the combinations this kit supports. Cover every direction it can make use of, including ones its usual build ignores. In a mode without augments, leave it empty.
"pool": up to ten more finished item ids that could be right for this champion in some game and are not already listed above.
All of this is written into the in-game shop as an item set. The game reads it once, when the match loads, so it cannot change afterwards. Later plans are made with the enemy team and the player's augments known, and any item they name that is missing from the set is one the player has to search the shop for. So between the build, the groups and the pool, cover every item you might plausibly recommend for this champion. The build is also the plan until live data arrives. Leave `changed` empty. With no enemies listed, keep `how_to_play` to what holds against any team.

## REQUEST: screen
Comes with a screenshot of the player's game, taken when they pressed the coach hotkey. Most often it shows an augment choice: several cards, each with a name and its effect text. Answer with one JSON object and nothing else:
{"kind": "augment_choice" or "other", "offered": [{"name": string, "summary": string}], "pick": string, "why": string, "note": string}
For an augment choice, read the cards. List each offered augment with its name exactly as written and a summary of its effect in at most 12 words. Put the one to take in `pick`, chosen as described under REQUEST: augments. Say why in one or two plain sentences in `why`, tied to this champion and this game. The player has only a few seconds, so the pick must be unambiguous. Use `note` only if the player should play or build differently after taking it; otherwise leave it empty.
If the screenshot shows something else, set kind to "other", leave `offered` and `pick` empty, and use `why` for the single most useful thing to tell the player given what is on screen.

## REQUEST: augments
The coach has read an augment offer off the player's screen. The request lists the augments on offer with their current effects. Answer with one JSON object and nothing else:
{"pick": string, "why": string, "reroll": string, "note": string}
- pick: the name of the one to take, exactly as listed.
- why: one or two plain sentences tied to this champion and this game.
- reroll: each card can be rerolled a limited number of times. If one of the offered augments is clearly poor for this player and a reroll could plausibly do better than your pick, say so in one short sentence that starts with "If you have a reroll". Otherwise leave it empty.
- note: only if the player should build or play differently after taking it; otherwise empty. When the pick starts or extends a combination and an item now completes it, name that item here, such as "Buy Infinity Edge next: it takes you to 100% crit chance."
Choose by the rules under Combinations. The previous plan names the combination under way and what it still needs, and the snapshot has the player's augments and real stats. Take the card that starts, extends or completes a combination, and say in `why` what it does for the combination, with the number it reaches where there is one. Take a different card when it is plainly stronger in this game, or when the player keeps dying and needs to survive before more damage helps. With a combination under way and no card that extends it, a reroll is worth suggesting more readily. The player has only seconds, so decide quickly and be unambiguous.

## REQUEST: debrief
Comes after a match, with everything the coach has on it. From the game's own record: every player's score, damage dealt and taken by type, damage blocked, healing, crowd control, gold, items and augments. From the kill timeline: every kill grouped into fights with the player's part in each, the gold lead minute by minute, and the structures destroyed. From the coach's own files: when each player finished each item, how the player died, and what the coach itself advised during the match, which is its build plans and its augment picks. Unlike the live snapshots, these numbers are measured.

The player already gets a grade from the game and a ranking from another tool. Do not grade, score or rank anyone, and do not read the scoreboard back to them. Your job is what a grade cannot do: work out why the match went the way it did and what this player's part in it was. Nobody is waiting on this answer, so reason through the whole record before you write:
- What decided the match. Use the fight list and the gold lead to find where it swung. Name the players on either side who carried those fights, and what in their items and augments let them.
- The player's part, fight by fight. Where were they in the fights their team won, and in the ones it lost? Which deaths cost the team something, and which came in fights it won? A death in a won or traded fight is not a mistake, and for a front-line champion it is often the job.
- What the numbers can and cannot show. Judge the player against what this champion, with the build they bought, can do. Low damage from a build with no damage in it is the build's result, not the player's failure. Revives, speed-ups, slows, shields on teammates and auras leave no trace in the record, so their absence is not evidence against a champion built to provide them. When your reading rests on something the record cannot show, say so.
- The build, piece by piece. For each item and augment, ask whether the record shows it doing its work. An item that fires on healing did nothing if almost no healing was recorded. Armor did its work if most of the damage taken was physical. Say whether the pieces multiplied each other as a combination, and which piece was missing when they did not. Teams in this mode heal a great deal in every match, so judge enemy healing by the comparison the request gives, not by the size of the number: an ordinary amount is not a reason to have bought an item that cuts healing.
- The coach's advice apart from the player's choices. The request says what the coach told the player to buy and which augments it picked. Where the player followed that advice and it turned out poor, the mistake is the coach's: say so plainly, and name what should have been bought instead. Where they departed from the plan, say whether that helped.
Say what the record supports and no more. A cause the player can act on is worth more than a count: "you died three times walking back alone after a lost fight" teaches something, and "30% of your deaths were avoidable" does not.

Answer with one JSON object and nothing else:
{"verdict": string, "went_well": [string], "to_fix": [string], "build_review": string, "focus_next_game": string}
- verdict: two sentences. How the match went for the player, then what decided it.
- went_well: one to three things the player did that mattered, each with its evidence: a fight and its time, or a number set against something comparable.
- to_fix: up to three specific things to do differently, each a cause with the evidence for it and the action that answers it. List fewer when the record shows fewer, and none when nothing in it is the player's to fix.
- build_review: three or four sentences. Whether the items and augments fit what both teams turned out to have, whether they came together as a combination, which pieces the record shows working and which it shows doing nothing, and where the coach's own advice was wrong.
- focus_next_game: the single habit that would help most, in one sentence that still makes sense on a different champion.
Be honest and kind. The player is learning: a review that only praises teaches nothing, and one that only criticises will not be read.

## REQUEST: champions
Lists every champion in the game as: id | name | classes | the game's own difficulty score from 1 to 10. The coach uses your answer in champion select, where the player has seconds to choose between a few champions and cannot wait for you. Answer with one line per champion, in the order given, and nothing else:
id | ease | job | why
- ease: a whole number from 1 to 5 for how well this champion works for the player described above, in ARAM. 5 means they can do its job by pressing abilities as they come up and clicking the nearest enemy. 1 means it does little without skills they do not claim: aiming a chain of skillshots, timing a combination, managing a resource, or dodging while fragile. A champion they say they know, love or like to play gets 5. When a champion plays much like one of those, rate it higher than you otherwise would and name the one it resembles in `why`, such as "plays like Nautilus: hook, then stun". Use the whole range, and judge for this player, not for an average one: a strong champion that dies before doing anything in their hands is a 1 or a 2.
- job: frontline, damage or support. What the champion mainly does for a team in ARAM: stands in front and takes hits, kills enemies, or heals, shields and protects teammates.
- why: at most 10 words the player can read at a glance, such as "tanky, point-and-click stun, hard to kill" or "fragile, needs every skillshot to land".

## REQUEST: research
Comes outside a match, to prepare what the requests above are given as PREPARED RESEARCH. The request states the task and the answer format. Nobody is waiting on it: reason at length, from the texts alone.

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
An effect marked PRESS-TO-USE only happens when the player presses that item's button. An effect marked Passive works by itself. BUTTON-ONLY means nothing on the item works without its button: unpressed, it is its stats and nothing more.
The numbers inside an effect are the standard game's, from a community dataset. This mode changes a few items, so a number can be slightly off; the stat lines in front are exact. "On-hit" and "on-attack" mean with every basic attack.
"""

PLAN_KEYS = ("headline", "build_order", "next_item_why", "how_to_play", "skill_order", "changed")

# How a plan is to use the damage estimate. This is part of plan requests and not of the system prompt, on purpose.
# The system prompt is read by every kind of request, and a change to it moves answers it was not aimed at: with
# these lines in the system prompt, one augment offer of a recorded match went from Ocean Soul in 5 answers of 6 to
# Lich Brain in 5 of 6, with nothing to say which was better. Guidance for plans goes where only plans read it.
ESTIMATE_NOTES = (
    "HOW TO USE THAT ESTIMATE IN THIS PLAN:",
    "  - Checked against 42 recorded matches, the split was within 12 points of the measured one about nine times in ten "
    "and 18 points off at worst. It counts the player's own armor and magic resist, so it moves as they buy either: a "
    "player who stacks one resistance is killed more and more by the other kind of damage, whatever the enemy team looks like.",
    "  - Read it together with the enemy kits and items above. When your own reading and the estimate point to different "
    "kinds of damage, do not stake the build on one of them: keep a resistance of each kind in it.",
    "  - Every point of a resistance stops less than the one before it, so a champion with far more of one than the other "
    "gains most from the one they lack. This holds on a champion whose abilities grow with armor or with magic resist: the "
    "kit is a reason to buy that stat first, not a reason to buy only that stat.",
    "  - The figures per item are arithmetic on the player's real stats, with each item's own effect counted. They are "
    "better evidence of what an item is worth here than its name or its reputation. When they put an item well ahead of "
    "the next defensive item in the build, half again as much or more for its gold, that item comes next among the "
    "defensive items, and `changed` says so. An augment or a combination that needs a particular item still comes first.",
)


def _clock(seconds: float) -> str:
    return f"{int(seconds) // 60}:{int(seconds) % 60:02d}"


def system_prompt_file(sd, family: str):
    """Write the system prompt for one item set and return its path.

    The text is identical for every call in a patch, so Claude serves it from the prompt cache.
    """
    augments = [f"{a['name']} | {a['tier']} | {a['description'][:260]}"
                for a in sorted(sd.augments_described(), key=lambda a: a["name"])]
    items = [f"{it['id']} | {it['name']} | {it['total']} | {', '.join(it['tags'])} | "
             f"{'BUTTON-ONLY; ' if it['button_only'] else ''}{it['text'][:900]}" for it in sd.catalog(family)]
    groups = sd.exclusive_groups(family)
    alone = ("\nITEMS THAT DO NOT COMBINE: a player gets each of these passives from one item only, so a build or a "
             "combination holds at most one item of each group. " + " ".join(
                 f"{name}: {', '.join(names)}." for name, names in groups.items()) + "\n") if groups else ""
    text = (SYSTEM_PROMPT.replace("<<PLAYER>>", config.player_profile()) + AUGMENT_HEADER + "\n".join(augments) + "\n"
            + CATALOG_HEADER + "\n".join(items) + "\n" + alone)
    # One file per version of the text. With a single file, a second process with another player description
    # or another version of this code (a test, a replay) rewrote the file under the coach while it was in a match.
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    path = sd.dir / f"system_prompt_{family}_{digest}.txt"
    if not path.exists():
        path.write_text(text, encoding="utf-8")
        for stale in sd.dir.glob(f"system_prompt_{family}_*.txt"):
            if stale != path and time.time() - stale.stat().st_mtime > 2 * 86400:
                stale.unlink(missing_ok=True)
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
    from . import champfit                           # imported here: champfit itself imports this module
    liked = champfit.favourites(sd).get(me["champ_id"])
    out.append("  familiarity: " + (f"the player says they {liked} playing this champion and know how it works" if liked else
                                    "not one of the champions the player says they know; assume they have never "
                                    "read its abilities"))
    checks = itemcheck.facts(sd, me["champ_id"], sd.catalog(catalog_family_for(state["item_ids"])))
    if checks:
        out.append("  ITEM CHECKS (worked out by the coach from this kit and the player's profile):")
        out += [f"    {line}" for line in checks]
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
    if state.get("deaths"):
        out.append(f"HOW YOU DIED THIS GAME (measured): {state['deaths']['line']}. Most recent: {state['deaths']['last']}")
    seen = _threats(sd, state)
    estimate = threats.lines(sd, state, seen)
    out += estimate
    if estimate and header.startswith("REQUEST: plan") and seen.get("sturdy"):
        out += ESTIMATE_NOTES                # how to balance resistances: for champions that buy them

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
        casts = sd.how_cast(p["champ_id"]) if role == "you" else {}
        if casts:
            out.append("    how each ability is cast, with the mouse aim it needs (a second press is listed as Recast):")
            out += [f"      {slot}" + (f" (aim: {casts[slot]['aim']})" if casts[slot]["aim"] else "") + f": {casts[slot]['text']}"
                    for slot in "PQWER" if slot in casts]

    out += research.plan_lines(sd, state, ahead=header.startswith("REQUEST: pregame"))
    told = state.get("told") or []
    if told:
        # The player typed "teammates say dont build anything defensive on my ap mage" in one match. The answer began
        # "Your teammates are half right" and the next plans kept the armor item. What the player asks for is theirs
        # to decide, so it reaches every later request of the match as an instruction.
        out += ["", "WHAT THE PLAYER TYPED TO YOU DURING THIS MATCH (oldest first):"]
        out += [f"  {_clock(t['time'])} \"{t['text']}\"" for t in told[-6:]]
        out.append("  What the player says there about their build or how they want to play is an instruction for the rest of "
                   "this match. Follow it in the build, and say in `changed` what you changed for it. Do not argue with it, and "
                   "do not keep an item they asked you to drop. If it cannot be done, say why in one sentence.")
    if previous_plan:
        out += ["", previous_plan]
    return "\n".join(out)


def _frontline(sd, me: dict) -> bool:
    """Whether the player's champion stands in front, from the fit table or the game's own class tags."""
    from . import champfit                           # imported here: champfit itself imports this module
    rating = (champfit.load(sd) or {}).get(me["champ_id"]) or champfit.fallback(sd, me["champ_id"])
    return rating["job"] == "frontline"


def _sturdy(sd, me: dict) -> bool:
    """Whether the player's champion builds defense: it stands in front, or the game classes it as a tank.

    The second part matters for the hook supports. Thresh, Blitzcrank, Braum and Taric protect teammates,
    so their job reads "support", and they buy armor and health all the same.
    """
    tags = (sd.champions.get(me.get("champ_id")) or {}).get("tags") or []
    return _frontline(sd, me) or "Tank" in tags


BACKLINE_REVIEW_NOTE = (
    "THE PLAYER'S INSTRUCTION FOR THIS KIND OF CHAMPION: {champion} fights from behind the front line. The player does not "
    "want items bought only for armor, magic resist or health on such champions, and the coach follows that. Do not count "
    "the absence of such an item as a mistake of the coach or of the player, and do not recommend one. Where the player died "
    "often, look at where they stood, when they entered fights, and whether the build had the damage to end fights sooner. A "
    "plain defensive item is right in such a build only when an augment the player held turned health, armor or magic resist "
    "into damage or healing.")


def _threats(sd, state: dict):
    """What kind of damage is killing the player and what answers it (see threats.read)."""
    me = state["me"]
    if me is None:
        return None
    catalog = sd.catalog(catalog_family_for(state["item_ids"]))
    return threats.read(sd, state, catalog, _frontline(sd, me), itemcheck.rejected(sd, me["champ_id"], catalog),
                        sturdy=_sturdy(sd, me))


def sets_the_build(trigger: str) -> bool:
    """Whether a plan made for this reason decides what the build is, as opposed to keeping one up to date.

    True at the start of a match, after an augment, when the player asks for a fresh plan and when
    they type something to the coach. A plan made because the player died or an enemy bought an
    item adjusts the build in force and is the one read on a death timer.
    """
    return (trigger.startswith(("game start", "the player typed", "the player's augments changed"))
            or "asked for a fresh plan" in trigger or "took the augment" in trigger)


def plan_tools(sd, state: dict, trigger: str):
    """The calculations a plan request may call (see tools.py), or None when this plan gets none.

    Only a plan that sets the build gets them: there the choice between items is open, and a
    few more seconds cost little. They need the API: the Claude Code login answers a question
    and cannot call anything.
    """
    if config.TOOLS != "plan" or config.BACKEND != "api" or state.get("me") is None or not sets_the_build(trigger):
        return None
    seen = _threats(sd, state)
    return tools.Toolbox(sd, state, sturdy=_sturdy(sd, state["me"]), share=seen["mix"]["share"] if seen else None)


def plan_summary(advice: dict, game_time: float, taken_out=()) -> str:
    """One paragraph describing the current plan, sent back to Claude so later plans stay consistent.

    taken_out: the items earlier plans of this match removed from the build and have not put
    back, as [{name, time, why}]. Each answer from Claude is made without memory of the last,
    so without this list a plan can swap an item out for one reason and back in for another.
    With it, going back is a decision made in sight of the first one.
    """
    order = " > ".join(b["name"] for b in advice["build_order"])
    scaling = advice.get("scaling") or {}
    goal, combo = scaling.get("goal"), scaling.get("combo") or {}
    text = (f"YOUR PREVIOUS PLAN (given at {_clock(game_time)}): {advice['headline']} "
            f"Build order: {order}. Skill order: {advice['skill_order']}"
            + (f" Scaling goal: {goal}" if goal else ""))
    if combo.get("name"):
        text += (f" Combination under way: {combo['name']}. Pieces held: {', '.join(combo.get('have') or []) or 'none'}."
                 f" Still needed: {'; '.join(combo.get('next') or []) or 'nothing'}.")
    else:
        hoped = scaling.get("augments_to_look_for") or []
        text += " No combination under way." + (f" Augments that would start one: {'; '.join(hoped)}." if hoped else "")
    if taken_out:
        text += ("\nITEMS YOUR EARLIER PLANS OF THIS MATCH TOOK OUT OF THE BUILD: "
                 + "; ".join(f"{t['name']} at {_clock(t['time'])}" + (f" (reason given: {t['why']})" if t["why"] else "")
                             for t in taken_out)
                 + ". You do not remember writing those plans, so check before you undo one: swapping the same two items "
                   "back and forth is noise to the player. Bring an item back when the reason it was taken out no longer "
                   "holds or the game has changed since, and name what changed in `changed`. A reason that turned out wrong "
                   "is itself a reason to go back.")
    return text


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


def _validate(advice: dict, catalog: list, rejected: dict | None = None, owned=()) -> dict:
    """Normalise a plan. Unknown items are dropped, and every field ends up with the right type.

    owned: ids of the items the player holds. Once they own finished boots, the build keeps
    that pair: a plan that lists other boots gets the owned pair in their place. In 188
    recorded plans that happened three times, all in one match, where the panel told a player
    with Ionian Boots and a full inventory to buy Mercury's Treads.

    rejected: items this champion and player must not be told to buy, as {item id: reason} (see
      itemcheck.rejected). Any in the build are removed and reported under `dropped`.

    A second item with a passive the player can only have once, such as a second Spellblade
    item, is removed the same way. In 206 recorded plans that happened four times, and a plan
    made from a playbook that mentioned a second Spellblade item listed one in one answer of
    four although the prompt says they do not combine.
    """
    by_id = {it["id"]: it for it in catalog}
    by_name = {norm(it["name"]): it for it in catalog}
    rejected = rejected or {}
    passive = {name: group for group, names in exclusive_groups(catalog).items() for name in names}
    build, seen, dropped, holder = [], set(), [], {}
    for entry in advice.get("build_order") or []:
        if not isinstance(entry, dict):
            continue
        # Names win over ids when they disagree: Claude is more reliable with names than numbers.
        item = by_name.get(norm(entry.get("name", ""))) or by_id.get(entry.get("item_id"))
        if item and item["id"] not in seen:
            seen.add(item["id"])
            group = passive.get(item["name"])
            if item["id"] in rejected:
                dropped.append({"name": item["name"], "why": rejected[item["id"]]})
            elif group in holder:
                dropped.append({"name": item["name"], "why": f"a second {group} item: the effect works from one item only, "
                                                             f"and the build already has {holder[group]}"})
            else:
                build.append({"item_id": item["id"], "name": item["name"], "why": _text(entry.get("why"))})
                if group:
                    holder[group] = item["name"]
    if not build:
        raise llm.LLMError("Claude's plan contained no items from the catalog.")
    is_boots = lambda item_id: "Boots" in by_id[item_id]["tags"]
    mine = next((i for i in owned if i in by_id and is_boots(i)), None)
    others = [b for b in build if is_boots(b["item_id"]) and b["item_id"] != mine] if mine is not None else []
    if others:
        if not any(b["item_id"] == mine for b in build):
            build[build.index(others[0])] = {"item_id": mine, "name": by_id[mine]["name"], "why": "The boots you already own."}
        build = [b for b in build if b not in others]
        dropped += [{"name": o["name"], "why": f"you already own {by_id[mine]['name']}: the build keeps the boots you have"}
                    for o in others]
    scaling = advice.get("scaling") if isinstance(advice.get("scaling"), dict) else {}
    combo = scaling.get("combo") if isinstance(scaling.get("combo"), dict) else {}
    pieces = lambda key, limit: [_text(s) for s in (combo.get(key) if isinstance(combo.get(key), list) else [])
                                 if _text(s)][:limit]
    return {
        "headline": _text(advice.get("headline")),
        "build_order": build,
        "next_item_why": _text(advice.get("next_item_why")),
        "how_to_play": [_text(s) for s in advice.get("how_to_play") or [] if _text(s)][:3],
        "scaling": {
            "goal": _text(scaling.get("goal")),
            # The combination under way. An empty name means there is none, so its pieces are dropped too.
            "combo": {"name": _text(combo.get("name"))[:40], "have": pieces("have", 8), "next": pieces("next", 3)}
            if _text(combo.get("name")) else {"name": "", "have": [], "next": []},
            "augments_to_look_for": [_text(s) for s in scaling.get("augments_to_look_for") or [] if _text(s)][:5],
        },
        "skill_order": _text(advice.get("skill_order")),
        "changed": _text(advice.get("changed")),
        "dropped": dropped,
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

def get_advice(sd, state: dict, previous_plan: str, trigger: str, on_partial=None, on_start=None):
    """Ask Claude for a full plan. Returns (advice, meta).

    on_partial: optional callback. It is called once, with a plan holding only the headline
      and build order, as soon as those have streamed in. The build order is what the player
      needs first, and it arrives several seconds before the full answer.
    """
    family = catalog_family_for(state["item_ids"])
    catalog = sd.catalog(family)
    rejected = itemcheck.rejected(sd, state["me"]["champ_id"], catalog)
    owned = {i["id"] for i in state["me"]["items"]}
    prompt = render_request(sd, state, previous_plan, f"REQUEST: plan (reason for this update: {trigger})")
    toolbox = plan_tools(sd, state, trigger)
    if toolbox is not None:
        prompt += "\n\n" + "\n".join(list(tools.PLAN_NOTE) + tools.kit_rules(sd, state["me"]["champ_id"]))
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
            on_partial(_validate({"headline": _streamed_headline(received), "build_order": build}, catalog, rejected, owned))
        except llm.LLMError:
            pass                      # nothing usable yet; the full answer follows

    text, meta = llm.run(system_prompt_file(sd, family), prompt, on_text=on_text if on_partial else None,
                         on_start=on_start, **({"tools": toolbox} if toolbox is not None else {}))
    return _validate(_parse_json(text), catalog, rejected, owned), meta


def consensus(plans: list, catalog: list, owned=(), previous=()) -> tuple:
    """Combine independent plans for the same moment into one. Returns (advice, info).

    plans: validated plans, each the answer to the same request. owned: ids of the items the
    player holds. Asked the same thing eight times in two real matches, Claude gave the same
    four core items and, in 14 of 16 answers, the same next purchase, while the last two slots
    changed from answer to answer. So:

    - an item most of the plans list goes in, ordered by its average place in them;
    - a slot they do not agree on keeps what the plan in force had there, when at least one
      of them still lists it (`previous`, the ids of that plan's build): without agreement
      there is no reason to change it;
    - what is left is filled, in its own order, from the plan the others agree with most. A
      build is a set of pieces meant to work together, so the tail comes from one plan and is
      not stitched from several;
    - the words (headline, how to play, the combination) are that plan's too.

    info: {votes, agreed, builds}: how many plans there were, how many items of the result
    most of them listed, and each plan's build by name.
    """
    builds = [[b["item_id"] for b in p["build_order"]] for p in plans]
    info = {"votes": len(plans), "agreed": len(builds[0]), "builds": [[b["name"] for b in p["build_order"]] for p in plans]}
    if len(plans) == 1:
        return plans[0], info
    held = set(owned)
    first_todo = lambda build: next((i for i in build if i not in held), None)

    def likeness(a, b):                          # shared items, and more for agreeing on what to buy next
        return len(set(a) & set(b)) + (2 if first_todo(a) is not None and first_todo(a) == first_todo(b) else 0)

    closest = max(range(len(plans)), key=lambda i: (sum(likeness(builds[i], builds[j]) for j in range(len(plans)) if j != i), -i))
    base = plans[closest]
    count = Counter(item for build in builds for item in set(build))
    place = {item: sum(b.index(item) for b in builds if item in b) / count[item] for item in count}
    most = len(plans) // 2 + 1
    order = sorted((i for i in count if count[i] >= most), key=lambda i: (place[i], -count[i]))
    order += [i for i in previous if i in count and i not in order]
    order += [i for i in builds[closest] if i not in order]
    tags = {it["id"]: it["tags"] for it in catalog}
    boots = [i for i in order if "Boots" in tags.get(i, [])]
    keep = max(boots, key=lambda i: (count[i], -order.index(i))) if boots else None
    order = [i for i in order if i not in boots or i == keep][:max(len(b) for b in builds)]
    entry = {b["item_id"]: b for p in reversed(plans) for b in p["build_order"]}
    entry.update({b["item_id"]: b for b in base["build_order"]})     # the chosen plan's own words where it lists the item
    build = [entry[i] for i in order]
    next_why = base["next_item_why"]
    if first_todo(order) != first_todo(builds[closest]) and first_todo(order) is not None:
        next_why = entry[first_todo(order)]["why"]        # the sentence must be about the item that is now next
    dropped = list({d["name"]: d for p in plans for d in p.get("dropped") or []}.values())
    info["agreed"] = sum(1 for i in order if count[i] >= most)
    return {**base, "build_order": build, "next_item_why": next_why, "dropped": dropped}, info


IN_PROGRESS_GOLD = 700        # parts worth this much make a finished item "in progress"
PROGRESS_MARGIN = 300         # and it must be this far ahead of the plan's own next item to displace it


def _parts(sd, item_id: int, seen=None) -> set:
    """Every component in one item's recipe, at any depth."""
    seen = set() if seen is None else seen
    for sub in (sd.items.get(item_id) or {}).get("from") or []:
        if sub not in seen:
            seen.add(sub)
            _parts(sd, sub, seen)
    return seen


def parts_held(sd, item_id: int, held) -> list:
    """The items in the player's inventory that are components of one finished item, as ids."""
    tree = _parts(sd, item_id)
    return [i for i in held if i in tree]


def steady(sd, old: dict | None, new: dict, held, fresh: bool) -> dict:
    """Hold a new plan to what the player has already committed to. Returns the plan to show.

    Each answer from Claude is a fresh opinion, and opinions differ from one answer to the next.
    A player following the plan purchase by purchase experiences that as the coach changing its
    mind: in one real match the fourth item went Spirit Visage, Warmog's Armor, Warmog's Armor
    while the player held 1,650 gold of Spirit Visage parts, and the last two slots changed in
    five of ten ordinary updates. So two things are decided here and not by Claude:

    - An item in progress is finished first. When the player holds parts worth IN_PROGRESS_GOLD
      toward a finished item of the old or the new build, and the new plan's next purchase does
      not use those parts as well, that item is the next purchase. If the new plan dropped it,
      it takes the place of the plan's last item.
    - An ordinary update that announces no change keeps the build. The request asks for a
      sentence in `changed` whenever the build changes. With no sentence, the build in force
      stays, and only the words of the new plan are used. `fresh` marks the plans that are
      free to change it: the first of a match, a remake, one the player asked for. A plan
      that lists a finished item the player holds and the build in force lacks is free as
      well: the player bought off the plan, and a build that leaves out what they own is
      wrong whatever the plan said about it. In a replay the kept build showed six items to
      buy beside a Blade of The Ruined King the player already had.

    For one day a third rule stood here: an item taken out of the build did not come back,
    whatever reason the plan gave. It was added after a replay in which one late slot went
    Thornmail, Force of Nature, Thornmail. In the next real match a plan took Force of Nature
    out at 3:40 on a wrong reading of the damage, and from 10:56 four plans in a row tried to
    put it back, each saying that the two enemy mages were what killed the player. The rule
    overrode all four, and the player finished with five armor items against a team whose
    damage on them was 68% magic. A rule that cannot tell a correction from a change of mind
    must not overrule the plan. What was taken out, when and why now goes to Claude with the
    previous plan (see plan_summary), which is the memory it lacked when it went back and forth.

    old: the plan in force, or None. held: ids of the items in the player's inventory.
    The result carries `kept`: "" when nothing was held back, "build" when the old build was
    kept, or the name of the item in progress that was put first. Whenever the build shown
    differs from the one the plan asked for, `proposed` holds the names the plan asked for and
    `proposed_change` its sentence, for the log: what the coach overrode has to be visible.
    """
    held = list(held)
    owned = set(held)
    out = {**new, "kept": ""}
    build = list(new["build_order"])
    planned = {b["item_id"] for b in old["build_order"]} if old else set()
    off_plan = any(b["item_id"] in owned and b["item_id"] not in planned for b in build)
    # An answer cut short is not a build. One replayed plan came back with a single item (200 output tokens);
    # shown as it was, the panel would have told the player to buy boots and nothing else.
    cut_short = bool(old) and len(build) < 4 <= len(old["build_order"])
    if old and (cut_short or (not fresh and not new.get("changed") and not off_plan)) \
            and [b["item_id"] for b in build] != [b["item_id"] for b in old["build_order"]]:
        first = lambda plan: next((b["item_id"] for b in plan if b["item_id"] not in owned), None)
        if first(build) != first(old["build_order"]):
            out["next_item_why"] = old.get("next_item_why") or out.get("next_item_why", "")
        build, out["kept"] = list(old["build_order"]), "build"
        out["changed"] = ""
    todo = [b for b in build if b["item_id"] not in owned]
    if todo:
        listed = {b["item_id"] for b in todo}
        earlier = [b for b in (old or {}).get("build_order") or [] if b["item_id"] not in owned and b["item_id"] not in listed]
        gold = lambda item_id: sum(sd.items[i]["total"] for i in parts_held(sd, item_id, held))
        started = max(todo + earlier, key=lambda b: gold(b["item_id"]))        # the first of equals: the plan's own order
        if started is not todo[0] and gold(started["item_id"]) >= max(IN_PROGRESS_GOLD, gold(todo[0]["item_id"]) + PROGRESS_MARGIN):
            rest = [b for b in todo if b is not started]
            if started["item_id"] not in listed:                               # the new plan dropped it: it replaces the last item
                boots = lambda b: "Boots" in (sd.items.get(b["item_id"]) or {}).get("tags", [])
                rest.remove(next((b for b in reversed(rest) if not boots(b)), rest[-1]))
            queue = iter([started] + rest)
            build = [b if b["item_id"] in owned else next(queue) for b in build]
            names = [sd.items[i]["name"] for i in parts_held(sd, started["item_id"], held)]
            out["next_item_why"] = f"You already hold {', '.join(dict.fromkeys(names))} for it, so finish it before anything else."
            out["kept"] = started["name"]
            if out.get("changed"):
                # The plan's sentence describes the order it asked for. One real panel read "Kaenic Rookern now comes
                # before Thornmail" above a build that listed Thornmail first.
                out["changed"] = f"{out['changed'].rstrip()} {started['name']} still comes first: you hold parts of it."
    out["build_order"] = build
    if [b["item_id"] for b in build] != [b["item_id"] for b in new["build_order"]]:
        out["proposed"], out["proposed_change"] = [b["name"] for b in new["build_order"]], new.get("changed") or ""
    if old and [b["item_id"] for b in build] == [b["item_id"] for b in old["build_order"]]:
        out["changed"] = ""                      # "Kept the build: ..." is not a change to announce
    return out


def build_change(old: dict | None, new: dict, owned=()) -> str:
    """One sentence on how a freshly made plan differs from the one it replaces, for the panel.

    Empty when the items the player holds and the next two to buy are what they were. The last
    slots of a build move between answers for no reason the player could act on, and they are
    decided again before they are reached, so a change there is shown and not announced.
    """
    if not old:
        return ""
    held = set(owned)
    front = lambda plan: [b["name"] for b in plan["build_order"] if b["item_id"] not in held][:2]
    if front(old) == front(new):
        return ""
    before, after = [b["name"] for b in old["build_order"]], [b["name"] for b in new["build_order"]]
    added, removed = [n for n in after if n not in before], [n for n in before if n not in after]
    why = {b["name"]: b["why"] for b in new["build_order"]}
    if len(added) == 1 and len(removed) == 1:
        return f"{added[0]} replaces {removed[0]}: {why[added[0]]}".rstrip(": ")
    if added or removed:
        parts = ([f"added {', '.join(added)}"] if added else []) + ([f"dropped {', '.join(removed)}"] if removed else [])
        return ("Build remade with what is known now: " + "; ".join(parts) + ".")
    return f"Same items in a new order: {front(new)[0]} now comes next."


def get_plan(sd, state: dict, previous_plan: str, trigger: str, votes: int = 1, on_partial=None, previous_build=()):
    """Ask Claude for a plan. With votes above one, make that many independent plans and combine them.

    The independent plans are not shown the earlier plan, so they do not lean on it: one real
    match kept a build that had been remade after an augment and never returned to an item the
    player had already started, which eight fresh plans out of eight picked up. They are sent
    together, so the wait is that of the slowest one. On a prompt the API no longer holds in
    its cache the rest wait until the first has begun to be answered and then read what it
    wrote: three sent at once each paid to write it, $0.85 where $0.20 is usual.
    previous_build: ids of the items in the plan in force, kept where the new plans disagree.
    Returns (advice, meta); meta adds `votes`, `agreed` and `builds` (see consensus).
    """
    if votes <= 1:
        return get_advice(sd, state, previous_plan, trigger, on_partial)
    family = catalog_family_for(state["item_ids"])
    cold = config.BACKEND == "api" and not llm.prompt_is_warm(system_prompt_file(sd, family))
    begun, asked_at = threading.Event(), time.time()

    def one(index):
        if index and cold:
            # Wait for the first answer to start. On a fresh process that took over ten seconds (loading the
            # API library), and a shorter wait let all three write the prompt. The first request releases
            # the others when it ends for any reason, so the long limit only guards against a hang.
            begun.wait(timeout=45)
        try:
            return get_advice(sd, state, "", trigger, on_partial if index == 0 else None,
                              on_start=begun.set if index == 0 else None)
        finally:
            begun.set()                          # never leave the others waiting on a request that failed

    answers, failures = [], []
    with ThreadPoolExecutor(max_workers=votes) as pool:
        for future in [pool.submit(one, i) for i in range(votes)]:
            try:
                answers.append(future.result())
            except Exception as exc:              # one failed answer must not lose the others
                failures.append(exc)
    if not answers:
        raise failures[0]
    advice, info = consensus([a for a, _ in answers], sd.catalog(family), {i["id"] for i in state["me"]["items"]},
                             previous_build)
    metas = [m for _, m in answers]
    costs = [m.get("cost") for m in metas]
    meta = {**metas[0], "latency": round(time.time() - asked_at, 1),      # the wait the player sees, not one request's
            "cost": None if any(c is None for c in costs) else round(sum(costs), 4),
            "output_tokens": sum(m.get("output_tokens") or 0 for m in metas), **info}
    return advice, meta


def get_pregame(sd, state: dict):
    """Ask Claude for the plan before the match, from champion picks alone. Returns (advice, meta).

    The advice is a normal plan plus `title`, `situational`, `augment_builds` and `pool`, which
    feed the in-game item set.
    """
    catalog = sd.catalog("std")
    rejected = itemcheck.rejected(sd, state["me"]["champ_id"], catalog)
    prompt = render_request(sd, state, "", "REQUEST: pregame")
    text, meta = llm.run(system_prompt_file(sd, "std"), prompt)
    raw = _parse_json(text)
    advice = _validate(raw, catalog, rejected)
    ids = {it["id"] for it in catalog} - set(rejected)     # the item set must not offer them either

    def groups(key: str, limit: int) -> list:
        found = raw.get(key)
        return [
            {"title": _text(g.get("title"))[:60], "item_ids": [i for i in g.get("item_ids") or [] if i in ids][:6]}
            for g in (found if isinstance(found, list) else []) if isinstance(g, dict) and _text(g.get("title"))
        ][:limit]

    advice["title"] = _text(raw.get("title"))[:28]
    advice["pool"] = [i for i in raw.get("pool") or [] if i in ids][:12]
    advice["situational"] = groups("situational", 5)
    advice["augment_builds"] = groups("augment_builds", 4)
    return advice, meta


def read_screen(sd, state: dict, previous_plan: str, image: bytes, names=()):
    """Ask Claude to read a screenshot of the game, usually an augment choice. Returns (result, meta).

    names: the augment names already read off the screen, when there are any, so that what the
      prepared research says about each can be given alongside the picture.
    """
    family = catalog_family_for(state["item_ids"])
    prompt = render_request(sd, state, previous_plan, "REQUEST: screen")
    found = research.card_lines(sd, state, list(names))
    if found:
        prompt += "\n\n" + "\n".join(found)
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
    found = research.card_lines(sd, state, [a["name"] for a in offer])
    if found:
        prompt += "\n\n" + "\n".join(found)
    text, meta = llm.run(system_prompt_file(sd, family), prompt)
    raw = _parse_json(text)
    names = {norm(a["name"]): a["name"] for a in offer}
    return {
        "pick": names.get(norm(_text(raw.get("pick"))), ""), "why": _text(raw.get("why")),
        "reroll": _text(raw.get("reroll")), "note": _text(raw.get("note")),
    }, meta


def _player_record(p: dict, team: list) -> str:
    """One player's line in the review request: the final numbers, with shares of their team's totals."""
    share = lambda value, key: f"{round(100 * value / (sum(q.get(key) or 0 for q in team) or 1))}%"
    kills = sum(q["kda"][0] for q in team) or 1
    text = (f"  {'YOU: ' if p['me'] else ''}{p['champion']} level {p['level']} | K/D/A {'/'.join(map(str, p['kda']))}"
            f" | in on {round(100 * (p['kda'][0] + p['kda'][2]) / kills)}% of team kills"
            f" | damage to champions {p['damage']} ({share(p['damage'], 'damage')} of team")
    if p.get("damage_kinds"):
        text += "; physical {}, magic {}, true {}".format(*p["damage_kinds"])
    text += f") | damage taken {p['taken']} ({share(p['taken'], 'taken')} of team"
    if p.get("taken_kinds"):
        text += "; physical {}, magic {}, true {}".format(*p["taken_kinds"])
    text += ")"
    if p.get("mitigated") is not None:
        text += f", blocked {p['mitigated']}"
    text += f" | healing {p['healing']}"
    if p.get("healed_units") is not None:
        text += " on themselves only" if p["healed_units"] <= 1 else f" across {p['healed_units']} players"
    if p.get("cc_seconds") is not None:
        text += f" | crowd control applied {p['cc_seconds']}s"
    text += f" | gold {p['gold']}"
    if p.get("gold_spent") is not None:
        text += (f", {p['gold_spent']} spent | longest life {_clock(p['longest_life'])}"
                 f" | best multikill {p['multikill']} | minions {p['minions']} | turret damage {p['turret_damage']}")
    return (text + f" | augments: {', '.join(p['augments']) or 'none'}"
            f" | items at the end: {', '.join(p['items']) or 'none'}")


def _fight_line(fight: dict) -> str:
    """One fight as a line of the review request, from the player's side."""
    span = _clock(fight["start"]) + (f"-{_clock(fight['end'])}" if fight["end"] - fight["start"] >= 5 else "")
    me = fight["me"]
    lost = ["YOU" if me["died"] and i == me["order"] else c for i, c in enumerate(fight["lost"])]
    text = f"  {span}  {len(fight['killed'])} for {len(fight['lost'])}"
    if fight["killed"]:
        text += " | killed " + ", ".join(fight["killed"])
    if lost:
        text += " | lost " + ", ".join(lost)
    part = []
    if me["died"]:
        order = "first of your team" if me["order"] == 0 else f"after {me['order']} teammate{'s' if me['order'] > 1 else ''}"
        helpers = f" with {', '.join(me['helpers'])}" if me["helpers"] else ""
        part.append(f"died {order}, to {me['killer'] or 'no champion'}{helpers}")
    if fight["killed"]:
        part.append(f"in on {me['credits']} of {len(fight['killed'])} kills")
    if not me["died"] and not me["credits"]:
        since = me["since_death"]
        part = ["no part" + (f", {since}s after your last death" if since is not None and since <= 90 else "")]
    return text + " | you: " + "; ".join(part)


def _coach_record(story: dict, held=None) -> list:
    """What the coach advised during the match, as lines of the review request.

    held: the names of the augments the game's own record says the player ended with, or None
    when there is no such record. The coach cannot see which card the player clicks. It assumes
    its pick was taken unless told otherwise, and that is sometimes wrong. One review blamed a
    build on Celestial Body, which the coach had assumed and the player had rerolled away. So
    an assumed augment that the record does not list is called out as never held.
    """
    out = []
    listed = {norm(n) for n in held or ()}
    never = lambda name: bool(listed) and norm(name) not in listed and "Shard" not in name and name.strip().upper() not in (
        "HEAVY", "POWER", "THRASH", "DOOM")       # shards and ability upgrades are not always in the record
    plans = story.get("plans") or []
    previous = None
    for plan in plans:
        if plan["build"] != previous or plan.get("changed") or plan.get("dropped"):
            build = " > ".join(plan["build"]) if plan["build"] != previous else "same build"
            out.append(f"  {_clock(plan['time'])} plan ({plan['trigger'][:90]}): {build}"
                       + (f" | the coach's note: {plan['changed']}" if plan.get("changed") else "")
                       + (f" | removed by the item checks: {', '.join(plan['dropped'])}" if plan.get("dropped") else ""))
        previous = plan["build"]
    if plans:
        out.append(f"  {len(plans)} plans in all; the ones not listed repeated the build above them.")
    for offer in story.get("offers") or []:
        taken = "not known" if not offer.get("taken") else (
            f"{offer['taken']} ({'assumed, the player did not say' if offer.get('assumed') else 'confirmed'})")
        if offer.get("taken") and offer.get("assumed") and never(offer["taken"]):
            taken = (f"NOT {offer['taken']}. The game's record shows the player never held it. The coach assumed they did "
                     f"and planned as if they held it for the rest of the match: that is the coach's mistake, not the player's")
        when = _clock(offer["time"]) if offer.get("time") is not None else "?"
        out.append(f"  {when} augment offer: {', '.join(offer['names'])} | the coach picked {offer.get('pick') or 'nothing'}"
                   + (f" because: {offer['why']}" if offer.get("why") else "") + f" | taken: {taken}")
    for said in story.get("told") or []:
        out.append(f"  {_clock(said['time'])} the player typed to the coach: \"{said['text']}\"")
    return out


def render_debrief(summary: dict, last_plan: str, deaths: dict | None = None, story: dict | None = None,
                   sd=None) -> str:
    """Render everything known about a finished match as the text Claude reviews.

    deaths: the coach's breakdown of how the player died (deaths.summarize), when it has one.
    story: the match as it unfolded and what the coach advised (postgame.story), when available.
    sd: game data. With it, the request carries the champions' ability notes and the item checks.
    """
    players = summary["players"]
    me = next(p for p in players if p["me"])
    mine = [p for p in players if p["team"] == me["team"]]
    theirs = [p for p in players if p["team"] != me["team"]]
    story = story or {}

    mode = {"KIWI": "ARAM: Mayhem", "ARAM": "ARAM"}.get(summary.get("mode"), summary.get("mode") or "unknown mode")
    out = ["REQUEST: debrief",
           f"MODE: {mode} | length {summary['minutes']} minutes | result for the player: {'WIN' if me['win'] else 'LOSS'}",
           f"TEAM SIZES: your side had {len(mine)}, the enemy side had {len(theirs)}.",
           f"YOUR TEAM ({sum(p['kda'][0] for p in mine)} kills):"] + [_player_record(p, mine) for p in mine]
    out += [f"ENEMY TEAM ({sum(p['kda'][0] for p in theirs)} kills):"] + [_player_record(p, theirs) for p in theirs]

    if story.get("fights"):
        out += ["", "THE MATCH FIGHT BY FIGHT (kills less than 15 seconds apart are one fight; \"2 for 1\" means the "
                    "player's team killed two and lost one):"]
        out += [_fight_line(f) for f in story["fights"]]
    if story.get("gold"):
        out.append("GOLD LEAD OF THE PLAYER'S TEAM, minute by minute: "
                   + ", ".join(f"{_clock(g['time'])} {g['lead']:+d}" for g in story["gold"]))
    if story.get("structures"):
        out.append("STRUCTURES DESTROYED: " + ", ".join(
            f"{_clock(s['time'])} {'your team' if s['ours'] else 'the enemy'} took a {s['kind']}" for s in story["structures"]))
    healing = story.get("healing")
    if healing:
        text = f"ENEMY HEALING: their team healed {healing['per_minute']} a minute."
        if healing.get("usual"):
            ratio = healing["per_minute"] / healing["usual"]
            word = ("well above" if ratio >= 1.4 else "above" if ratio >= 1.15 else "below" if ratio <= 0.85 else "about")
            text += (f" In the player's other {healing['matches']} recorded matches the middle value was {healing['usual']} a "
                     f"minute, so this was {word} the usual amount.")
        out.append(text)
    bought = story.get("purchases") or {}
    if any(bought.values()):
        out.append("WHEN EACH FINISHED ITEM WAS FIRST SEEN (from snapshots half a minute apart, so up to 30 seconds late):")
        for p in mine + theirs:
            rows = bought.get(p["champion"]) or []
            if rows:
                out.append(f"  {'YOU: ' if p['me'] else ''}{p['champion']}: "
                           + ", ".join(f"{r['item']} {_clock(r['time'])}" for r in rows))

    if deaths:
        out.append(f"HOW THE PLAYER DIED (measured by the coach during the match): {deaths['line']}.")
    for d in story.get("death_rows") or []:
        health = f"; health ten seconds earlier {round(100 * d['health'])}%" if d.get("health") is not None else ""
        out.append(f"  {_clock(d['time'])} {d['verdict']}: team lost {d['ours']} and killed {d['theirs']}; the fight "
                   f"began {d['started_with']} against {d['started_against']}{health}; killed by "
                   f"{d['killer'] or 'no champion'}" + (f" and {d['by'] - 1} more" if d.get("by", 0) > 1 else ""))
    advised = _coach_record(story, me.get("augments"))
    if advised:
        out += ["", "WHAT THE COACH ADVISED DURING THE MATCH:"] + advised
    if sd is not None and me.get("champ_id") and not _sturdy(sd, me):
        out.append(BACKLINE_REVIEW_NOTE.format(champion=me["champion"]))
    if last_plan:
        out += ["", "THE COACH'S LAST PLAN DURING THIS MATCH: " + last_plan]
    if story.get("focus"):
        out.append(f"THE FOCUS THE LAST REVIEW GAVE THE PLAYER FOR THIS MATCH: {story['focus']}")

    if sd is not None:
        checks = itemcheck.facts(sd, me.get("champ_id"), sd.catalog("std"))
        if checks:
            out += ["", "ITEM CHECKS FOR THE PLAYER'S CHAMPION (worked out by the coach from the kit and the profile):"]
            out += [f"  {line}" for line in checks]
        out.append("CHAMPION NOTES:")
        for p, role in [(me, "you")] + [(e, "enemy") for e in theirs]:
            notes = sd.champion_notes(p["champ_id"]) if p.get("champ_id") else None
            if notes:
                out.append(f"  {p['champion']} ({role}): {notes['passive']}")
                out += [f"    {s}" for s in notes["spells"]]
    return "\n".join(out)


def get_debrief(sd, summary: dict, last_plan: str = "", deaths: dict | None = None, story: dict | None = None):
    """Ask Claude to review a finished match from everything recorded about it. Returns (review, meta).

    Nobody is waiting on a death timer for this answer, so it runs at a higher reasoning effort
    than the plans made during a match.
    """
    text, meta = llm.run(system_prompt_file(sd, "std"), render_debrief(summary, last_plan, deaths, story, sd),
                         effort=config.DEBRIEF_EFFORT)
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
    prompt = (render_request(sd, state, previous_plan, "REQUEST: question") + f"\n\nTHE PLAYER ASKS: {question}"
              + "\nIf that tells you how the player wants to build or play, it is an instruction and not a question: agree, "
                "say in one or two sentences what changes in the build, and do not argue the point. A new plan that follows "
                "it is being made as you answer.")
    mentioned = augments_mentioned(sd, question)
    if mentioned:
        prompt += "\n\nAUGMENTS NAMED IN THE QUESTION (current descriptions):\n" + "\n".join(
            f"  {a['name']} ({a['tier']}): {a['description']}" for a in mentioned)
    text, meta = llm.run(system_prompt_file(sd, family), prompt)
    return text.strip(), meta
