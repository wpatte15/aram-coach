"""Reads augments off the screen with Windows' built-in text recognition.

Riot's local APIs do not report augments, so tools for this mode read them from the screen.
Windows.Media.Ocr runs locally in tens of milliseconds, which makes it cheap enough to
check the screen continuously: no hotkey and no model call are needed to know what is there.

Two things are read:

- The offer: three cards with a title each. Layout facts come from the open-source Mayhem
  overlays Hexsight and minimal-mayhem-overlay: the titles sit in one row between about 33%
  and 52% of the game's height. The whole band is read in one pass and matches are grouped
  by row, so exact card positions do not matter.
- Hover tooltips on the scoreboard: while Tab is held, pointing at another player's augment
  shows its name. That name is found near the mouse cursor, and the player is worked out
  from which scoreboard row the cursor is on.
"""
from __future__ import annotations

import asyncio
import difflib
import re
import threading

from PIL import Image

# Fractions of the screen that contain the offer's card titles, with a margin.
BAND = (0.08, 0.28, 0.92, 0.58)        # left, top, right, bottom
_TARGET_HEIGHT = 420                    # the band is scaled to about this height before reading

_engine = None
_engine_lock = threading.Lock()         # Windows allows one recognition at a time per engine


def _get_engine():
    global _engine
    if _engine is None:
        from winrt.windows.globalization import Language
        from winrt.windows.media.ocr import OcrEngine
        _engine = (OcrEngine.try_create_from_language(Language("en-US"))
                   or OcrEngine.try_create_from_user_profile_languages())
        if _engine is None:
            raise RuntimeError("Windows has no text-recognition language installed.")
    return _engine


def read_lines(image: Image.Image) -> list:
    """Recognise text in an image.

    Returns one dict per line: text, x and y of its centre, h (height), and words, each with
    its own text, x, y and h. Positions are in image pixels.
    """
    from winrt.windows.graphics.imaging import BitmapAlphaMode, BitmapPixelFormat, SoftwareBitmap
    from winrt.windows.storage.streams import DataWriter

    engine = _get_engine()
    rgba = image.convert("RGBA")
    writer = DataWriter()
    writer.write_bytes(rgba.tobytes())
    bitmap = SoftwareBitmap.create_copy_from_buffer(
        writer.detach_buffer(), BitmapPixelFormat.RGBA8, rgba.width, rgba.height, BitmapAlphaMode.PREMULTIPLIED)

    async def recognise():
        return await engine.recognize_async(bitmap)

    with _engine_lock:
        result = asyncio.run(recognise())
    lines = []
    for line in result.lines:
        words = [{"text": w.text, "x": w.bounding_rect.x + w.bounding_rect.width / 2,
                  "y": w.bounding_rect.y + w.bounding_rect.height / 2, "h": w.bounding_rect.height,
                  "left": w.bounding_rect.x, "right": w.bounding_rect.x + w.bounding_rect.width}
                 for w in line.words]
        if not words:
            continue
        left, right = min(w["left"] for w in words), max(w["right"] for w in words)
        lines.append({"text": line.text, "x": (left + right) / 2, "y": sum(w["y"] for w in words) / len(words),
                      "h": max(w["h"] for w in words), "words": words})
    return lines


