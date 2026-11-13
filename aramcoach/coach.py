"""Core loop: polls the game, decides when to ask Claude for a plan, and builds the panel's view."""
from __future__ import annotations

import json
import threading
import time
from collections import deque

from . import advisor, champfit, config, deaths, itemset, lcu, live, ocr, postgame, research, screen, shop
from .log import log


def _big_items(enemies: list) -> set:
    """Enemy purchases worth reacting to, as (champion, item name) pairs."""
    return {(p["champion"], i["name"]) for p in enemies for i in p["items"] if i["gold"] >= config.BIG_ITEM_GOLD}


def _fingerprint(state: dict) -> tuple:
    """Changes when the game has moved on: kills, levels, or items. Gold and time are excluded."""
    everyone = [state["me"]] + state["allies"] + state["enemies"]
    return tuple((p["level"], tuple(p["kda"]), tuple(sorted(str(i["id"]) for i in p["items"]))) for p in everyone if p)


def _follow_up(name: str) -> bool:
    """Whether a card only ever appears as a second choice: a stat shard or an ability upgrade."""
    return name.strip().endswith("Shard") or name.strip().upper() in ("HEAVY", "POWER", "THRASH", "DOOM")


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
        self.champ_options = None        # champions on offer in champion select, ranked (see champfit.rank)
        self._fit = champfit.load(sd) or {}   # each champion's job on a team, used to name a teammate to follow
        self.pre_cost, self.pre_calls = 0.0, 0
        self._loading_plan_at = 0.0      # when a loading-screen plan was requested and is not back yet
        self.item_set = None             # the in-game item set written in champion select: {champ_id, ids}
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
        self.offers = []                 # augment offers seen this game: {names, pick, why, taken, assumed, time}
        self.plans = []                  # every plan given this game: {time, trigger, build, changed, dropped}
        self._offer = None               # the offer on screen right now (an entry of self.offers)
        self._offer_misses = 0
        self._offer_candidate = None    # the cards read on the last scan, waiting for a second scan to agree
        self._offer_partial = 0          # scans in a row that read fewer than three cards
        self._death_at = 0.0             # when the player died, while the plan for that death is being held
        self._death_trigger = ""
        self.deaths = []                 # the player's deaths this game, as measured by deaths.record
        self._health = deque(maxlen=40)  # (game time, share of health left) for the last seconds alive
        self._death_shot_at = 0.0        # when to save a picture of the screen after a death; 0 when none is due
        self._hover_misses = 0
        self._start_misses = 0
        self.seen_augments = {}          # other players' augments read from scoreboard tooltips: {champion: [names]}
        self._hover_news = []            # newly read augments not yet passed to a plan update
        self._last_capture_seen = None   # the most recent tooltip read: {name, owner, at}
        self.my_augments = []            # augments taken this game, confirmed or assumed
        self.assumed_augments = []       # the subset assumed because the coach's pick was not corrected
        self.screen = None               # result of the last screen read
        self.screen_busy = False
        self._have_live_plan = False     # a plan made with the enemy team known
        self._awaiting_loading = 0.0     # set at match start while the loading-screen plan is still in flight
        self._pending = None             # (trigger, urgent, fresh)
        self._remake_owed = False        # an augment that matters was recorded while another choice was on screen
        self._taken_out = {}             # items plans of this match took out of the build: {item id: {name, time, why}}
        self.told = []                   # what the player typed to the coach this match: {time, text}
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

    def set_item_set(self, champ_id, item_set):
        """Remember what was written into the in-game shop, or forget it when the file is removed."""
        with self.lock:
            self.item_set = None if item_set is None else {"champ_id": champ_id, "ids": itemset.item_ids(item_set)}

    def _item_set_for(self, state):
        """The item set, if it was written for the champion being played. Call with the lock held."""
        me = state["me"] if state else None
        return self.item_set if self.item_set and me and me["champ_id"] == self.item_set["champ_id"] else None

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
                self._note_plan(advice, 0, "made on the loading screen")
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
                build=[b["name"] for b in advice["build_order"]], whys=[b["why"] for b in advice["build_order"]],
                dropped=[d["name"] for d in advice.get("dropped") or []])
            return used

    def pregame_summary(self, champ_id: str) -> str:
        with self.lock:
            if self.pregame and self.pregame["champ_id"] == champ_id:
                return advisor.plan_summary(self.pregame["advice"], 0)
            return ""

    def set_champ_options(self, ranked):
        """The ranked champions on offer in champion select, or None when champion select is over."""
        with self.lock:
            self.champ_options = ranked

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
            if state["me"] is None and self.status != "live" and self._start_misses < 20:
                self._start_misses += 1      # the first second of a match can lack the player's name
                self.status = "loading"
                return
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
            state["told"] = list(self.told)
            state["focus"] = (self.debrief or {}).get("focus_next_game")
            in_set = self._item_set_for(state)
            state["item_set"] = [self.sd.items[i]["name"] for i in in_set["ids"] if i in self.sd.items] if in_set else None
            self.status, self.state = "live", state
            me, was = state["me"], prev and prev["me"]
            died = bool(was and me and me["dead"] and not was["dead"])
            if me and not me["dead"] and me.get("health") is not None:
                self._health.append((state["time"], me["health"]))
            if died:
                # Health about ten seconds earlier says whether the player went into the fight already low.
                earlier = [(abs(t - (state["time"] - 10)), h) for t, h in self._health
                           if state["time"] - 14 <= t <= state["time"] - 6]
                self.deaths.append(deaths.record(state, min(earlier)[1] if earlier else None,
                                                 after=self.deaths[-1]["time"] if self.deaths else -1.0))
                if len(self.deaths) <= 8:
                    self._death_shot_at = time.time() + 3.0
            state["deaths"] = self._death_summary(state)
            self._capture(raw, state, force=new_game or died)
            self._check_triggers(state, died)

    def _death_summary(self, state):
        """Breakdown of the player's deaths so far, or None. Call with the lock held."""
        me = state["me"]
        if me is None or not self.deaths:
            return None
        rows = [deaths.classify(d, state["kills"], (me["team"], me["champion"]), state["time"]) for d in self.deaths]
        job = lambda p: (self._fit.get(p["champ_id"]) or champfit.fallback(self.sd, p["champ_id"]))["job"]
        lead = next((p["champion"] for p in state["allies"] if job(p) == "frontline"), "")
        return deaths.summarize(rows, tank=job(me) == "frontline", lead=lead)

    def _game_over(self):
        """The match has ended: log it and start the post-game review in the background."""
        died = (self.state or {}).get("deaths")
        log("game_over", game=self.game_id, client_game_id=self.lcu_game_id, calls=self.game_calls,
            cost=round(self.game_cost, 3), game_time=int(self.state["time"]) if self.state else None,
            deaths=died and died["line"])
        if self.source.capture and self.lcu_game_id:
            folder = config.CAPTURE_DIR / self.game_id
            threading.Thread(target=postgame.run, name="postgame", daemon=True,
                             args=(self, self.sd, folder, self.lcu_game_id, self._plan_summary(), died,
                                   self._match_record())).start()

    def _adopt_pregame(self, state):
        """Start the match with the plan made in champion select or on the loading screen."""
        self.game_cost, self.game_calls = self.pre_cost, self.pre_calls
        self.pre_cost, self.pre_calls = 0.0, 0
        pregame, self.pregame = self.pregame, None
        me = state["me"]
        if me and me["champ_id"]:
            research.ensure(self.sd, me["champ_id"])     # this champion's playbook, if the loading screen did not start it
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
        self._note_plan(self.advice, 0, "made before the match loaded, "
                        + ("with the enemy team known" if pregame["enemies_known"] else "in champion select"))
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
                self.request("game start", urgent=True, fresh=True)
            return
        new = _big_items(state["enemies"]) - self._basis_big
        bought = ", ".join(f"{c} bought {i}" for c, i in sorted(new))
        if died:
            # The buy list is worked out locally and is always current. A death needs a new plan
            # only when the plan is old or an enemy has finished an item since it was made.
            old = time.time() - self.advice_meta.get("at", 0) > config.DEATH_REFRESH_AFTER
            if new or old:
                self._death_at = time.time()
                self._death_trigger = "the player just died and the shop is open" + (f"; {bought}" if new else "")
        if self._death_at:
            # In Mayhem an augment offer often opens at the moment of death, and taking it asks for
            # a plan too. Eight real games made 29 such doubled plans. Wait a moment: if an offer is
            # on screen, the plan made when it closes covers this death as well.
            held = time.time() - self._death_at
            offer_open = self._offer is not None or self._offer_candidate is not None
            wait = config.DEATH_PLAN_WAIT if state["mode"] == "KIWI" else 0.0
            if held >= wait and (not offer_open or held >= 45):
                self._death_at = 0.0
                self.request(self._death_trigger, urgent=True)
            return
        if died:
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

    def request(self, trigger: str, urgent: bool = False, fresh: bool = False):
        """Queue a plan update. Urgent requests skip the minimum interval.

        fresh: remake the plan from what is known now instead of adjusting the last one. Used at
          the start of a match and when the player's augments change, the two moments at which
          what the build should be can change most. Several independent plans are made and
          combined (see advisor.get_plan).
        """
        with self.lock:
            if self._pending and self._pending[1] and not urgent:
                return                       # an urgent request is already waiting; keep its reason
            if urgent:
                self._retry_after = 0.0
            self._pending = (trigger, urgent, fresh or bool(self._pending and self._pending[2]))
        self.wake.set()

    def _advise_loop(self):
        while True:
            self.wake.wait(timeout=1.0)
            self.wake.clear()
            with self.lock:
                state = self.state
                if not self._pending or state is None or state["me"] is None:
                    continue
                trigger, urgent, fresh = self._pending
                now = time.time()
                if not urgent and now - self._last_request < config.MIN_ADVICE_INTERVAL:
                    continue                 # checked again on the next one-second wake-up
                self._pending = None
                self.thinking = True
                self._last_request = now
                self._basis_big = _big_items(state["enemies"])
                self._basis_print = _fingerprint(state)
                game_id = self.game_id
                votes = config.PLAN_VOTES if fresh else 1
                previous = self._plan_summary(for_plan=True)
                in_force = self.advice if not self.advice_meta.get("partial") else None
                replaced = in_force if votes > 1 else None
                first_plan = self.advice is None
            base_meta = {"trigger": trigger, "game_time": state["time"]}

            def show_partial(partial, game_id=game_id, base_meta=base_meta):
                # First plan of a game only: show the build order as soon as it has streamed in.
                with self.lock:
                    if game_id == self.game_id and self.advice is None:
                        self.advice = partial
                        self.advice_meta = {**base_meta, "at": time.time(), "partial": True}

            try:
                advice, meta = advisor.get_plan(
                    self.sd, state, previous, trigger, votes, on_partial=show_partial if first_plan else None,
                    previous_build=[b["item_id"] for b in replaced["build_order"]] if replaced else ())
                # The player may have shopped while Claude was answering: go by what they hold now.
                latest = self.state if self.state is not None and self.state.get("me") else state
                held = [i["id"] for i in latest["me"]["items"]]
                # A remake from several plans, the first plan with the enemy team known, and a plan the player asked
                # for may change the build freely. Any other must say what it changed.
                free = (votes > 1 or trigger.startswith("game start") or "asked for a fresh plan" in trigger
                        or trigger.startswith("the player typed"))
                advice = advisor.steady(self.sd, in_force, advice, held, fresh=free)
                if votes > 1:                # made without sight of the last plan, so the coach says what changed
                    advice["changed"] = advisor.build_change(replaced, advice, set(held))
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
                    build=[b["name"] for b in advice["build_order"]] if advice else None,
                    # The reason given for each item, and any item the item checks removed (see itemcheck).
                    whys=[b["why"] for b in advice["build_order"]] if advice else None,
                    dropped=[d["name"] for d in advice.get("dropped") or []] if advice else None,
                    # What the plan said it changed, and what the coach held it to (see advisor.steady).
                    changed=advice.get("changed") if advice else None, kept=advice.get("kept") if advice else None,
                    # The build the plan asked for and its reason, when the coach showed a different one.
                    proposed=advice.get("proposed") if advice else None,
                    proposed_change=advice.get("proposed_change") if advice else None,
                    # With several independent plans: how many, how many items most of them agreed on, and each build.
                    votes=meta.get("votes"), agreed=meta.get("agreed"), builds=meta.get("builds"),
                    # With calculations on offer: the seconds each answer took, and what was called (see tools.py).
                    turns=meta.get("turns"), tool_calls=meta.get("tool_calls"))
                if advice:
                    if in_force:
                        # Remember what this plan took out and why, for the plans after it (see advisor.plan_summary).
                        now_in = {b["item_id"] for b in advice["build_order"]}
                        for b in in_force["build_order"]:
                            if b["item_id"] not in now_in and b["item_id"] not in held:
                                self._taken_out[b["item_id"]] = {"name": b["name"], "time": int(state["time"]),
                                                                 "why": (advice.get("changed") or "")[:200]}
                        for item_id in now_in & set(self._taken_out):
                            del self._taken_out[item_id]
                    self.advice = advice
                    self.advice_meta = {**meta, **base_meta, "at": time.time()}
                    self._note_plan(advice, state["time"], trigger)
                    self.error = None
                    self._have_live_plan = True
                    self._spent(meta)
                else:
                    if self.advice_meta.get("partial"):
                        self.advice, self.advice_meta = None, {}   # drop a half-arrived plan
                    self.error = failure
                    self._retry_after = time.time() + config.RETRY_AFTER_ERROR

    def _plan_summary(self, for_plan: bool = False) -> str:
        """The plan in force as text for the next request. A plan request also gets what earlier plans took out."""
        if not self.advice:
            return ""
        return advisor.plan_summary(self.advice, self.advice_meta.get("game_time", 0),
                                    list(self._taken_out.values()) if for_plan else ())

    def _note_plan(self, advice: dict, game_time: float, trigger: str):
        """Keep a plan for the post-game review, which checks the coach's advice against the result."""
        self.plans.append({"time": int(game_time), "trigger": trigger, "changed": advice.get("changed") or "",
                           "build": [b["name"] for b in advice["build_order"]],
                           "dropped": [d["name"] for d in advice.get("dropped") or []],
                           "proposed": advice.get("proposed"), "proposed_change": advice.get("proposed_change") or ""})

    def _match_record(self) -> dict:
        """What the coach did during this match, for the post-game review. Call with the lock held."""
        state = self.state
        me = state["me"] if state else None
        rows = [deaths.classify(d, state["kills"], (me["team"], me["champion"]), state["time"])
                for d in self.deaths] if me else []
        return {
            # Who the player was, in case the client cannot say which account is theirs after the match.
            "me": {"champ_id": me["champ_id"], "team": me["team"]} if me else None,
            "plans": list(self.plans),
            "offers": [{"time": o.get("time"), "names": list(o["names"]), "pick": o["pick"], "why": o.get("why", ""),
                        "taken": o["taken"], "assumed": o["assumed"]} for o in self.offers],
            "death_rows": [{**{k: d[k] for k in ("time", "killer", "by", "health", "ours", "theirs",
                                                 "started_with", "started_against")},
                            "verdict": deaths.words(d["kind"])} for d in rows],
            "focus": (self.debrief or {}).get("focus_next_game") or "",
            "told": list(self.told),
        }

    def _spent(self, meta: dict):
        self.game_cost += meta.get("cost") or 0.0
        self.game_calls += 1

    # ---- questions, screen reads, augments --------------------------------

    def ask(self, question: str) -> str:
        """Answer something the player typed, keep it for the rest of the match, and make the plan again with it.

        Most of what the player types mid-match is about the build: an item they already own, an
        item they do not want. One real message asked for no defensive items on a mage, the
        answer argued, and the plan did not change. What they typed now reaches every later
        request of the match as an instruction (see advisor.render_request).
        """
        with self.lock:
            state, game_id = self.state, self.game_id
            if state is None or state["me"] is None:
                return "No game is running, so there is nothing to answer about yet."
            self.told.append({"time": int(state["time"]), "text": " ".join(question.split())[:300]})
            state["told"] = list(self.told)
            previous = self._plan_summary()
        text, meta = advisor.answer_question(self.sd, state, previous, question)
        log("question", game=game_id, game_time=int(state["time"]), question=question, latency=meta.get("latency"),
            cost=meta.get("cost"), answer=text)
        with self.lock:
            self._spent(meta)
            if game_id == self.game_id:
                self.request(f"the player typed: {' '.join(question.split())[:120]}", urgent=True)
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
                self._note_picture_read(result, int(state["time"]))
            self.screen = {**result, "at": time.time(), "game_time": int(state["time"]),
                           "took": round(time.time() - started, 1)}
            if meta:
                self._spent(meta)

    def _note_picture_read(self, result: dict, game_time: int):
        """Record an augment choice read from a picture. Call with the lock held.

        The choice on screen usually has a record already, made by the local card reader. The
        picture can show a card that reader missed. Before this, the picture got a second
        record of its own, and one choice could then yield two augments: in a real match the
        reader saw two cards and picked BEES!!!, the picture showed the third and picked it,
        the player took that one, and the coach planned around both.
        """
        canon = lambda name: (self.sd.augment(name) or {}).get("name") or name
        names = [canon(o["name"]) for o in result["offered"]]
        pick = canon(result["pick"]) if result["pick"] else ""
        result["pick"] = pick
        for o in result["offered"]:
            o["name"] = canon(o["name"])
        episode = self._offer
        if episode is None and self.offers and game_time - self.offers[-1]["time"] <= 45 \
                and set(names) & set(self.offers[-1]["names"]):
            episode = self.offers[-1]                # the same choice, read just after it closed
        if episode is None:
            self.offers.append({"names": names, "pick": pick, "why": result["why"], "taken": None, "assumed": False,
                                "time": game_time})
            return
        episode["names"] = list(dict.fromkeys(names + episode["names"]))
        episode["by_picture"] = True
        if not episode["taken"] or episode["assumed"]:
            episode["pick"], episode["why"] = pick, result["why"]
        if episode["taken"] and episode["assumed"] and pick and episode["taken"] != pick:
            # It closed on the earlier pick. The player has now been shown another: stop assuming either.
            episode["taken"], episode["assumed"] = None, False
            self._augments_changed("", replan=False)

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

    def _keep_death_shot(self, shot):
        """Save what the screen shows a few seconds after a death, for the first deaths of a match.

        The game API does not say which abilities killed the player; the game's own death
        recap does. These pictures are kept to find out whether that recap is on screen
        without a click, and so whether the coach could read it.
        """
        with self.lock:
            if not self._death_shot_at or time.time() < self._death_shot_at or not self.source.capture:
                return
            self._death_shot_at = 0.0
            folder, game_time = config.CAPTURE_DIR / self.game_id, int(self.state["time"])
        folder.mkdir(parents=True, exist_ok=True)
        shot.save(folder / f"death_t{game_time:05d}.png")

    def scan_for_offer(self):
        """Look at the screen once for an augment offer and react to what is there.

        Runs every 0.7 seconds during an ARAM: Mayhem match. Reading the three card titles
        takes about 50 ms locally, so no hotkey and no model call are needed to notice an offer.

        Cards animate in, and a scan can catch one or two of them. In eight real games that
        produced 80 requests for 29 offers. So a set of cards is acted on only after two scans
        in a row read the same thing, a set of fewer than three is given a little longer to
        fill in, and a set already answered in this offer is answered from memory.
        """
        with self.lock:
            state = self.state
            if (self.status != "live" or state is None or state["me"] is None
                    or state["mode"] != "KIWI" or state["ended"]):
                return
        if not screen.league_in_front():
            return
        if self._reader is None:
            self._reader = ocr.OfferReader(self.sd.augments_all())
        shot = screen.grab()
        self._keep_death_shot(shot)
        offer = self._reader.find(shot)
        names = [a["name"] for a in offer]
        with self.lock:
            if self.state is None:
                return
            if not names:
                self._offer_candidate = None
                self._offer_closed_maybe()
                return
            if self._offer is not None and self._offer_misses:
                # Scans that found no cards while this offer was open. Kept for the record: a card that is taken
                # may clear the screen for a moment before the next choice, which a reroll never does.
                self._offer["gap"] = max(self._offer.get("gap", 0), self._offer_misses)
            self._offer_misses = 0
            if self._offer is not None:
                self._offer["last_seen"] = names         # even one unconfirmed read: it shows a late reroll
            if names != self._offer_candidate:
                self._offer_candidate, self._offer_partial = names, 0
                if self._offer is not None and self._offer["names"] and names != self._offer["names"]:
                    # Kept for the record: cards read once, between two sets that were read twice. A reroll changes
                    # one card at a time, so these show whether three new cards came together or one by one.
                    log("offer_glimpse", game=self.game_id, game_time=int(self.state["time"]), cards=names)
                return                       # wait for a second scan to agree
            if len(names) < 3:
                self._offer_partial += 1
                if self._offer_partial < 3:
                    return                   # a third card may still be appearing
            earlier = self._offer
            if earlier is not None and earlier["names"] and not set(names) & set(earlier["names"]):
                # Every card changed at once. That is one of two things, and the screen does not say which.
                # A second choice: Mayhem follows some augments with another choice, with no gap between
                # the two, so a card of the earlier one has been taken. Before this check the second
                # choice replaced the first in the coach's record: two real games lost an augment that
                # way (Infernal Conduit, Recursion). Or the player rerolled all three cards within a
                # second or two, which this player does whenever all three look weak, and nothing has
                # been taken. Read as a second choice, that put Celestial Body in the record of a match
                # whose player never held it, and every plan after was built on it.
                # What a reroll can and cannot do settles most cases. Each card has one reroll: in 103
                # recorded choices no card changed twice. A rerolled card keeps its tier (76 of 78). Stat
                # shards and ability upgrades appear only after a pick. So it is a second choice when
                # the new cards are shards or upgrades, when a card of the earlier set had already been
                # rerolled, or when the tier is a different one. Anything else is read as a reroll of all
                # three. Of the 11 such moments with a pick and a post-game record to check against, that
                # is right in 10. The miss is a second choice of the same tier with no reroll before it
                # (one match), which leaves one augment unrecorded. Always reading a second choice was
                # right in 9, and both misses were augments the player never held.
                tiers = lambda cards: {t for t in ((self.sd.augment(n) or {}).get("tier") for n in cards) if t}
                was, now = tiers(earlier["names"]), tiers(names)
                second_choice = (all(_follow_up(n) for n in names) or earlier.get("rerolled", 0) > 0
                                 or bool(was and now and not was & now))
                if second_choice:
                    # With no pick given yet, the card that was taken is not known and nothing is assumed.
                    self._end_offer(earlier, replan=False)   # the plan waits for the choice now on screen
                else:
                    earlier["rerolled"] = 3
                    log("offer_rerolled_whole", game=self.game_id, was=earlier["names"], now=names, pick=earlier["pick"],
                        gap=earlier.get("gap", 0))
            if self._offer is None:
                self._offer = {"names": [], "pick": "", "why": "", "taken": None, "assumed": False,
                               "answers": {}, "time": int(self.state["time"])}
                self.offers.append(self._offer)
            if names == self._offer["names"]:
                return
            if self._offer.get("by_picture") and set(names) <= set(self._offer["names"]):
                return                       # a picture read these cards and one more that this reader cannot
            episode = self._offer            # a new offer, or a reroll changed the cards
            if len(names) == 3 and len(episode["names"]) == 3 and set(names) & set(episode["names"]):
                # Count the cards rerolled in this choice: one that has been rerolled cannot change again.
                episode["rerolled"] = episode.get("rerolled", 0) + sum(a != b for a, b in zip(episode["names"], names))
            episode["names"], episode["pick"], episode["why"] = names, "", ""
            hoped_for = ((self.advice or {}).get("scaling") or {}).get("augments_to_look_for") or []
            wanted = [n for n in names if any(n.lower() in w.lower() for w in hoped_for)]
            self.screen = {
                "kind": "augment_choice", "pick": "", "why": "", "note": "", "reroll": "", "choosing": True,
                "wanted": wanted, "at": time.time(), "game_time": int(self.state["time"]),
                "offered": [{"name": a["name"], "tier": a["tier"], "summary": a["description"][:240]} for a in offer],
            }
            log("offer_seen", game=self.game_id, game_time=int(self.state["time"]), offered=names, wanted=wanted)
            known = episode["answers"].get(tuple(names))
            if known:                        # the cards went back to a set already answered
                episode["pick"], episode["why"] = known["pick"], known["why"]
                self.screen.update(known, choosing=False)
                return
            args = (episode, offer, names, self.state, self._plan_summary(), self.game_id, shot)
        threading.Thread(target=self._choose_augment, args=args, name="augment", daemon=True).start()

    def _choose_augment(self, episode, offer, names, state, previous, game_id, shot=None):
        # Stat shards and a few augments have no description in the data. For those, Claude reads
        # the cards from the picture instead, which needs an API key.
        by_picture = shot is not None and config.BACKEND == "api" and any(not a["description"] for a in offer)
        try:
            if by_picture:
                seen, meta = advisor.read_screen(self.sd, state, previous, screen.to_jpeg(shot), names)
                on_offer = {ocr.fold(n): n for n in names}
                result = {"pick": on_offer.get(ocr.fold(seen["pick"]), seen["pick"]), "why": seen["why"],
                          "reroll": "", "note": seen["note"]}
                if seen["offered"]:
                    result["offered"] = [{"name": o["name"], "tier": "", "summary": o["summary"]} for o in seen["offered"]]
            else:
                result, meta = advisor.choose_augment(self.sd, state, previous, offer)
        except Exception as exc:
            result, meta = {"pick": "", "why": f"No pick: {exc}", "reroll": "", "note": ""}, {}
        log("offer_pick", game=game_id, offered=names, pick=result["pick"], why=result["why"],
            latency=meta.get("latency"), cost=meta.get("cost"), by_picture=by_picture)
        with self.lock:
            if game_id != self.game_id:
                return
            if meta:
                self._spent(meta)
                episode["answers"][tuple(names)] = result
            if episode["names"] != names:
                return                       # the cards changed while Claude was answering
            episode["pick"], episode["why"] = result["pick"], result["why"]
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
            self._reader = ocr.OfferReader(self.sd.augments_all())
        shot, cursor = screen.grab(), screen.cursor_position()
        lines = ocr.read_lines(shot)
        augment = self._reader.tooltip(lines, cursor)
        if augment is None:
            on_panel = ((cursor[0] < 0.21 * shot.width or cursor[0] > 0.79 * shot.width)
                        and 0.26 * shot.height < cursor[1] < 0.68 * shot.height)
            if on_panel and self.source.capture and self._hover_misses < 6:
                self._hover_misses += 1
                folder = config.CAPTURE_DIR / game_id
                folder.mkdir(parents=True, exist_ok=True)
                shot.save(folder / f"hover_miss_t{game_time:05d}_{self._hover_misses}.png")
                near = [l["text"] for l in lines if abs(l["x"] - cursor[0]) < 620 and abs(l["y"] - cursor[1]) < 420]
                log("hover_miss", game=game_id, game_time=game_time, cursor=list(cursor), text_near_cursor=near[:25])
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
        self._end_offer(episode)

    def _end_offer(self, episode, replan: bool = True):
        """An offer is over. Call with the lock held.

        replan: ask for a new plan. False when another choice is already on screen: the plan made
          when that one closes covers both.
        """
        self._offer = None
        log("offer_closed", game=self.game_id, offered=episode["names"], pick=episode["pick"], taken=episode["taken"],
            followed_by_another=not replan, rerolled=episode.get("rerolled", 0), gap=episode.get("gap", 0))
        # A reroll replaces one card or two. When every card is different, that is the next choice
        # (a stat shard follows some augments at once), and this one was made before it appeared.
        last = episode.get("last_seen") or []
        late = [n for n in last if n not in episode["names"]] if set(last) & set(episode["names"]) else []
        if episode["pick"] and not episode["taken"] and late:
            # A card appeared after the pick was made, too late for a new pick. The player rerolled and
            # may have taken the new card. In a real match that happened twice, the coach assumed its
            # own pick both times, and planned around two augments the player did not hold. Say so
            # and let the player tap what they took. Nothing is assumed and the build stays as it is.
            log("offer_changed_late", game=self.game_id, pick=episode["pick"], late=late)
            episode["names"] = list(dict.fromkeys(late + episode["names"]))
            if self.screen and self.screen.get("kind") == "augment_choice":
                cards = [self.sd.augment(n) or {"name": n, "tier": "", "description": ""} for n in episode["names"]]
                self.screen.update(
                    pick="", why="", reroll="", choosing=False,
                    note="The cards changed after my pick, so I do not know which one you took. Tap it here.",
                    offered=[{"name": a["name"], "tier": a["tier"], "summary": a["description"][:240]} for a in cards])
            if replan and self._remake_owed:     # the choice before this one still has its plan to come
                self._remake_owed = False
                self.request("the player's augments changed", urgent=True, fresh=True)
            return
        if episode["pick"] and not episode["taken"]:
            # The player cannot be seen choosing. The coach gave a pick and was not corrected, so
            # assume they took it, mark it as assumed, and let a tap on the panel correct it.
            episode["taken"], episode["assumed"] = episode["pick"], True
            self._augments_changed(
                f"the player probably took the augment {episode['pick']} (the coach's pick, not confirmed)", replan,
                augment=episode["pick"])

    def _augments_changed(self, reason: str, replan: bool = True, augment: str = ""):
        """Rebuild the taken-augment lists from the offers and refresh the plan. Call with the lock held.

        augment: the augment that was added. The build is remade from several fresh plans only
        when it matters on this champion (see research.matters). Otherwise the next plan is an
        ordinary one, which knows of the augment and keeps the build unless it says why not.
        """
        taken = [o for o in self.offers if o["taken"]]
        self.my_augments = [o["taken"] for o in taken]
        self.assumed_augments = [o["taken"] for o in taken if o["assumed"]]
        if self.state is not None:
            self.state["my_augments"] = list(self.my_augments)
            self.state["assumed_augments"] = list(self.assumed_augments)
        if self.screen and self.screen.get("kind") == "augment_choice" and self.offers:
            self.screen["taken"] = self.offers[-1]["taken"]
            self.screen["assumed"] = self.offers[-1]["assumed"]
        me = self.state["me"] if self.state else None
        matters = bool(augment) and research.matters(self.sd, me and me["champ_id"], augment)
        if not replan:
            self._remake_owed = self._remake_owed or matters     # the plan comes when the choice now on screen closes
            return
        if self._death_at:                   # this plan also serves as the plan for the death that was held
            self._death_at = 0.0
            reason += "; the player is dead and the shop is open"
        remake, self._remake_owed = matters or self._remake_owed or not augment, False
        self.request(reason, urgent=True, fresh=remake)

    def took_augment(self, name: str):
        """Record an augment the player says they took. It replaces an assumed one from the same offer."""
        name = name.strip()[:60]
        with self.lock:
            if not name or self.state is None:
                return
            episode = next((o for o in reversed(self.offers) if name in o["names"]), None)
            unknown = episode is None
            if unknown:
                episode = {"names": [name], "pick": "", "taken": None, "assumed": False,
                           "time": int(self.state["time"])}
                self.offers.append(episode)
            if episode["taken"] == name and not episode["assumed"]:
                return
            episode["taken"], episode["assumed"] = name, False
            # One choice gives one augment. An assumption made for the same choice is withdrawn: under a
            # second record of it (the record next to this one, sharing a card), or, when the player names
            # a card the coach never read, the choice that closed just before.
            at = self.offers.index(episode)
            for other in self.offers[max(0, at - 1): at + 2]:
                same = unknown or set(other["names"]) & set(episode["names"])
                if other is not episode and other["taken"] and other["assumed"] and same                         and abs(other["time"] - episode["time"]) <= 60:
                    log("augment_withdrawn", game=self.game_id, name=other["taken"], instead=name)
                    other["taken"], other["assumed"] = None, False
            log("augment_taken", game=self.game_id, name=name)
            self._augments_changed(f"the player took the augment {name}", augment=name)

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
                view["champ_options"] = self.champ_options
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
            view["deaths"] = state.get("deaths")
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
                              ("headline", "next_item_why", "how_to_play", "scaling", "skill_order", "changed")}
            meta = self.advice_meta
            view["meta"] = {"trigger": meta.get("trigger"), "age": int(time.time() - meta.get("at", time.time())),
                            "latency": meta.get("latency"), "game_time": int(meta.get("game_time", 0)),
                            "partial": bool(meta.get("partial"))}
            return view
