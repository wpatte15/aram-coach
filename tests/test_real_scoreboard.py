"""Checks the scoreboard reader against a real ARAM: Mayhem scoreboard picture.

Run with: .venv\\Scripts\\python.exe tests\\test_real_scoreboard.py

Uses a recording from a real five-against-five match (captures/20261109-202234). The
picture and the game snapshot taken two seconds earlier stay in the captures folder
because they contain other players' names; the test is skipped when they are absent.

It verifies that each player's row is found from the K/D/A column, that a mouse position
on any player's augment icons maps to the right champion, and that an augment name in a
tooltip beside the mouse is read. The tooltip itself is drawn onto the real picture,
because no real augment tooltip has been captured yet.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from aramcoach import live, ocr  # noqa: E402
from aramcoach.static_data import StaticData  # noqa: E402

FOLDER = ROOT / "captures" / "20261109-202234"

# Mouse positions on augment icons in the real picture, and whose row each one is in.
CASES = [
    ((300, 331), "Taliyah"), ((329, 407), "Maokai"), ((358, 483), "Sivir"), ((300, 560), "Singed"), ((329, 636), "Gnar"),
    ((1560, 331), "Karthus"), ((1590, 407), "Shaco"), ((1620, 483), "Hwei"), ((1560, 560), "Annie"), ((1620, 636), "Taric"),
    ((329, 440), "Maokai"),        # the lower of a player's two rows of augment slots
    ((1590, 669), "Taric"),
    ((329, 760), None),            # below the board
    ((960, 150), None),            # above the board
]


def main():
    picture, snapshot = FOLDER / "scoreboard_t00676.png", FOLDER / "t00674.json"
    if not picture.exists() or not snapshot.exists():
        print("skipped: the real recording is not present")
        return
    sd = StaticData()
    image = Image.open(picture).convert("RGB")
    order = live.summarize(json.loads(snapshot.read_text(encoding="utf-8")), sd)["scoreboard"]
    lines = ocr.read_lines(image)
    anchors = ocr.score_anchors(image, lines)
    print(f"scores read from the picture: {len(anchors)} of 10 ->", sorted("/".join(map(str, a[0])) for a in anchors))
    assert len(anchors) >= 6, "too few K/D/A texts were read to place the rows"

    for cursor, expected in CASES:
        owner, details = ocr.scoreboard_owner(anchors, cursor, image.size, order)
        assert owner == expected, f"cursor {cursor}: expected {expected}, got {owner} ({details})"
    _owner, details = ocr.scoreboard_owner(anchors, (329, 407), image.size, order)
    print("row geometry:", details)
    assert details["left_team"] == "ORDER" and abs(details["row_pitch"] - 76) < 2 and abs(details["first_row_y"] - 349) < 4

    # A tooltip with an augment's name, drawn beside the mouse on the real picture.
    reader = ocr.OfferReader(sd.augments_described())
    for cursor, title, expected in [((1590, 407), "Still Here", "Shaco"), ((329, 636), "CRIMSON COBALT", "Gnar"),
                                    ((300, 331), "It's Killing Time", "Taliyah")]:
        frame = image.copy()
        draw = ImageDraw.Draw(frame)
        x, y = cursor
        left = x + 30 if x < 960 else x - 450
        draw.rectangle((left, y + 26, left + 420, y + 200), fill=(8, 12, 20), outline=(150, 130, 80))
        draw.text((left + 16, y + 38), title, font=ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 24), fill=(240, 220, 170))
        draw.text((left + 16, y + 84), "Effect text of the augment goes here.", fill=(190, 190, 190),
                  font=ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 17))
        frame_lines = ocr.read_lines(frame)
        augment = reader.tooltip(frame_lines, cursor)
        owner, _ = ocr.scoreboard_owner(ocr.score_anchors(frame, frame_lines), cursor, frame.size, order)
        assert augment and augment["name"] == title and owner == expected, (cursor, augment and augment["name"], owner)

    # With no tooltip open, nothing on the real scoreboard should be mistaken for an augment.
    for cursor, _expected in CASES[:10]:
        assert reader.tooltip(lines, cursor) is None, f"false augment read near {cursor}"
    print(f"real scoreboard passed: {len(CASES)} mouse positions mapped correctly, 3 tooltips read, no false reads")


if __name__ == "__main__":
    main()