def fold(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def word_windows(line: dict, longest: int = 5):
    """Every run of one to `longest` neighbouring words in a line, as (text, x, y, h)."""
    words = line["words"]
    for start in range(len(words)):
        for end in range(start + 1, min(start + longest, len(words)) + 1):
            run = words[start:end]
            yield (" ".join(w["text"] for w in run), (run[0]["left"] + run[-1]["right"]) / 2,
                   sum(w["y"] for w in run) / len(run), max(w["h"] for w in run))


def locate(lines: list, names: dict, cutoff: float = 0.8) -> list:
    """Find known names in recognised text. names: {folded name: value}. Returns [(value, x, y)].

    Used to find each player's row on the scoreboard. A name can sit inside a longer line, so
    runs of words are tried as well as whole lines.
    """
    found, folded_names = {}, list(names)
    for line in lines:
        for text, x, y, _h in word_windows(line, longest=3):
            folded = fold(text)
            if len(folded) < 3:
                continue
            if folded in names:
                key, score = folded, 1.0
            else:
                close = difflib.get_close_matches(folded, folded_names, n=1, cutoff=cutoff) if len(folded) >= 5 else []
                if not close:
                    continue
                key, score = close[0], difflib.SequenceMatcher(None, folded, close[0]).ratio()
            if score > found.get(key, (0,))[0]:
                found[key] = (score, x, y)
    return [(names[key], x, y) for key, (_score, x, y) in found.items()]


_SHARD = re.compile(r"^(?:[A-Z][a-z]+ ){1,2}Shard$")
_SCORE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{1,2})$")
ROW_PITCH = 76 / 1080      # distance between scoreboard rows as a share of screen height (measured at 1080p)


def score_anchors(image: Image.Image, lines: list | None = None) -> list:
    """K/D/A texts on the scoreboard, as [((kills, deaths, assists), x, y)] in screen pixels.

    Each scoreboard row shows its player's score, and those scores are also in the game API,
    so they tie a row on screen to a player. The middle of the screen is read a second time at
    double size, because some rows are missed at normal size.
    """
    found = {}

    def collect(text_lines, scale=1.0, dx=0, dy=0):
        for line in text_lines:
            for word in line["words"]:
                match = _SCORE.match(word["text"].replace(" ", ""))
                if match:
                    x, y = word["x"] * scale + dx, word["y"] * scale + dy
                    found[(match.groups(), round(x / 60), round(y / 20))] = (tuple(map(int, match.groups())), x, y)

    collect(lines if lines is not None else read_lines(image))
    width, height = image.size
    box = (int(0.2 * width), int(0.25 * height), int(0.8 * width), int(0.67 * height))
    middle = image.crop(box)
    collect(read_lines(middle.resize((middle.width * 2, middle.height * 2), Image.LANCZOS)), 0.5, box[0], box[1])
    return list(found.values())


def scoreboard_owner(anchors: list, cursor: tuple, size: tuple, order: list):
    """The champion whose scoreboard row the cursor is on, plus what was measured.

    anchors: output of score_anchors. order: every player as {team, champion, kda} in the game
    API's order, which is also the scoreboard's row order within each team. One team is listed
    on the left half of the screen and the other on the right; which is which is decided by
    whose scores appear on each side. Rows are evenly spaced, so two matched rows are enough to
    place all five. Returns (champion or None, details for the log).
    """
    width, height = size
    teams = {}
    for player in order:
        teams.setdefault(player["team"], []).append(player)
    if len(teams) != 2:
        return None, {"reason": "need two teams"}
    first, second = list(teams)
    left = [a for a in anchors if a[1] < width / 2]
    right = [a for a in anchors if a[1] >= width / 2]
    hits = lambda side, team: sum(1 for a in side if any(tuple(p["kda"]) == a[0] for p in teams[team]))
    if hits(left, first) + hits(right, second) >= hits(left, second) + hits(right, first):
        left_team, right_team = first, second
    else:
        left_team, right_team = second, first

    points = []                                   # (row index, y) for rows identified by a unique score
    for side, team in ((left, left_team), (right, right_team)):
        for score, _x, y in side:
            rows = [i for i, p in enumerate(teams[team]) if tuple(p["kda"]) == score]
            if len(rows) == 1:
                points.append((rows[0], y))
    if not points:
        return None, {"reason": "no score matched a player", "anchors": len(anchors)}
    pitch = ROW_PITCH * height
    if len({i for i, _ in points}) >= 2:          # least-squares line through (row index, y)
        n = len(points)
        mean_i, mean_y = sum(i for i, _ in points) / n, sum(y for _, y in points) / n
        spread = sum((i - mean_i) ** 2 for i, _ in points)
        pitch = sum((i - mean_i) * (y - mean_y) for i, y in points) / spread
        first_row = mean_y - pitch * mean_i
    else:
        first_row = points[0][1] - points[0][0] * pitch

    team = left_team if cursor[0] < width / 2 else right_team
    index = round((cursor[1] - first_row) / pitch)
    details = {"left_team": left_team, "first_row_y": round(first_row), "row_pitch": round(pitch, 1),
               "rows_matched": len(points), "side": "left" if team == left_team else "right", "row": index}
    if not 0 <= index < len(teams[team]) or abs(cursor[1] - (first_row + index * pitch)) > 0.48 * pitch:
        return None, {**details, "reason": "cursor is not on a row"}
    return teams[team][index]["champion"], details


