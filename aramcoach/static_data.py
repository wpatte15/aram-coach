"""Game reference data.

Items and champions come from Riot's Data Dragon. ARAM: Mayhem augments come from
CommunityDragon (ids, names, rarity) and the League wiki (descriptions). Everything is
cached on disk per patch version.
"""
from __future__ import annotations

import json
import re

import requests

from . import config

DDRAGON = "https://ddragon.leagueoflegends.com"
CDRAGON = "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1"
WIKI_AUGMENTS = "https://wiki.leagueoflegends.com/en-us/Module:MayhemAugmentData/data?action=raw"
MERAKI_CHAMPIONS = "https://cdn.merakianalytics.com/riot/lol/resources/latest/en-US/champions.json"
MERAKI_CHAMPION = "https://cdn.merakianalytics.com/riot/lol/resources/latest/en-US/champions/{}.json"
MERAKI_ITEMS = "https://cdn.merakianalytics.com/riot/lol/resources/latest/en-US/items.json"
_HEADERS = {"User-Agent": "Mozilla/5.0"}

# Data Dragon ships several parallel item sets. Ids below 100000 are the standard set and
# 12xxxx are ARAM-only additions. 77xxxx is a retro set used by a rotating ARAM variant.
# The rest (Arena and others) are never sold in an ARAM shop.
_CATALOG_FAMILIES = {"std": ("std", "12"), "77": ("77",)}


