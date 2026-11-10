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


def clean_wiki(text: str) -> str:
    """Reduce wiki markup to plain text: '''bold''', [[links]], and {{templates|shown text|...}}."""
    text = text.replace("'''", "").replace("''", "")
    text = re.sub(r"\[\[File:[^\]]*\]\]", "", text)
    text = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", text)
    innermost = re.compile(r"\{\{([^{}]*)\}\}")

    def shown(match):
        args = [p for p in match.group(1).split("|")[1:] if "=" not in p]
        return args[0].strip() if args else ""

    for _ in range(8):
        replaced = innermost.sub(shown, text)
        if replaced == text:
            break
        text = replaced
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

    def _load_items(self):
        raw = self._json(f"{DDRAGON}/cdn/{self.version}/data/en_US/item.json", "item.json")["data"]
        self.items = {}
        for key, r in raw.items():
            iid = int(key)
            gold = r["gold"]
            # Keep the difference between effects that work by themselves and ones that need a button press.
            marked = re.sub(r"<active>(.*?)</active>", r"PRESS-TO-USE \1:", r.get("description", ""), flags=re.S)
            marked = re.sub(r"<passive>(.*?)</passive>", r"Passive \1:", marked, flags=re.S)
            text = clean_html(marked).replace(":;", ":")
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
                  "base": c.get("stats", {})}
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
        compact_path = self.dir / "ability_numbers.json"
        self.ability_numbers, self.ability_error = {}, None
        try:
            if compact_path.exists():
                self.ability_numbers = json.loads(compact_path.read_text(encoding="utf-8"))
            else:
                resp = requests.get(MERAKI_CHAMPIONS, headers=_HEADERS, timeout=120)
                resp.raise_for_status()
                for entry in resp.json().values():
                    cid = self.champ_by_key.get(entry.get("id"))
                    if cid is None:
                        continue
                    self.ability_numbers[cid] = {
                        "ad_per_level": ((entry.get("stats") or {}).get("attackDamage") or {}).get("perLevel") or 0,
                        "abilities": {slot: _ability_numbers(forms[0])
                                      for slot, forms in (entry.get("abilities") or {}).items() if forms},
                    }
                compact_path.write_text(json.dumps(self.ability_numbers), encoding="utf-8")
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

    def augments_described(self) -> list:
        """Every augment that has a description, one entry per augment."""
        if self._described is None:
            self._described = list(
                {e["name"]: e for e in self._aug_by_name.values() if e["name"] and e["description"]}.values())
        return self._described

    def augment(self, key):
        """Look an augment up by numeric id, display name, or internal name."""
        if isinstance(key, bool) or key is None:
            return None
        if isinstance(key, int) or str(key).isdigit():
            return self._aug_by_id.get(int(key))
        return self._aug_by_name.get(norm(key))