class OfferReader:
    """Finds augment names on the screen."""

    def __init__(self, augments: list):
        """augments: [{name, tier, description}] for every augment the mode can offer."""
        self.by_fold = {fold(a["name"]): a for a in augments if len(fold(a["name"])) >= 3}
        self.folds = list(self.by_fold)

    def match(self, text: str):
        """The augment a piece of recognised text names, or None. Tolerates small reading errors."""
        folded = fold(text)
        if folded in self.by_fold:
            return self.by_fold[folded]
        shard = _SHARD.match(text.strip())
        if shard:                                 # stat shards are offered like augments but are not in the data
            return {"name": shard.group(0), "tier": "Shard", "description": ""}
        if len(folded) < 6:
            return None                           # short names must match exactly
        close = difflib.get_close_matches(folded, self.folds, n=2, cutoff=0.84)
        if not close:
            return None
        ratio = lambda name: difflib.SequenceMatcher(None, folded, name).ratio()
        if len(close) == 2 and ratio(close[0]) - ratio(close[1]) < 0.06:
            return None                           # two names fit about equally well: do not guess
        return self.by_fold[close[0]]

    def find(self, screenshot: Image.Image) -> list:
        """Augments on offer, left to right. Empty unless at least two titles sit in one row."""
        width, height = screenshot.size
        box = (int(BAND[0] * width), int(BAND[1] * height), int(BAND[2] * width), int(BAND[3] * height))
        band = screenshot.crop(box)
        scale = max(0.75, min(2.0, _TARGET_HEIGHT / band.height))
        if abs(scale - 1) > 0.05:
            band = band.resize((int(band.width * scale), int(band.height * scale)), Image.LANCZOS)
        hits = []
        for line in read_lines(band):
            augment = self.match(line["text"])
            if augment:
                hits.append({**line, "augment": augment})
        best = []
        for anchor in hits:                       # keep the largest group of titles that share a row
            row = [h for h in hits if abs(h["y"] - anchor["y"]) < 1.2 * max(h["h"], anchor["h"])]
            if len(row) > len(best):
                best = row
        if len(best) < 2:
            return []
        seen, offer = set(), []
        for hit in sorted(best, key=lambda h: h["x"]):
            if hit["augment"]["name"] not in seen:
                seen.add(hit["augment"]["name"])
                offer.append(hit["augment"])
        return offer[:4]

    def tooltip(self, lines: list, cursor: tuple, reach: tuple = (620, 420)):
        """The augment named in a hover tooltip near the cursor, or None.

        lines: output of read_lines for the whole screen. A tooltip opens beside the cursor,
        so only text within `reach` pixels of it counts. A whole line may match loosely; a run
        of words inside a longer line must match exactly. The match closest to the cursor wins.
        """
        cx, cy = cursor
        best = None
        for line in lines:
            candidates = [(self.match(line["text"]), line["x"], line["y"])]
            if len(line["words"]) > 1:
                candidates += [(self.by_fold.get(fold(text)), x, y) for text, x, y, _h in word_windows(line)
                               if len(fold(text)) >= 4]
            for augment, x, y in candidates:
                if augment is None or abs(x - cx) > reach[0] or abs(y - cy) > reach[1]:
                    continue
                distance = abs(x - cx) + abs(y - cy)
                if best is None or distance < best[0]:
                    best = (distance, augment)
        return best[1] if best else None
