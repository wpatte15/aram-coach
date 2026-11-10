"""Plans before the match loads, using the League client instead of the game API.

Champion select: the player's champion and teammates are known. Claude makes a build, and it
is written into the in-game shop as an item set (the game reads item sets when it loads).

Loading screen: the enemy team becomes known. Claude makes the full first plan, so it is on
the panel when the player spawns instead of ten seconds later.
"""
from __future__ import annotations

import threading
import time

from . import advisor, itemset, lcu, live
from .log import log

ARAM_MAP = 12


class Pregame:
    def __init__(self, sd, coach):
        self.sd = sd
        self.coach = coach
        self._seen = None          # (champion number, how many polls it has been stable)
        self._planned = None       # (champion number, enemies known) of the last plan started
        self._played = False       # the current match has already been live
        self._phase = None         # client phase on the previous poll
        self._set_for = None       # champion number the item set on disk was written for

    def start(self):
        itemset.clear()            # a set left by an earlier run would show for the wrong champion
        threading.Thread(target=self._loop, name="pregame", daemon=True).start()

    def _loop(self):
        while True:
            time.sleep(2)
            try:
                self._tick()
            except Exception as exc:        # never let a client hiccup stop pregame planning
                self.coach.set_pregame_info({"error": f"Pregame planning failed: {exc!r}"})

    def _tick(self):
        if self.coach.status == "live":
            self._seen = self._planned = None
            self._played = True
            return
        phase, previous_phase = lcu.phase(), self._phase
        self._phase = phase
        if phase != previous_phase:
            log("client_phase", phase=phase)
        if phase == "ChampSelect":
            self._played = False
            if previous_phase != "ChampSelect":
                self._drop_item_set()        # new champion select: the last game's set no longer applies
            picks = lcu.champ_select()
            if picks:
                self._consider(picks[0], picks[1], [], enemies_known=False)
        elif phase in ("GameStart", "InProgress"):
            # The client stays "InProgress" for a moment after a match ends. Plan only on the way in.
            teams = None if self._played else lcu.match_teams()
            if teams and teams[2]:
                self._consider(teams[0], teams[1], teams[2], enemies_known=True)
        else:
            self._seen = self._planned = None
            self._played = False
            if phase is not None:            # back in the client with no match: remove the finished game's set
                self._drop_item_set()

    def _drop_item_set(self):
        itemset.clear()
        self._set_for = None
        self.coach.set_item_set(None, None, None)

    def _consider(self, mine: int, allies: list, enemies: list, enemies_known: bool):
        if self._set_for is not None and self._set_for != mine:
            self._drop_item_set()            # the champion changed, so the set on disk is for the wrong one
        # In ARAM the champion can change through rerolls and trades. Wait until the same
        # champion has been seen on two polls in a row before paying for a plan.
        stable = self._seen[1] + 1 if self._seen and self._seen[0] == mine else 1
        self._seen = (mine, stable)
        if stable < 2 or self._planned == (mine, enemies_known):
            return
        queue = lcu.queue_info() or {}
        if queue.get("mapId") not in (None, ARAM_MAP):
            return                           # the item catalog only covers the ARAM shop
        self._planned = (mine, enemies_known)
        log("pregame_start", champion=self.sd.champ_by_key.get(mine, mine), allies=len(allies),
            enemies=len(enemies), queue=queue.get("description"))
        threading.Thread(target=self._plan, args=(mine, allies, enemies, enemies_known, queue),
                         name="pregame-plan", daemon=True).start()

    def _plan(self, mine: int, allies: list, enemies: list, enemies_known: bool, queue: dict):
        sd = self.sd
        champ_id = sd.champ_by_key.get(mine)
        if champ_id is None:
            return
        name = sd.champions[champ_id]["name"]
        ids = lambda keys: [sd.champ_by_key[k] for k in keys if k in sd.champ_by_key]
        state = live.pregame_state(sd, champ_id, ids(allies), ids(enemies),
                                   queue.get("description") or live.MODE_LABELS.get(queue.get("mode"), "ARAM"))
        state["focus"] = (self.coach.debrief or {}).get("focus_next_game")
        self.coach.set_pregame_info({"champion": name, "champ_id": champ_id, "status": "planning"})
        try:
            if enemies_known:
                previous = self.coach.pregame_summary(champ_id)
                self.coach.loading_plan_started()    # the match can load before this returns; the coach waits for it
                advice, meta = advisor.get_advice(sd, state, previous, "loading screen: the enemy team is now known")
            else:
                advice, meta = advisor.get_pregame(sd, state)
        except Exception as exc:
            self._planned = None             # allow another attempt on the next poll
            if enemies_known:
                self.coach.loading_plan_failed()
            log("pregame_error", champion=champ_id, error=str(exc))
            self.coach.set_pregame_info({"champion": name, "champ_id": champ_id, "error": str(exc)})
            return
        if not enemies_known and (self._seen is None or self._seen[0] != mine):
            return                           # the champion changed while Claude was answering
        written = None
        if not enemies_known:
            written, item_set = itemset.write(sd, champ_id, advice)
            self._set_for = mine if written else None
            self.coach.set_item_set(champ_id, advice, item_set)
            log("item_set", champion=champ_id, title=advice.get("title"), path=str(written) if written else None)
        self.coach.set_pregame(champ_id, advice, enemies_known, meta.get("cost") or 0.0)
        info = {"champion": name, "champ_id": champ_id, "status": "ready", "headline": advice["headline"],
                "build": [b["name"] for b in advice["build_order"]], "enemies_known": enemies_known}
        if written:
            info["item_set"] = f"Coach: {advice.get('title') or champ_id}"
        elif not enemies_known:
            info["error"] = "Could not find League's folder, so no item set was written."
        self.coach.set_pregame_info(info, merge=True)
