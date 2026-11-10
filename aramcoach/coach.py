"""Core loop: polls the game, decides when to ask Claude for a plan, and builds the panel's view."""
from __future__ import annotations

import json
import threading
import time

from . import advisor, config, itemset, lcu, live, ocr, postgame, screen, shop
from .log import log


def _big_items(enemies: list) -> set:
    """Enemy purchases worth reacting to, as (champion, item name) pairs."""
    return {(p["champion"], i["name"]) for p in enemies for i in p["items"] if i["gold"] >= config.BIG_ITEM_GOLD}


def _fingerprint(state: dict) -> tuple:
    """Changes when the game has moved on: kills, levels, or items. Gold and time are excluded."""
    everyone = [state["me"]] + state["allies"] + state["enemies"]
    return tuple((p["level"], tuple(p["kda"]), tuple(sorted(str(i["id"]) for i in p["items"]))) for p in everyone if p)


class Coach:
    def __init__(self, sd, source):
        self.sd = sd
        self.source = source
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.status = "waiting"          # waiting | loading | live
        self.poll_error = None
        self.pregame = None              # plan made before the match: {champ_id, advice, enemies_known}
        self.pregame_info = None         # what the panel shows while waiting
        self.pre_cost, self.pre_calls = 0.0, 0
        self._loading_plan_at = 0.0      # when a loading-screen plan was requested and is not back yet
        self.item_set = None             # the in-game item set written in champion select: {champ_id, extras, ids}
        self.debrief = self._load_last_debrief()   # review of the most recent finished match
        self._reader = None              # reads augment offers off the screen; built on first use
        self._reset_game()

    def _reset_game(self):
        self.game_id = None
        self.lcu_game_id = None          # the client's id for this match, used to find its post-game record
        self.state = None
        self.queue = None
        self.advice = None
        self.advice_meta = {}
        self.error = None
        self.thinking = False
        self.offers = []                 # augment offers seen this game: {names, pick, taken, assumed}
        self._offer = None               # the offer on screen right now (an entry of self.offers)
        self._offer_misses = 0
        self.seen_augments = {}          # other players' augments read from scoreboard tooltips: {champion: [names]}
        self._hover_news = []            # newly read augments not yet passed to a plan update
        self._last_capture_seen = None   # the most recent tooltip read: {name, owner, at}
        self.my_augments = []            # augments taken this game, confirmed or assumed
        self.assumed_augments = []       # the subset assumed because the coach's pick was not corrected
        self.screen = None               # result of the last screen read
        self.screen_busy = False
        self._have_live_plan = False     # a plan made with the enemy team known
        self._awaiting_loading = 0.0     # set at match start while the loading-screen plan is still in flight
        self._pending = None             # (trigger, urgent)
        self._last_request = 0.0
        self._retry_after = 0.0
        self._basis_big = set()
        self._basis_print = None
        self._last_capture = 0.0
        self._last_scoreboard = 0.0
        self.game_cost = 0.0            # US dollars spent on Claude calls this game (api backend only)
        self.game_calls = 0

    @staticmethod
    def _load_last_debrief():
        try:
            newest = max(config.CAPTURE_DIR.glob("*/debrief.json"), key=lambda f: f.stat().st_mtime)
            return json.loads(newest.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return None

    def set_debrief(self, review: dict, cost: float):
        with self.lock:
            self.debrief = review
            self.pre_cost += cost
            self.pre_calls += 1

    def start(self, watch_screen: bool = False):
        threading.Thread(target=self._poll_loop, name="poll", daemon=True).start()
        threading.Thread(target=self._advise_loop, name="advise", daemon=True).start()
        if watch_screen:
            threading.Thread(target=self._offer_loop, name="offers", daemon=True).start()
            threading.Thread(target=self._scoreboard_loop, name="scoreboard", daemon=True).start()

    # ---- before the match ------------------------------------------------

    def set_item_set(self, champ_id, extras, item_set):
        """Remember what was written into the in-game shop, or forget it when the file is removed."""
        with self.lock:
            self.item_set = None if item_set is None else {
                "champ_id": champ_id, "extras": extras, "ids": itemset.item_ids(item_set), "rewritten": None}

    def _item_set_for(self, state):
        """The item set, if it was written for the champion being played. Call with the lock held."""
        me = state["me"] if state else None
        return self.item_set if self.item_set and me and me["champ_id"] == self.item_set["champ_id"] else None

    def _rewrite_item_set(self, state, advice):
        """Rewrite the item set file to match a new live plan, stamped with the game time.

        The game may only read the file when the match loads, in which case this changes
        nothing on screen. The stamp in the title makes it easy to see which is true.
        """
        with self.lock:
            current = self._item_set_for(state)
            build = [b["item_id"] for b in advice["build_order"]]
            if current is None or not self.source.capture or current["rewritten"] == build:
                return
            current["rewritten"] = build
            champ_id, extras = current["champ_id"], current["extras"]
        stamp = f"{int(state['time']) // 60}:{int(state['time']) % 60:02d}"
        try:
            path, _ = itemset.write(self.sd, champ_id, advice, extras, stamp=f"updated {stamp}")
            log("item_set_rewritten", game_time=int(state["time"]), build=[b["name"] for b in advice["build_order"]],
                written=path is not None)
        except Exception as exc:
            log("item_set_rewrite_failed", error=repr(exc))

    def loading_plan_started(self):
        """The loading-screen plan has been requested. The match may load before it is back."""
        with self.lock:
            self._loading_plan_at = time.time()

    def loading_plan_failed(self):
        with self.lock:
            self._loading_plan_at = self._awaiting_loading = 0.0

    def set_pregame(self, champ_id: str, advice: dict, enemies_known: bool, cost: float):
        """Take a plan made before the match. Returns how it was used: "stored", "live" or "late"."""
        with self.lock:
            if enemies_known:
                self._loading_plan_at = 0.0
            me = self.state["me"] if self.state else None
            if self.status != "live":
                self.pregame = {"champ_id": champ_id, "advice": advice, "enemies_known": enemies_known,
                                "at": time.time()}
                self.pre_cost += cost
                self.pre_calls += 1
                used = "stored"
            elif (enemies_known and self._awaiting_loading and not self._have_live_plan
                  and me and me["champ_id"] == champ_id):
                # A real loading screen lasted 13 seconds and the plan takes longer than that. The
                # match loaded first and waited, so the plan goes straight onto the panel now.
                self.advice = advice
                self.advice_meta = {"trigger": "made on the loading screen", "game_time": 0, "at": time.time()}
                self._have_live_plan = True
                self._awaiting_loading = 0.0
                self._last_request = time.time()
                self._basis_big = _big_items(self.state["enemies"])
                self._basis_print = _fingerprint(self.state)
                self.error = None
                self.game_cost += cost
                self.game_calls += 1
                used = "live"
            else:
                self.game_cost += cost
                self.game_calls += 1
                used = "late"
            log("pregame_plan", champion=champ_id, enemies_known=enemies_known, cost=cost, used=used,
                build=[b["name"] for b in advice["build_order"]])
            return used

    def pregame_summary(self, champ_id: str) -> str:
        with self.lock:
            if self.pregame and self.pregame["champ_id"] == champ_id:
                return advisor.plan_summary(self.pregame["advice"], 0)
            return ""

    def set_pregame_info(self, info: dict, merge: bool = False):
        with self.lock:
            self.pregame_info = {**(self.pregame_info or {}), **info} if merge else info

    # ---- polling ---------------------------------------------------------

    def _poll_loop(self):
        while True:
            started = time.time()
            try:
                raw, status = self.source.fetch()
                self._on_snapshot(raw, status)
                self.poll_error = None
            except Exception as exc:          # keep polling; the panel shows the problem
                self.poll_error = f"Reading the game failed: {exc!r}"
            time.sleep(max(0.1, config.POLL_SECONDS - (time.time() - started)))

    def _on_snapshot(self, raw, status):
        with self.lock:
            if raw is None:
                if self.status == "live":
                    self._game_over()
                    self._reset_game()
                    self.pregame_info = None
                self.status = status
                return
            state = live.summarize(raw, self.sd)
            prev = self.state
            new_game = self.status != "live" or prev is None or state["time"] + 30 < prev["time"]
            if new_game:
                self._reset_game()
                self.game_id = time.strftime("%Y%m%d-%H%M%S")
                prev = None
                self._adopt_pregame(state)
                if self.source.capture:
                    threading.Thread(target=self._load_queue, args=(self.game_id,), daemon=True).start()
            state["queue"] = self.queue
            self._merge_seen_augments(state)
            state["my_augments"] = list(self.my_augments)
            state["assumed_augments"] = list(self.assumed_augments)
            state["focus"] = (self.debrief or {}).get("focus_next_game")
            in_set = self._item_set_for(state)
            state["item_set"] = [self.sd.items[i]["name"] for i in in_set["ids"] if i in self.sd.items] if in_set else None
            self.status, self.state = "live", state
            died = bool(prev and prev["me"] and state["me"] and state["me"]["dead"] and not prev["me"]["dead"])
            self._capture(raw, state, force=new_game or died)
            self._check_triggers(state, died)

    def _game_over(self):
        """The match has ended: log it and start the post-game review in the background."""
        log("game_over", game=self.game_id, client_game_id=self.lcu_game_id, calls=self.game_calls,
            cost=round(self.game_cost, 3), game_time=int(self.state["time"]) if self.state else None)
        if self.source.capture and self.lcu_game_id:
            folder = config.CAPTURE_DIR / self.game_id
            threading.Thread(target=postgame.run, name="postgame", daemon=True,
                             args=(self, self.sd, folder, self.lcu_game_id, self._plan_summary())).start()

    def _adopt_pregame(self, state):
        """Start the match with the plan made in champion select or on the loading screen."""
        self.game_cost, self.game_calls = self.pre_cost, self.pre_calls
        self.pre_cost, self.pre_calls = 0.0, 0
        pregame, self.pregame = self.pregame, None
        me = state["me"]
        fresh = pregame and time.time() - pregame["at"] < 900
        adopted = bool(fresh and me and pregame["champ_id"] == me["champ_id"])
        log("game_start", game=self.game_id, champion=me and me["champion"], mode=state["mode"],
            allies=len(state["allies"]), enemies=len(state["enemies"]), game_time=int(state["time"]),
            pregame_plan=("full" if pregame["enemies_known"] else "champion select") if adopted else None)
        if time.time() - self._loading_plan_at < 45:
            self._awaiting_loading = time.time()     # the loading-screen plan is still being written: wait for it
        if not adopted:
            return
        self.advice = pregame["advice"]
        self.advice_meta = {"trigger": "made before the match loaded", "game_time": 0, "at": time.time()}
        if pregame["enemies_known"]:
            # The loading-screen plan already saw both teams, so no second plan is needed at spawn.
            self._have_live_plan = True
            self._last_request = time.time()
            self._basis_big = _big_items(state["enemies"])
            self._basis_print = _fingerprint(state)

    def _load_queue(self, game_id):
        info, client_game_id = lcu.queue_info(), lcu.current_game_id()
        with self.lock:
            if game_id != self.game_id:
                return
            self.lcu_game_id = client_game_id
            if info:
                self.queue = info
                if self.state:
                    self.state["queue"] = info

    def _capture(self, raw, state, force):
        """Save raw payloads so the API's real contents can be inspected later."""
        if not self.source.capture:
            return
        now = time.time()
        if not force and now - self._last_capture < config.CAPTURE_EVERY:
            return
        self._last_capture = now
        folder = config.CAPTURE_DIR / self.game_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"t{int(state['time']):05d}.json").write_text(json.dumps(raw), encoding="utf-8")
        if state["augment_fields"]:
            (folder / "augment_fields.json").write_text(
                json.dumps(state["augment_fields"], indent=2, ensure_ascii=False), encoding="utf-8")

    # ---- deciding when to ask --------------------------------------------

    def _check_triggers(self, state, died):
        if state["me"] is None or state["ended"] or time.time() < self._retry_after:
            return
        if not self._have_live_plan:
            waiting = self._awaiting_loading and time.time() - self._awaiting_loading < 30
            if not waiting and not self.thinking and self._pending is None:
                self.request("game start", urgent=True)
            return
        new = _big_items(state["enemies"]) - self._basis_big
        bought = ", ".join(f"{c} bought {i}" for c, i in sorted(new))
        if died:
            # The buy list is worked out locally and is always current. A death needs a new plan
            # only when the plan is old or an enemy has finished an item since it was made.
            old = time.time() - self.advice_meta.get("at", 0) > config.DEATH_REFRESH_AFTER
            if new or old:
                self.request("the player just died and the shop is open" + (f"; {bought}" if new else ""), urgent=True)
            return
        if not state["me"]["dead"] and not config.UPDATE_WHILE_ALIVE:
            # A living player cannot shop and is not reading the panel. What changed meanwhile is
            # picked up by the plan made at the next death.
            return
        if new:
            self.request("enemy purchases: " + bought)
        elif (time.time() - self._last_request > config.PERIODIC_REFRESH
              and _fingerprint(state) != self._basis_print):
            self.request("periodic refresh")

    def request(self, trigger: str, urgent: bool = False):
        """Queue a plan update. Urgent requests skip the minimum interval."""
        with self.lock:
            if self._pending and self._pending[1] and not urgent:
                return                       # an urgent request is already waiting; keep its reason
            if urgent:
                self._retry_after = 0.0
            self._pending = (trigger, urgent)
        self.wake.set()

    def _advise_loop(self):
        while True:
            self.wake.wait(timeout=1.0)
            self.wake.clear()
            with self.lock:
                state = self.state
                if not self._pending or state is None or state["me"] is None:
                    continue
                trigger, urgent = self._pending
                now = time.time()
                if not urgent and now - self._last_request < config.MIN_ADVICE_INTERVAL:
                    continue                 # checked again on the next one-second wake-up
                self._pending = None
                self.thinking = True
                self._last_request = now
                self._basis_big = _big_items(state["enemies"])
                self._basis_print = _fingerprint(state)
                game_id = self.game_id
                previous = self._plan_summary()
                first_plan = self.advice is None
            base_meta = {"trigger": trigger, "game_time": state["time"]}

            def show_partial(partial, game_id=game_id, base_meta=base_meta):
                # First plan of a game only: show the build order as soon as it has streamed in.
                with self.lock:
                    if game_id == self.game_id and self.advice is None:
                        self.advice = partial
                        self.advice_meta = {**base_meta, "at": time.time(), "partial": True}

            try:
                advice, meta = advisor.get_advice(self.sd, state, previous, trigger,
                                                  on_partial=show_partial if first_plan else None)
                failure = None
            except Exception as exc:
                advice, meta, failure = None, {}, str(exc)
            with self.lock:
                if game_id != self.game_id:
                    continue                 # the game ended while Claude was answering
                self.thinking = False
                log("plan", game=game_id, trigger=trigger, game_time=int(state["time"]), ok=bool(advice),
                    latency=meta.get("latency"), cost=meta.get("cost"), output_tokens=meta.get("output_tokens"),
                    cache_read=meta.get("cached_tokens"), error=failure,
                    build=[b["name"] for b in advice["build_order"]] if advice else None)
                if advice:
                    self.advice = advice
                    self.advice_meta = {**meta, **base_meta, "at": time.time()}
                    self.error = None
                    self._have_live_plan = True
                    self._spent(meta)
                    threading.Thread(target=self._rewrite_item_set, args=(state, advice), daemon=True).start()
                else:
                    if self.advice_meta.get("partial"):
                        self.advice, self.advice_meta = None, {}   # drop a half-arrived plan
                    self.error = failure
                    self._retry_after = time.time() + config.RETRY_AFTER_ERROR

    def _plan_summary(self) -> str:
        if not self.advice:
            return ""
        return advisor.plan_summary(self.advice, self.advice_meta.get("game_time", 0))

    def _spent(self, meta: dict):
        self.game_cost += meta.get("cost") or 0.0
        self.game_calls += 1

    # ---- questions, screen reads, augments --------------------------------

    def ask(self, question: str) -> str:
        with self.lock:
            state, previous = self.state, self._plan_summary()
        if state is None or state["me"] is None:
            return "No game is running, so there is nothing to answer about yet."
        text, meta = advisor.answer_question(self.sd, state, previous, question)
        log("question", question=question, latency=meta.get("latency"), cost=meta.get("cost"), answer=text)
        with self.lock:
            self._spent(meta)
        return text

    def read_screen(self):
        """Take a screenshot and ask Claude what to pick. Runs in the background; the panel shows the result."""
        with self.lock:
            ready = not self.screen_busy and self.state is not None and self.state["me"] is not None
            log("screen_requested", accepted=ready, status=self.status)
            if not ready:
                return
            self.screen_busy = True
            state, previous, game_id = self.state, self._plan_summary(), self.game_id
        threading.Thread(target=self._read_screen, args=(state, previous, game_id), name="screen", daemon=True).start()

    def _read_screen(self, state, previous, game_id):
        started = time.time()
        try:
            shot = screen.grab()
            if self.source.capture:
                # Keep the full-resolution image: it is the reference for building icon recognition.
                folder = config.CAPTURE_DIR / game_id
                folder.mkdir(parents=True, exist_ok=True)
                shot.save(folder / f"screen_t{int(state['time']):05d}.png")
            result, meta = advisor.read_screen(self.sd, state, previous, screen.to_jpeg(shot))
        except Exception as exc:
            result, meta = {"kind": "error", "offered": [], "pick": "", "why": str(exc), "note": ""}, {}
        log("screen_read", game=game_id, game_time=int(state["time"]), kind=result["kind"], pick=result["pick"],
            offered=[o["name"] for o in result["offered"]], why=result["why"], latency=meta.get("latency"),
            cost=meta.get("cost"))
        with self.lock:
            if game_id != self.game_id:
                return
            self.screen_busy = False
            if result["kind"] == "augment_choice":
                self.offers.append({"names": [o["name"] for o in result["offered"]], "pick": result["pick"],
                                    "taken": None, "assumed": False})
            self.screen = {**result, "at": time.time(), "game_time": int(state["time"]),
                           "took": round(time.time() - started, 1)}
            if meta:
                self._spent(meta)

    def capture_scoreboard(self):
        """Save a full-resolution screenshot while the scoreboard (Tab) is up. No Claude call.

        These images are the reference for reading every player's augments off the scoreboard.
        """
        with self.lock:
            now = time.time()
            if (self.status != "live" or self.state is None or not self.source.capture
                    or now - self._last_scoreboard < 15):
                return
            self._last_scoreboard = now
            folder, game_time = config.CAPTURE_DIR / self.game_id, int(self.state["time"])
        try:
            folder.mkdir(parents=True, exist_ok=True)
            screen.grab().save(folder / f"scoreboard_t{game_time:05d}.png")
            log("scoreboard_saved", game_time=game_time)
        except Exception as exc:             # a failed reference capture must never disturb the coach
            log("scoreboard_failed", error=repr(exc))

    # ---- augment offers read off the screen --------------------------------

    def _offer_loop(self):
        while True:
            try:
                self.scan_for_offer()
            except Exception as exc:
                log("offer_scan_error", error=repr(exc))
                time.sleep(5)
            time.sleep(0.7)

    def scan_for_offer(self):
        """Look at the screen once for an augment offer and react to what is there.

        Runs every 0.7 seconds during an ARAM: Mayhem match. Reading the three card titles
        takes about 50 ms locally, so no hotkey and no model call are needed to notice an offer.
        """
        with self.lock:
            state = self.state
            if (self.status != "live" or state is None or state["me"] is None
                    or state["mode"] != "KIWI" or state["ended"]):
                return
        if not screen.league_in_front():
            return
        if self._reader is None:
            self._reader = ocr.OfferReader(self.sd.augments_described())
        offer = self._reader.find(screen.grab())
        names = [a["name"] for a in offer]
        with self.lock:
            if self.state is None:
                return
            if not names:
                self._offer_closed_maybe()
                return
            self._offer_misses = 0
            if self._offer is None:
                self._offer = {"names": [], "pick": "", "taken": None, "assumed": False}
                self.offers.append(self._offer)
            if names == self._offer["names"]:
                return
            episode = self._offer            # a new offer, or a reroll changed the cards
            episode["names"], episode["pick"] = names, ""
            hoped_for = ((self.advice or {}).get("scaling") or {}).get("augments_to_look_for") or []
            wanted = [n for n in names if any(n.lower() in w.lower() for w in hoped_for)]
            self.screen = {
                "kind": "augment_choice", "pick": "", "why": "", "note": "", "reroll": "", "choosing": True,
                "wanted": wanted, "at": time.time(), "game_time": int(self.state["time"]),
                "offered": [{"name": a["name"], "tier": a["tier"], "summary": a["description"][:240]} for a in offer],
            }
            log("offer_seen", game=self.game_id, game_time=int(self.state["time"]), offered=names, wanted=wanted)
            args = (episode, offer, names, self.state, self._plan_summary(), self.game_id)
        threading.Thread(target=self._choose_augment, args=args, name="augment", daemon=True).start()

    def _choose_augment(self, episode, offer, names, state, previous, game_id):
        try:
            result, meta = advisor.choose_augment(self.sd, state, previous, offer)
        except Exception as exc:
            result, meta = {"pick": "", "why": f"No pick: {exc}", "reroll": "", "note": ""}, {}
        log("offer_pick", game=game_id, offered=names, pick=result["pick"], why=result["why"],
            latency=meta.get("latency"), cost=meta.get("cost"))
        with self.lock:
            if game_id != self.game_id:
                return
            if meta:
                self._spent(meta)
            if episode["names"] != names:
                return                       # the cards changed while Claude was answering
            episode["pick"] = result["pick"]
            if self.screen and self.screen.get("kind") == "augment_choice":
                self.screen.update(result, choosing=False, took=meta.get("latency"))

    # ---- other players' augments, read from scoreboard tooltips --------------

    def _scoreboard_loop(self):
        while True:
            try:
                if screen.tab_is_down():
                    self.scan_scoreboard()
                else:
                    self.flush_hover_news()          # scoreboard closed: one plan update for the whole look
            except Exception as exc:
                log("hover_scan_error", error=repr(exc))
                time.sleep(5)
            time.sleep(0.25)

    def scan_scoreboard(self):
        """While the scoreboard is up, read the augment the player is pointing at and note whose it is.

        The game only names another player's augment in the tooltip that opens when the mouse is
        over its icon; the icons themselves are shared between many augments. The tooltip's title
        is read near the cursor. Its owner is worked out from the scoreboard row the cursor is on:
        rows carry no player names, so they are located by their K/D/A text, which is matched to
        the scores the game API reports.
        """
        with self.lock:
            state = self.state
            if (self.status != "live" or state is None or state["me"] is None
                    or state["mode"] != "KIWI" or state["ended"]):
                return
            order = state["scoreboard"]
            game_id, game_time = self.game_id, int(state["time"])
        if not screen.league_in_front():
            return
        if self._reader is None:
            self._reader = ocr.OfferReader(self.sd.augments_described())
        shot, cursor = screen.grab(), screen.cursor_position()
        lines = ocr.read_lines(shot)
        augment = self._reader.tooltip(lines, cursor)
        if augment is None:
            return
        anchors = ocr.score_anchors(shot, lines)
        owner, rows = ocr.scoreboard_owner(anchors, cursor, shot.size, order)
        with self.lock:
            if game_id != self.game_id:
                return
            key = owner or "?"
            if augment["name"] in self.seen_augments.setdefault(key, []):
                return
            self.seen_augments[key].append(augment["name"])
            if owner and augment["name"] in self.seen_augments.get("?", []):
                self.seen_augments["?"].remove(augment["name"])      # now attributed
            saved = sum(len(v) for v in self.seen_augments.values())
            log("augment_hovered", game=game_id, game_time=game_time, augment=augment["name"], owner=owner,
                cursor=list(cursor), rows=rows, anchors=len(anchors))
            self._last_capture_seen = {"name": augment["name"], "owner": owner, "at": time.time()}
            mine = owner == self.state["me"]["champion"]
        if self.source.capture and saved <= 8:
            # Keep the first few pictures so the row matching can be checked against the real layout.
            folder = config.CAPTURE_DIR / game_id
            folder.mkdir(parents=True, exist_ok=True)
            shot.save(folder / f"hover_t{game_time:05d}_{saved}.png")
        if mine:
            self.took_augment(augment["name"])       # pointing at your own augment confirms it
        elif owner:
            with self.lock:
                self._hover_news.append(f"{owner} has {augment['name']}")

    def _augment_tracker(self, state: dict) -> dict:
        """What the coach knows of every player's augments, and how many each could have by now.

        Mayhem offers an augment at levels 3, 7, 11 and 15, so a player's level gives the most
        they can hold. A pick can be pending (it is made while dead), so this is an upper bound.
        Call with the lock held.
        """
        def row(p, side):
            known = [a["name"] for a in p.get("augments") or []]
            if side == "you":
                known = list(dict.fromkeys(self.my_augments + known))
            return {"champion": p["champion"], "champ_id": p["champ_id"], "side": side, "known": known,
                    "assumed": [n for n in known if side == "you" and n in self.assumed_augments],
                    "possible": max(len(known), sum(p["level"] >= level for level in (3, 7, 11, 15)))}

        players = ([row(p, "enemy") for p in state["enemies"]] + [row(p, "ally") for p in state["allies"]]
                   + ([row(state["me"], "you")] if state["me"] else []))
        last = self._last_capture_seen
        return {
            "players": players,
            "known": sum(len(p["known"]) for p in players),
            "possible": sum(p["possible"] for p in players),
            "unowned": list(self.seen_augments.get("?", [])),
            "last": {**last, "age": int(time.time() - last["at"])} if last else None,
        }

    def flush_hover_news(self):
        """Ask for one plan update covering everything read during a look at the scoreboard."""
        with self.lock:
            news, self._hover_news = self._hover_news, []
        if news:
            self.request("the player read augments off the scoreboard: " + "; ".join(news))

    def _merge_seen_augments(self, state: dict):
        """Add augments read from the scoreboard to each player in a snapshot. Call with the lock held."""
        for p in [state["me"]] + state["allies"] + state["enemies"]:
            if p is None:
                continue
            have = {a["name"] for a in p["augments"]}
            for name in self.seen_augments.get(p["champion"], []):
                entry = self.sd.augment(name)
                if entry and name not in have:
                    p["augments"].append(entry)

    def _offer_closed_maybe(self):
        """Called with the lock held when a scan finds no offer. Three misses in a row close it."""
        episode = self._offer
        if episode is None:
            return
        self._offer_misses += 1
        if self._offer_misses < 3:
            return
        self._offer = None
        log("offer_closed", game=self.game_id, offered=episode["names"], pick=episode["pick"], taken=episode["taken"])
        if episode["pick"] and not episode["taken"]:
            # The player cannot be seen choosing. The coach gave a pick and was not corrected, so
            # assume they took it, mark it as assumed, and let a tap on the panel correct it.
            episode["taken"], episode["assumed"] = episode["pick"], True
            self._augments_changed(
                f"the player probably took the augment {episode['pick']} (the coach's pick, not confirmed)")

    def _augments_changed(self, reason: str):
        """Rebuild the taken-augment lists from the offers and refresh the plan. Call with the lock held."""
        taken = [o for o in self.offers if o["taken"]]
        self.my_augments = [o["taken"] for o in taken]
        self.assumed_augments = [o["taken"] for o in taken if o["assumed"]]
        if self.state is not None:
            self.state["my_augments"] = list(self.my_augments)
            self.state["assumed_augments"] = list(self.assumed_augments)
        if self.screen and self.screen.get("kind") == "augment_choice" and self.offers:
            self.screen["taken"] = self.offers[-1]["taken"]
            self.screen["assumed"] = self.offers[-1]["assumed"]
        self.request(reason, urgent=True)

    def took_augment(self, name: str):
        """Record an augment the player says they took. It replaces an assumed one from the same offer."""
        name = name.strip()[:60]
        with self.lock:
            if not name or self.state is None:
                return
            episode = next((o for o in reversed(self.offers) if name in o["names"]), None)
            if episode is None:
                episode = {"names": [name], "pick": "", "taken": None, "assumed": False}
                self.offers.append(episode)
            if episode["taken"] == name and not episode["assumed"]:
                return
            episode["taken"], episode["assumed"] = name, False
            log("augment_taken", game=self.game_id, name=name)
            self._augments_changed(f"the player took the augment {name}")

    # ---- panel view ------------------------------------------------------

    @staticmethod
    def _lite(p: dict) -> dict:
        return {"champion": p["champion"], "champ_id": p["champ_id"], "level": p["level"], "kda": p["kda"],
                "dead": p["dead"], "items": [{"id": i["id"], "name": i["name"]} for i in p["items"]],
                "augments": [a["name"] for a in p.get("augments") or []]}

    def view(self) -> dict:
        """Everything the panel shows, as one JSON-ready dict."""
        with self.lock:
            billed = config.BACKEND == "api"
            view = {"status": self.status, "thinking": self.thinking, "error": self.error or self.poll_error,
                    "version": self.sd.version, "hotkey": config.HOTKEY,
                    "model": config.MODEL + (" fast mode" if billed and config.SPEED == "fast" else ""),
                    "spend": {"billed": billed, "cost": round(self.game_cost, 2), "calls": self.game_calls}}
            state = self.state
            if self.status != "live" or state is None:
                view["pregame"] = self.pregame_info
                view["debrief"] = self.debrief
                return view
            me = state["me"]
            view["game"] = {"mode": (state.get("queue") or {}).get("description") or state["mode_label"],
                            "time": int(state["time"]), "is_aram": state["map"] == 12, "ended": state["ended"]}
            view["teams"] = {"allies": [self._lite(p) for p in state["allies"]],
                             "enemies": [self._lite(p) for p in state["enemies"]]}
            view["augment_fields"] = sorted(state["augment_fields"])
            view["my_augments"] = list(self.my_augments)
            view["assumed_augments"] = list(self.assumed_augments)
            view["unowned_augments"] = list(self.seen_augments.get("?", []))
            if state["mode"] == "KIWI":
                view["augment_tracker"] = self._augment_tracker(state)
            view["screen"] = {"busy": self.screen_busy, **(
                {**self.screen, "age": int(time.time() - self.screen["at"])} if self.screen else {})}
            if me is None:
                view["error"] = view["error"] or "Could not tell which player is you in the game data."
                return view
            view["me"] = {**self._lite(me), "gold": me["gold"], "respawn": me["respawn"]}
            if not self.advice:
                return view

            advice = self.advice
            build_ids = [b["item_id"] for b in advice["build_order"]]
            inventory = [i["id"] for i in me["items"] if i["slot"] < shop.MAX_SLOTS]
            buy = shop.plan(build_ids, inventory, me["gold"], self.sd.items)
            view["buy_now"] = {
                "purchases": buy["purchases"], "spend": buy["spend"], "left": buy["left"], "next": buy["next"],
                "shop_open": me["dead"] or state["time"] < 45,
                "complete": all(s == "done" for s in buy["statuses"]),
            }
            in_set = self._item_set_for(state)
            view["build"] = [{"id": b["item_id"], "name": b["name"], "why": b["why"], "status": s,
                              "in_set": b["item_id"] in in_set["ids"] if in_set else None}
                             for b, s in zip(advice["build_order"], buy["statuses"])]
            view["advice"] = {k: advice.get(k) for k in
                              ("headline", "next_item_why", "how_to_play", "threats", "duels", "scaling",
                               "skill_order", "changed")}
            meta = self.advice_meta
            view["meta"] = {"trigger": meta.get("trigger"), "age": int(time.time() - meta.get("at", time.time())),
                            "latency": meta.get("latency"), "game_time": int(meta.get("game_time", 0)),
                            "partial": bool(meta.get("partial"))}
            return view