def item_family(item_id: int) -> str:
    return "std" if item_id < 100000 else str(item_id // 10000)


def catalog_family_for(item_ids) -> str:
    """Pick the item set a game is using from the item ids seen in it."""
    ids = list(item_ids)
    retro = sum(1 for i in ids if item_family(i) == "77")
    return "77" if retro > len(ids) / 2 else "std"


def norm(text) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def clean_html(text: str) -> str:
    text = re.sub(r"(<br\s*/?>\s*)+", "; ", text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([;:.,])", r"\1", text)
    text = re.sub(r"(;\s*)+", "; ", text)
    return text.strip(" ;")


_ITEM_STAT = re.compile(r"<attention>\s*([\d.]+)\s*(%?)\s*</attention>\s*([^<]+)")


def parse_item_stats(description: str) -> dict:
    """Read an item's stat lines from its Data Dragon description.

    Returns {"Ability Power": 95.0, "Magic Penetration%": 40.0}. Percent stats get a "%" suffix.
    The description is used because Data Dragon's own `stats` field omits newer stats such as omnivamp.
    """
    block = re.search(r"<stats>(.*?)</stats>", description or "", re.S)
    if not block:
        return {}
    return {name.strip() + ("%" if pct else ""): float(value)
            for value, pct, name in _ITEM_STAT.findall(block.group(1))}


_EFFECT_TAG = re.compile(r"<(passive|active)>(.*?)</\1>", re.S)
_ATTENTION = re.compile(r"<attention>\s*([A-Za-z][^<]*?)\s*</attention>")
# An item effect that fires when the holder heals or shields a teammate (Moonstone Renewer, Ardent Censer).
_ALLY_TRIGGER = re.compile(r"heal(ing)? or shield(ing)? an ally", re.I)


def split_effects(description: str) -> list:
    """An item's effects in the order its Data Dragon description lists them.

    Returns [(kind, name, body)], kind being "passive" or "active" (an effect behind the item's
    button) and body the effect's text as HTML. The same tags also mark a mention of an effect
    inside a sentence ("Empower your next <passive>Cleave</passive>"); a mention stays in the
    body it appears in. A heading comes first, after a line break, or after the end of a sentence.
    """
    body = re.sub(r"</?mainText>", "", description or "")
    stats = re.search(r"<stats>.*?</stats>", body, re.S)
    rest = body[stats.end():] if stats else body
    heads = []
    for match in _EFFECT_TAG.finditer(rest):
        before = rest[:match.start()].rstrip()
        bare = re.sub(r"(\s|<br\s*/?>|</?li>)+$", "", before)
        if not bare or bare != before or bare.endswith((".", "!", "?", "</active>", "</passive>")):
            heads.append(match)
    effects = []
    for i, match in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(rest)
        text = re.sub(r"\(\d+s\)", "", rest[match.end():end])
        effects.append((match.group(1), clean_html(match.group(2)).strip(" -:"), text))
    # "ACTIVE" and "Active -" are labels in front of the real heading, not effects of their own.
    return [e for i, e in enumerate(effects)
            if clean_html(e[2]) or i + 1 == len(effects) or effects[i + 1][0] != e[0]]


def _level_range(match) -> str:
    """A {{pp|...}} template: a value that grows with level or with something else, as "low to high"."""
    parts = match.group(1).split("|")
    plain = [p.strip() for p in parts if "=" not in p]
    steps = lambda text: re.sub(r"\s+(?:for|by)\s+[\d.]+\s*$", "", text)     # drops the number of steps
    shown = steps(plain[0]) if plain else ""
    percent = any(re.fullmatch(r"\s*key\d*\s*=\s*%\s*", p) for p in parts)
    low_high = [_sum(piece) for piece in shown.split(" to ")]
    out = " to ".join(low_high) + ("%" if percent and not shown.endswith("%") else "")
    # A value that grows with something about the enemy says what and over which range: Kraken Slayer's bonus
    # "by target's missing health, 0 to 100". Without it the item cannot be valued against a given enemy.
    grows = next((re.sub(r"'{2,}", "", p.split("=", 1)[1]).strip() for p in parts if re.match(r"\s*type\s*=", p)), "")
    if grows.startswith("target") and len(plain) >= 2:
        out += f" (by {grows}, {steps(plain[1])})"
    return out


def clean_item_effect(text: str, limit: int = 620) -> str:
    """One item effect from the Meraki dataset as plain sentences with their numbers.

    The dataset holds the wiki's text, markup included. Left out: what an effect does to minions
    and monsters, which decides no build in this mode. A sentence the markup leaves unreadable
    is dropped and the rest kept.
    """
    text = text or ""
    defined = dict(re.findall(r"\{\{#vardefineecho:([^|{}]*)\|([^{}]*)\}\}", text))       # a number named once, used again
    text = re.sub(r"\{\{#vardefineecho:[^|{}]*\|([^{}]*)\}\}", r"\1", text)
    text = re.sub(r"\{\{#var:([^{}]*)\}\}", lambda m: defined.get(m.group(1).strip(), ""), text)
    text = re.sub(r"\{\{stil\|[^|{}]*\|([^{}]*)\}\}", r"\1", text)                      # shows its second part
    text = re.sub(r"\{\{pp\|([^{}]*)\}\}", _level_range, text)
    text = clean_wiki(text)
    # "150 + (200-150)/10*(x-1) for 13": a value written as its formula by level
    text = re.sub(r"(\d+(?:\.\d+)?) \+ \((\d+(?:\.\d+)?)-\1\)/\d+\*\(x-1\)(?: for \d+)?", r"\1 to \2", text)
    text = re.sub(r"(\d(?:\.\d+)?%? to \d+(?:\.\d+)?%?) (?:for|by) \d+\b", r"\1", text)
    text = re.sub(r"\b(\d+(?:\.\d+)?)(?:; \d+(?:\.\d+)?){3,}; (\d+(?:\.\d+)?)\b", r"\1 to \2", text)   # a value listed step by step
    text = re.sub(r"\((\+ [^()]*)\)", r"\1", text)                                      # "20 (+ 1% bonus health)" reads as a sum
    text = re.sub(r",? (?:with the damage being|with a maximum of|capped at|increased to|reduced to|modified to)[^.;]*"
                  r"\b(?:minions?|monsters?|non-champions)\b[^.;]*", "", text)
    text = re.sub(r"\b(?:cr|er) (?=[a-z])", "", text)
    text = re.sub(r"\s+", " ", text).replace(" ,", ",").replace(" .", ".").strip()
    out = ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if re.match(r"(This executes|Against (?:minions|monsters)|Killing a non-champion)", sentence):
            continue
        if NO_EFFECT_TEXT in sentence or "{{" in sentence or "}}" in sentence or re.search(r"(?:^|[\s(])\*\d|\(x-1\)", sentence):
            return ""                    # half an effect misleads: the caller keeps the game's own wording for this one
        if out and len(out) + 1 + len(sentence) > limit:
            break
        out = f"{out} {sentence}".strip()
    return out


def item_text(description: str, numbers: dict | None = None) -> tuple:
    """An item description as catalog text. Returns (text, button_only, ally_trigger).

    Effects that work by themselves are marked "Passive" and effects behind the item's button
    "PRESS-TO-USE". button_only is true when nothing works without the button: every effect is
    behind it, or the passive depends on something only the button sets (Knight's Vow protects
    the ally its button names). ally_trigger is true when a passive fires on healing or
    shielding an ally.

    numbers: {normalised effect name: text with numbers} for this item, from the Meraki dataset.
    The game's own item file names every effect and leaves most of the numbers out: Unending
    Despair "deals magic damage to nearby enemy champions", Sunfire Aegis "deals magic damage
    per second", Thornmail "deals magic damage to the attacker". Without the numbers an item
    cannot be valued, and in 35 recorded matches the coach never once listed Unending Despair,
    which other players finish on every tank. Where the dataset has an effect of the same name,
    its text is used. The structure and both flags still come from the game's file.
    """
    numbers = numbers or {}
    stats = re.search(r"<stats>(.*?)</stats>", description or "", re.S)
    effects = split_effects(description)
    parts = [clean_html(stats.group(1))] if stats else []
    for kind, name, body in effects:
        label = "PRESS-TO-USE" if kind == "active" else "Passive"
        shown = numbers.get(norm(name)) or clean_html(body)
        parts.append(f"{label} {name}: {shown}".rstrip(": ") + ("" if shown else ":"))
    passives = [body for kind, _, body in effects if kind == "passive"]
    buttons = [body for kind, _, body in effects if kind == "active"]
    set_by_button = {word for body in buttons for word in _ATTENTION.findall(body)}
    standalone = [body for body in passives if not set_by_button & set(_ATTENTION.findall(body))]
    button_only = bool(buttons) and not standalone
    if not effects:                       # no tagged effects: keep whatever the description says
        parts = [clean_html(description or "")]
    text = "; ".join(p for p in parts if p).replace(":;", ":")
    return text, button_only, any(_ALLY_TRIGGER.search(clean_html(body)) for body in passives)


NO_EFFECT_TEXT = "(effect text not in the data)"
# Passives a player can have from one item only. Two Spellblade items give one Spellblade effect.
EXCLUSIVE_PASSIVES = ("Spellblade", "Lifeline", "Immolate", "Annul", "Cleave", "Manaflow")


def _sum(expr: str) -> str:
    """Work out a plain multiplication or division the wiki leaves written out, such as "35*4" or "30/12"."""
    found = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([*/])\s*(\d+(?:\.\d+)?)\s*", expr)
    if not found or (found.group(2) == "/" and float(found.group(3)) == 0):
        return expr.strip()
    a, b = float(found.group(1)), float(found.group(3))
    return f"{a * b if found.group(2) == '*' else a / b:.2f}".rstrip("0").rstrip(".")


def exclusive_groups(catalog: list) -> dict:
    """Finished items that share a passive a player can only have once: {passive name: [item names]}.

    Data Dragon does not list these groups. They are read off the item text: two items with a
    passive called Spellblade are both Spellblade items. Only the names in EXCLUSIVE_PASSIVES
    count, because other shared names (Grievous Wounds) do not stop a player owning both items.
    The rule is the standard game's and was not confirmed for ARAM: Mayhem from local data.
    """
    groups = {}
    for it in catalog:
        for name in set(re.findall(r"Passive ([A-Z][A-Za-z' -]+?):", it["text"])):
            if name in EXCLUSIVE_PASSIVES:
                groups.setdefault(name, []).append(it["name"])
    return {name: items for name, items in sorted(groups.items()) if len(items) >= 2}


def clean_wiki(text: str) -> str:
    """Reduce wiki markup to plain text: '''bold''', [[links]], and {{templates|shown text|...}}.

    Most templates show their first argument. A few carry meaning in their name, and reading
    only the argument loses it: {{g|25}} is 25 gold, {{adaptive|10}} is 10 adaptive force,
    {{rd|75|50}} is 75 for melee champions and 50 for ranged ones, {{ap|35*4}} is 140. A
    template that fetches text this module cannot see is replaced by NO_EFFECT_TEXT.
    """
    text = text.replace("'''", "").replace("''", "")
    text = re.sub(r"\[\[File:[^\]]*\]\]", "", text)
    text = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", text)
    innermost = re.compile(r"\{\{([^{}]*)\}\}")

    def shown(match):
        parts = match.group(1).split("|")
        name = parts[0].strip().lower()
        args = [p for p in parts[1:] if "=" not in p]
        first = args[0].strip() if args else ""
        if name.startswith("#invoke"):
            return NO_EFFECT_TEXT
        if name == "g":
            return f"{first} gold"
        if name == "adaptive":
            return f"{first} adaptive force"
        if name == "rd" and len(args) >= 2:
            return f"{first} (melee) / {args[1].strip()} (ranged)"
        if name == "ap":
            return _sum(first)
        if name == "pp":                         # a value that grows with level, sometimes written as "6/3 to 60/3"
            return " to ".join(_sum(part) for part in first.split(" to "))
        if name == "tip" and len(args) >= 2:
            return args[1].strip()               # {{tip|heal|healed}} shows "healed"
        if name == "critical damage":
            return f"{first}%"
        if name == "times":
            return "×"
        if name == "ft":
            return f" {first} "                  # one of two wordings of the same thing; the wiki glues it to its neighbours
        return first

    for _ in range(8):
        replaced = innermost.sub(shown, text)
        if replaced == text:
            break
        text = replaced
    for _ in range(4):                                       # "11*4 to 80*4", and a chain such as "150*0.8*1.75"
        worked = re.sub(r"\d+(?:\.\d+)?\*\d+(?:\.\d+)?", lambda m: _sum(m.group(0)), text)
        if worked == text:
            break
        text = worked
    text = re.sub(r"\b(?:er|cr) (?=\d)", "", text)          # the wiki's markers for how a range is measured
    return clean_html(text)


def parse_wiki_augments(lua: str) -> dict:
    """Parse the wiki's Lua table of augments into {name: {name, tier, description}}."""
    out = {}
    heads = list(re.finditer(r'^\t\["((?:[^"\\]|\\.)+)"\]\s*=\s*\{', lua, re.M))
    for i, head in enumerate(heads):
        block = lua[head.end(): heads[i + 1].start() if i + 1 < len(heads) else len(lua)]
        desc = re.search(r'\["description"\]\s*=\s*"((?:[^"\\]|\\.)*)"', block)
        tier = re.search(r'\["tier"\]\s*=\s*"([^"]*)"', block)
        name = head.group(1).replace('\\"', '"')
        out[name] = {
            "name": name,
            "tier": tier.group(1) if tier else "",
            "description": clean_wiki(desc.group(1).replace('\\"', '"')) if desc else "",
        }
    return out


def ability_casts(champion: dict, limit: int = 600) -> dict:
    """How each ability of a champion is cast, from one champion's entry in the Meraki dataset.

    Returns {slot: {"aim": how it is targeted, "text": what each press does}} for P, Q, W, E
    and R. The text keeps the dataset's own words, such as "Active: ..." for the first press
    and "Recast: ..." for the second, which is the part Data Dragon's descriptions leave out.
    """
    out = {}
    for slot, forms in (champion.get("abilities") or {}).items():
        form = forms[0] if forms else {}
        text = " ".join((e.get("description") or "").strip() for e in form.get("effects") or [])
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            out[slot] = {"aim": (form.get("targeting") or "").strip(), "text": text[:limit]}
    return out


def _values(values: list) -> str:
    """Per-rank values as text: one number when every rank is the same, else 90/110/130."""
    texts = [f"{v:g}" for v in values]
    return texts[0] if len(set(texts)) == 1 else "/".join(texts)


def _ability_numbers(form: dict) -> list:
    """Numeric lines for one ability from the Meraki dataset, such as 'Heal: 90/110/130/150/170 +50% AP'."""
    lines = []
    for effect in form.get("effects") or []:
        for leveling in effect.get("leveling") or []:
            parts = []
            for i, modifier in enumerate(leveling.get("modifiers") or []):
                unit = ((modifier.get("units") or [""])[0] or "").strip()
                text = _values(modifier.get("values") or []) + (unit if unit.startswith("%") else f" {unit}" if unit else "")
                parts.append(text if i == 0 else f"+{text}")
            if parts and leveling.get("attribute"):
                lines.append(f"{leveling['attribute']}: {' '.join(parts)}")
    return lines[:4]


# A sentence of an ability that says how an item stat changes it: Garen's spin "can critically strike for (50% +
# 40%) bonus physical damage" and spins "7 (+ 1 per 25% bonus attack speed) times". The text Claude reads per
# ability is cut at 600 characters, and for Garen the first of those two fell behind the cut.
_ITEM_RULE = re.compile(r"critical(?:ly)? str|bonus attack speed|on-hit|on-attack|life steal|ability haste", re.I)


def kit_data(entry: dict) -> dict:
    """One champion's attack type and ability numbers from the Meraki dataset, as data a program can work with.

    Returns {ranged, as_ratio, abilities}. abilities maps a slot (P, Q, W, E, R) to {name, kind,
    cooldown, haste, lines, rules}: kind is the dataset's damage type, cooldown the seconds per
    rank, haste whether ability haste shortens it, and lines the numeric lines of the ability,
    each {attr, mods} with mods a list of [values, unit]. A list of values runs per rank, or per
    champion level when it has 18 entries. rules holds up to three sentences of the ability that
    say how an item stat changes it (see _ITEM_RULE). `_ability_numbers` keeps the same lines as
    text for Claude to read; this keeps all of them as numbers for the calculators (see calc.py).
    """
    stats = entry.get("stats") or {}
    flat = lambda key: (stats.get(key) or {}).get("flat") or 0
    out = {"ranged": entry.get("attackType") == "RANGED", "as_ratio": flat("attackSpeedRatio") or flat("attackSpeed"),
           "abilities": {}}
    for slot, forms in (entry.get("abilities") or {}).items():
        if not forms:
            continue
        form = forms[0]
        lines, rules = [], []
        for effect in form.get("effects") or []:
            for leveling in effect.get("leveling") or []:
                mods = [[m.get("values") or [], ((m.get("units") or [""])[0] or "").strip()]
                        for m in leveling.get("modifiers") or [] if m.get("values")]
                if leveling.get("attribute") and mods:
                    lines.append({"attr": leveling["attribute"].strip(), "mods": mods})
            text = re.sub(r"\s+", " ", re.sub(r"[\[\]]", " ", effect.get("description") or "")).strip()   # stray wiki brackets
            for sentence in re.split(r"(?<=[.!?])\s+", text):
                if _ITEM_RULE.search(sentence) and len(rules) < 3:
                    rules.append(sentence[:260])
        cooldown = form.get("cooldown") or {}
        out["abilities"][slot] = {
            "name": form.get("name") or "", "kind": form.get("damageType") or "",
            "cooldown": ((cooldown.get("modifiers") or [{}])[0].get("values") or []),
            "haste": bool(cooldown.get("affectedByCdr", True)), "lines": lines, "rules": rules}
    return out


class StaticData:
    def __init__(self):
        self.version = self._resolve_version()
        self.dir = config.CACHE_DIR / self.version
        self.dir.mkdir(parents=True, exist_ok=True)
        self._catalogs = {}
        self._load_items()
        self._load_champions()
        self._load_ability_numbers()
        self._load_augments()

    # ---- downloads -------------------------------------------------------

    def _resolve_version(self) -> str:
        try:
            return requests.get(f"{DDRAGON}/api/versions.json", timeout=10).json()[0]
        except (requests.RequestException, ValueError, IndexError):
            cached = [p.name for p in config.CACHE_DIR.glob("*") if (p / "item.json").exists()]
            if not cached:
                raise RuntimeError("Cannot reach Data Dragon and no game data is cached yet.")
            return max(cached, key=lambda v: [int(x) if x.isdigit() else 0 for x in v.split(".")])

    def _text(self, url: str, name: str) -> str:
        path = self.dir / name
        if path.exists():
            return path.read_text(encoding="utf-8")
        resp = requests.get(url, headers=_HEADERS, timeout=40)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        path.write_text(resp.text, encoding="utf-8")
        return resp.text

    def _json(self, url: str, name: str):
        return json.loads(self._text(url, name))

    # ---- items -----------------------------------------------------------

    def _item_numbers(self) -> dict:
        """Effect text with numbers for every item in the Meraki dataset: {item id: {effect name: text}}.

        Kept per patch as a small file. Best effort, like the champion numbers: without it the
        catalog shows the game's own text. The dataset describes the standard game and can lag a
        patch, so a number can be off where this mode changes an item.
        """
        path = self.dir / "item_numbers.json"
        self.item_numbers_error = None
        try:
            if path.exists():
                return {int(k): v for k, v in json.loads(path.read_text(encoding="utf-8")).items()}
            resp = requests.get(MERAKI_ITEMS, headers=_HEADERS, timeout=120)
            resp.raise_for_status()
            out = {}
            for entry in resp.json().values():
                effects = {}
                for effect in (entry.get("passives") or []) + (entry.get("active") or []):
                    text = clean_item_effect(effect.get("effects") or "")
                    if effect.get("name") and text:
                        effects.setdefault(norm(effect["name"]), text)
                if entry.get("id") and effects:
                    out[int(entry["id"])] = effects
            path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
            return out
        except (requests.RequestException, ValueError, OSError, AttributeError, TypeError) as exc:
            self.item_numbers_error = repr(exc)
            return {}

    def _load_items(self):
        raw = self._json(f"{DDRAGON}/cdn/{self.version}/data/en_US/item.json", "item.json")["data"]
        numbers = self._item_numbers()
        self.items = {}
        for key, r in raw.items():
            iid = int(key)
            gold = r["gold"]
            # Keep the difference between effects that work by themselves and ones that need a button press.
            text, button_only, ally_trigger = item_text(r.get("description", ""), numbers.get(iid))
            plain = (r.get("plaintext") or "").strip()
            self.items[iid] = {
                "id": iid,
                "name": r["name"],
                "total": gold["total"],
                "base": gold["base"],
                "from": [int(x) for x in r.get("from", [])],
                "into": [int(x) for x in r.get("into", [])],
                "tags": r.get("tags", []),
                "stats": parse_item_stats(r.get("description", "")),
                "text": text if len(text) > 60 or not plain else f"{text}. {plain}".strip(". "),
                "button_only": button_only,     # does nothing without its button
                "ally_trigger": ally_trigger,   # has a passive that fires on healing or shielding an ally
                "family": item_family(iid),
                "upgrade_of": int(r["specialRecipe"]) if r.get("specialRecipe") else None,
                # Sold in a Howling Abyss shop to any champion.
                "shop": bool(
                    r.get("maps", {}).get("12") and gold["purchasable"] and gold["total"] > 0
                    and r.get("inStore", True) and not r.get("requiredChampion") and not r.get("requiredAlly")
                ),
            }

    def catalog(self, family: str = "std") -> list:
        """Finished items a player can build in the given item set, ordered by id."""
        if family not in self._catalogs:
            fams = _CATALOG_FAMILIES[family]
            shop = {i for i, it in self.items.items() if it["shop"] and it["family"] in fams}
            self._catalogs[family] = [
                self.items[i] for i in sorted(shop)
                if not any(x in shop for x in self.items[i]["into"])
                and self.items[i]["total"] >= 500
                and not {"Consumable", "Trinket"} & set(self.items[i]["tags"])
            ]
        return self._catalogs[family]

    def exclusive_groups(self, family: str = "std") -> dict:
        """The groups of finished items of which a player can use only one (see exclusive_groups)."""
        return exclusive_groups(self.catalog(family))

    def find_item(self, name: str, family: str = "std"):
        """Look an item up by name within one item set. Returns None when the patch has no such item."""
        fams = _CATALOG_FAMILIES[family]
        wanted = norm(name)
        for iid in sorted(self.items):
            it = self.items[iid]
            if it["family"] in fams and it["shop"] and norm(it["name"]) == wanted:
                return it
        return None

    # ---- champions -------------------------------------------------------

    def _load_champions(self):
        raw = self._json(f"{DDRAGON}/cdn/{self.version}/data/en_US/champion.json", "champion.json")["data"]
        self.champions = {
            cid: {"id": cid, "name": c["name"], "tags": c.get("tags", []), "resource": c.get("partype", ""),
                  "base": c.get("stats", {}), "difficulty": (c.get("info") or {}).get("difficulty"),
                  # The game's own 1-10 scores for attack and magic: which kind of damage the champion usually deals.
                  "attack": (c.get("info") or {}).get("attack"), "magic": (c.get("info") or {}).get("magic")}
            for cid, c in raw.items()
        }
        # The League client identifies champions by number, for example 412 for Thresh.
        self.champ_by_key = {int(c["key"]): cid for cid, c in raw.items() if str(c.get("key", "")).isdigit()}
        self._champ_lookup = {}
        for cid, c in self.champions.items():
            self._champ_lookup[norm(cid)] = cid
            self._champ_lookup[norm(c["name"])] = cid

    def _load_ability_numbers(self):
        """Stat growth and per-rank ability numbers from the Meraki Analytics community dataset.

        Data Dragon has ability text but no usable numbers, and in 16.22 it reports zero attack
        damage growth for every champion. Meraki fills both gaps. It is maintained by volunteers
        and can lag a patch or miss the newest champions, so it is best effort: without it the
        coach falls back to Data Dragon alone. The 13 MB download is reduced to a small file
        once per patch.
        """
        compact_path, kits_path = self.dir / "ability_numbers.json", self.dir / "kits.json"
        self.ability_numbers, self.ability_error, self.kits = {}, None, {}
        try:
            if compact_path.exists():
                self.ability_numbers = json.loads(compact_path.read_text(encoding="utf-8"))
            if kits_path.exists():
                self.kits = json.loads(kits_path.read_text(encoding="utf-8"))
            if not self.ability_numbers or not self.kits:
                resp = requests.get(MERAKI_CHAMPIONS, headers=_HEADERS, timeout=120)
                resp.raise_for_status()
                numbers, kits = {}, {}
                for entry in resp.json().values():
                    cid = self.champ_by_key.get(entry.get("id"))
                    if cid is None:
                        continue
                    numbers[cid] = {
                        "ad_per_level": ((entry.get("stats") or {}).get("attackDamage") or {}).get("perLevel") or 0,
                        "abilities": {slot: _ability_numbers(forms[0])
                                      for slot, forms in (entry.get("abilities") or {}).items() if forms},
                    }
                    kits[cid] = kit_data(entry)
                # A file that exists is left as it is: the text Claude reads must not change in the middle of a patch.
                if not self.ability_numbers:
                    self.ability_numbers = numbers
                    compact_path.write_text(json.dumps(numbers), encoding="utf-8")
                if not self.kits:
                    self.kits = kits
                    kits_path.write_text(json.dumps(kits), encoding="utf-8")
        except (requests.RequestException, ValueError, OSError, AttributeError) as exc:
            self.ability_error = repr(exc)
        for cid, data in self.ability_numbers.items():
            base = (self.champions.get(cid) or {}).get("base")
            if base is not None and not base.get("attackdamageperlevel"):
                base["attackdamageperlevel"] = data.get("ad_per_level") or 0

    def champ_id(self, display_name: str = "", raw_name: str = ""):
        """Map the game API's champion naming to a Data Dragon champion id."""
        for candidate in (raw_name.rsplit("_", 1)[-1], display_name):
            cid = self._champ_lookup.get(norm(candidate))
            if cid:
                return cid
        return None

    def how_cast(self, cid: str) -> dict:
        """How each of one champion's abilities is cast (see ability_casts). Empty when it cannot be had.

        Data Dragon says what an ability does but often not how it is used: Xerath's ultimate is
        "gains numerous long-range barrages", with no word that each shot is a second press of R
        aimed with the mouse. The Meraki dataset has that. Fetched per champion and kept per patch.
        """
        path = self.dir / f"casts_{cid}.json"
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
            resp = requests.get(MERAKI_CHAMPION.format(cid), headers=_HEADERS, timeout=20)
            resp.raise_for_status()
            casts = ability_casts(resp.json())
            path.write_text(json.dumps(casts, ensure_ascii=False), encoding="utf-8")
            return casts
        except (requests.RequestException, ValueError, OSError, AttributeError, TypeError):
            return {}

    def champion_notes(self, cid: str):
        """Abilities and tips for one champion. Returns None when the lookup fails."""
        try:
            c = self._json(
                f"{DDRAGON}/cdn/{self.version}/data/en_US/champion/{cid}.json", f"champion_{cid}.json"
            )["data"][cid]
        except (requests.RequestException, ValueError, KeyError):
            return None
        numbers = (self.ability_numbers.get(cid) or {}).get("abilities") or {}
        with_numbers = lambda slot: f" | numbers by rank: {'; '.join(numbers[slot])}" if numbers.get(slot) else ""
        spells = []
        for key, s in zip("QWER", c.get("spells", [])):
            cooldown = s.get("cooldownBurn", "")
            spells.append(f"{key} {s['name']}: {clean_html(s.get('description', ''))}"
                          + (f" (cooldown {cooldown}s)" if cooldown and cooldown != "0" else "") + with_numbers(key))
        passive = c.get("passive") or {}
        return {
            "passive": f"Passive {passive.get('name', '')}: {clean_html(passive.get('description', ''))}" + with_numbers("P"),
            "spells": spells,
            "allytips": [clean_html(t) for t in c.get("allytips", [])],
            "enemytips": [clean_html(t) for t in c.get("enemytips", [])],
        }

    # ---- augments --------------------------------------------------------

    def _wiki_augment_text(self) -> str:
        """Augment descriptions from the League wiki.

        The wiki sits behind a bot check that can refuse this download with a 403. When that
        happens, the copy cached for an earlier patch is used, and failing that the copy in
        aramcoach/data. To refresh it by hand, save the page at WIKI_AUGMENTS to
        cache/<version>/mayhem_augments.lua.
        """
        name = "mayhem_augments.lua"
        try:
            return self._text(WIKI_AUGMENTS, name)
        except requests.RequestException:
            older = sorted(config.CACHE_DIR.glob(f"*/{name}"), key=lambda p: p.stat().st_mtime)
            if older:
                return older[-1].read_text(encoding="utf-8")
            # A copy ships with the project so a fresh install works. It dates from patch 16.22.
            return (config.PKG_DIR / "data" / name).read_text(encoding="utf-8")

    def _load_augments(self):
        """Best effort. The coach runs without augment data if these sources are unreachable."""
        self._aug_by_name, self._aug_by_id, self.augment_error = {}, {}, None
        self._described = None
        described = {}
        try:
            described = {norm(k): v for k, v in parse_wiki_augments(self._wiki_augment_text()).items()}
        except (requests.RequestException, OSError) as exc:
            self.augment_error = f"augment descriptions: {exc!r}"
        try:
            for a in self._json(f"{CDRAGON}/cherry-augments.json", "cherry-augments.json"):
                name = a.get("nameTRA") or ""
                entry = described.get(norm(name)) or {
                    "name": name, "tier": (a.get("rarity") or "").lstrip("k"), "description": "",
                }
                self._aug_by_id[a.get("id")] = entry
                self._aug_by_name.setdefault(norm(name), entry)
                self._aug_by_name.setdefault(norm(a.get("augmentNameId") or ""), entry)
        except (requests.RequestException, ValueError, OSError) as exc:
            self.augment_error = f"augment names: {exc!r}"
        for key, entry in described.items():
            self._aug_by_name.setdefault(key, entry)
        # The wiki table leaves out quests and a few other augments. Their text, where the coach has
        # read it from arammayhem.com (see augtext.texts), fills the gap.
        try:
            extra = json.loads((self.dir / "augment_text.json").read_text(encoding="utf-8")).get("data") or {}
        except (OSError, ValueError):
            extra = {}
        for name, text in extra.items():
            entry = self._aug_by_name.get(norm(name))
            if entry is not None and text and not entry["description"]:
                entry["description"] = text
            elif entry is not None and text and NO_EFFECT_TEXT in entry["description"]:
                # Keep the wiki's own sentence: it names the summoner spell the augment gives, which is how the
                # coach recognises the augment in another player's spell slot (see live.augments_from_spells).
                entry["description"] = entry["description"].replace(NO_EFFECT_TEXT, text)

    def augments_described(self) -> list:
        """Every augment that has a description, one entry per augment."""
        if self._described is None:
            self._described = list(
                {e["name"]: e for e in self._aug_by_name.values() if e["name"] and e["description"]}.values())
        return self._described

    def augments_all(self) -> list:
        """Every augment name known, described or not, one entry per augment. Used to recognise names on screen."""
        return list({e["name"]: e for e in self._aug_by_name.values() if e["name"]}.values())

    def augment(self, key):
        """Look an augment up by numeric id, display name, or internal name."""
        if isinstance(key, bool) or key is None:
            return None
        if isinstance(key, int) or str(key).isdigit():
            return self._aug_by_id.get(int(key))
        return self._aug_by_name.get(norm(key))
