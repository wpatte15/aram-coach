# ARAM Coach

A local coaching panel for League of Legends ARAM and ARAM: Mayhem. It reads the live game state and asks Claude what to build and how to play, in plain language, for the match you are in.

It is built for players who find the number of items and augments overwhelming. It tells you exactly what to buy with the gold you have, which augment to take, and how to play your champion against the specific enemy team.

## What it does

- **Champion choice.** In champion select the panel ranks the champions you can take: the one you hold, your cards, and the team's bench. Each is rated for how easy it is for you, from your own description in `player.txt`, with your past results on it and what your team is missing. The ranking is local and instant, and updates as the bench changes. The coach only shows the ranking: you make the swap yourself.
- **How you died.** After each death the panel says what kind it was: outnumbered (for example 3 against 5), first on your team to die in the fight, alone, or straight after respawning. When one kind repeats, it shows one rule for it, and the next plan and the post-game review use the counts.
- **Before the match.** In champion select it plans a build for your champion and writes it into the in-game shop as an item set named "Coach: ...". The set holds the main build, a group of items per enemy type, a group per direction an augment could push the build, and a pool of other items. On the loading screen, once the enemy team is known, it prepares the full plan so it is ready when you spawn.
- **What to buy now.** When you die, the panel lists the exact items to buy with your current gold, including components. This part is local arithmetic and updates every second.
- **The plan.** A build order with a reason per item, three to five instructions for this champion against these enemies, the most dangerous enemies, an estimate of which enemies you can fight alone, and how your build scales.
- **Combinations.** In ARAM: Mayhem the coach looks for augments, items and a part of your champion's kit that multiply each other, such as crit augments plus Infinity Edge on a Garen whose spin can crit. It prefers augment cards that start or extend one, rebuilds the item order around it, and shows on the panel which pieces you hold and what is still missing. When nothing supports a combination, it says so and keeps the plain build.
- **Augments.** The game does not report augments, so the coach reads them off the screen with Windows' built-in text recognition. When the three augment cards appear, the panel shows them and Claude's pick follows in about five seconds. No key press is needed.
- **Your augments.** When the cards close, the coach records its pick as the one you took, marked "assumed". Tap a different card on the panel if you took that one. The "Your augments" card lists what is recorded.
- **Other players' augments (optional).** Hold Tab and rest the mouse on an augment icon on the scoreboard. The coach reads the tooltip and records the augment against that player. Other players appear on the "Your augments" card once one of theirs has been read.
- **Questions.** Type a question into the panel, such as "is anti-heal worth it now?".
- **After the match.** A short review written from the game's own post-game record: measured damage, healing, items and every player's augments.

## Requirements

- Windows 10 or 11. Text recognition and screen capture use Windows APIs.
- League of Legends, with the game language set to English and the window mode set to Borderless or Windowed.
- Python 3.12 or newer.
- Your own access to Claude: an Anthropic API key, or a Claude subscription with Claude Code installed. See "Connect your own Claude".

## Setup

1. Download this repository: on its GitHub page choose Code, then Download ZIP, and unzip it. Or clone it with git.
2. Double-click `setup.bat`. It creates a private Python environment in `.venv`, installs the packages, and creates a `.env` file.
3. Open `.env` in a text editor and choose how the coach reaches Claude.

## Connect your own Claude

The coach never ships with credentials. Each person uses their own account, in one of two ways.

| | API key | Claude subscription |
|---|---|---|
| What you need | A key from [console.anthropic.com](https://console.anthropic.com/) | [Claude Code](https://claude.com/claude-code) installed and signed in |
| Setup | Put `ANTHROPIC_API_KEY=...` in `.env` | Leave the key out of `.env`. Run `claude` once and sign in |
| Cost | Billed per use, about $1 to $1.50 per match | Counts against your plan's usage limits |
| Speed | About 16 seconds per plan | Slower: each request starts a new process |
| Limits | None | No cost counter. The F9 screenshot read is unavailable. Automatic augment reading still works |

The key is read from `.env` by this app only. Do not set `ANTHROPIC_API_KEY` as a system-wide environment variable if you also use Claude Code, because that switches Claude Code itself to API billing.

`.env` is listed in `.gitignore`. Never commit it.

## Tell the coach how you play

`player.txt` is your own description of your skill, in plain sentences. The coach reads it on every request and coaches the player you describe, not a better one. `setup.bat` creates it from `player.example.txt`.

Say which champions you understand, what you do on the rest, and whether you press item buttons. For example:

```
Champions I understand reasonably well: Blitzcrank, Thresh.
On every other champion I mostly click on enemies and press my abilities whenever they are ready.
I never press item buttons, so do not count on me using them.
```

With that, the coach values items by their stats and passive effects only, avoids items whose worth is mostly a button, prefers augments that work by themselves, gives at most three simple rules on a champion you do not know, and judges which fights you can take by your execution. Edits take effect on the next plan; no restart is needed. The file is ignored by git.

## Run

```
start.bat            waits for a game
start.bat --demo     a built-in sample game, no League needed
start.bat --replay captures\<game folder>     replays one of your recorded games
```

Open `http://127.0.0.1:8777` in a browser. A second monitor works best. With one monitor, use a laptop or phone:

- On a network you trust, set `ARAMCOACH_HOST=0.0.0.0` in `.env` and open `http://<your PC's address>:8777` on the other device. The panel has no password.
- With [Tailscale](https://tailscale.com/), keep the default host and run `tailscale serve --bg --https=8777 http://127.0.0.1:8777`. The panel is then reachable only from your own devices.

## In a game

1. Start the coach before you queue. The panel shows your champion's plan during champion select.
2. In the shop, open the item set dropdown and pick "Coach: ...".
3. When you die, read the top card on the panel and buy what it lists.
4. At an augment choice, look at the panel. The pick arrives a few seconds after the cards do.
5. Optional: to record other players' augments, hold Tab and rest the mouse on each icon for half a second.
6. After the match, the review appears on the panel.

`F9` is a fallback that sends a screenshot to Claude when the automatic augment reading misses.

## Cost and speed

Measured with Claude Opus 5.5 at low effort and an API key, in a 20-minute five-against-five match:

- A plan takes about 16 seconds and costs about $0.06.
- An augment pick takes about 5 seconds and costs about $0.03.
- A match makes about 15 plans, because plans are made when you die, not while you are alive.
- A whole match costs roughly $1 to $1.50.

`ARAMCOACH_SPEED=fast` makes plans about 2.5 times quicker for twice the price.

### Choosing a model

Set `ARAMCOACH_MODEL` and `ARAMCOACH_EFFORT` in `.env`. These figures come from the same five moments of one real match, so treat them as a guide, not a benchmark.

| Model and effort | Full plan | Build order visible | Cost per plan | Plans read closely |
|---|---|---|---|---|
| `claude-opus-5-5`, `low` (default) | 19 s | 8 s | $0.07 | No mistakes found |
| `claude-sonnet-5-5`, `medium` | 14 s | 5.5 s | $0.03 | Builds sound; fight-alone estimates too optimistic |
| `claude-sonnet-5-5`, `low` | 12 s | 3.5 s | $0.03 | About one game-knowledge slip per plan |
| `claude-haiku-5-5`, `low` | 17 s | 11 s | under $0.01 | Mistakes in most plans; not recommended |

Examples of the slips: Sonnet at low effort put two burn items in one build although their effects do not combine, and told the player to sell an item that cannot be sold. Haiku listed an item as owned that the player did not have.

Sonnet roughly halves the cost of a match. Opus is the default because the player this was built for follows the plan literally and cannot catch a wrong instruction.

Raising Opus above `low` effort did not pay off on three of those moments. Medium took 31 seconds per plan and high took 36, against 21 at low, for 17% and 29% more cost. The builds were the same or differed only in the last two items. A plan that takes over 30 seconds arrives after most respawn timers have run out.

## Settings

Put these in `.env` as `NAME=value` lines.

| Variable | Default | Meaning |
|---|---|---|
| `ANTHROPIC_API_KEY` | none | Your API key. When set, the API is used |
| `ARAMCOACH_MODEL` | `claude-opus-5-5` | Claude model ID |
| `ARAMCOACH_EFFORT` | `low` | Reasoning effort: `low`, `medium`, `high`, `xhigh`, `max`. Higher is slower |
| `ARAMCOACH_SPEED` | `standard` | `fast` is quicker and costs twice as much. API key only |
| `ARAMCOACH_BACKEND` | automatic | `api` or `cli`. Overrides the automatic choice |
| `ARAMCOACH_PORT` | `8777` | Panel port |
| `ARAMCOACH_HOST` | `127.0.0.1` | `0.0.0.0` opens the panel to your network |
| `ARAMCOACH_HOTKEY` | `F9` | Key for the screenshot fallback. `F1` to `F12` |
| `ARAMCOACH_UPDATE_WHILE_ALIVE` | `0` | `1` also updates the plan on enemy purchases while you are alive |

Other timings are in `aramcoach/config.py`.

## How it works

| File | Role |
|---|---|
| `live.py` | Polls the game's Live Client Data API once per second and reduces it to the state the coach uses |
| `lcu.py` | Reads the League client's local API: champion select, loading screen, post-game record |
| `coach.py` | The core loop: decides when to ask for a plan and builds what the panel shows |
| `advisor.py` | The prompts, and validation of Claude's answers |
| `llm.py` | Calls Claude, through the API or the Claude Code CLI |
| `shop.py` | Turns a build order and your gold into exact purchases |
| `pregame.py`, `itemset.py` | Champion-select and loading-screen plans, and the in-game item set |
| `champfit.py` | Ranks the champions on offer in champion select: ease ratings, your record, team needs |
| `deaths.py` | Classifies each of your deaths from the kill events and who was alive |
| `ocr.py`, `screen.py` | Screen capture, text recognition, augment offers and scoreboard tooltips |
| `postgame.py` | The post-game record and review |
| `static_data.py` | Item, champion, ability and augment data, cached per patch |
| `server.py`, `web/index.html` | The panel |

The coach makes a plan at game start, when you die (if the plan is more than 45 seconds old or an enemy has finished an item since), and when you take an augment.

Estimated enemy stats come from base stats, level and item stat lines. They leave out champion passives, augments and item passives, so they are minimums. The fight-alone table and cost-benefit answers are estimates, not measurements.

## Files written

- `cache/<patch>/`: item, champion, augment and ability data, downloaded once per patch.
- `cache/champion_fit.json`: Claude's rating of every champion for you. It is written once, in about a minute, and again whenever you edit `player.txt`.
- `cache/history.json`: your champion, result and deaths in recent matches, copied from the client's match history.
- `captures/champselect/`: a few raw champion-select sessions per match, with player identities removed, kept to check the client's data format.
- `captures/<game start time>/`: raw game API payloads, screenshots taken for augment reads and scoreboard reads, the post-game record, the kill timeline and the review. These contain other players' names. They are ignored by git; do not share them.
- `logs/coach.log`: one line per event. Read this to find out what happened in a game.
- `Config\Global\Recommended\!!!aramcoach-0.json` in the League folder: the in-game item set. It is removed when the match ends.

## Data sources

| Data | Source |
|---|---|
| Live game state | The game's Live Client Data API on port 2999 |
| Champion select, loading screen, post-game record | The League client's local API |
| Items, champion text, base stats | Riot Data Dragon |
| Attack damage growth, ability numbers by rank | Meraki Analytics community dataset. Can lag a patch |
| Augment ids and names | CommunityDragon |
| Augment descriptions | League of Legends Wiki. A copy is bundled in `aramcoach/data` under CC BY-SA 3.0; see the note in that folder |

## Tests

```
.venv\Scripts\python.exe tests\test_shop.py
.venv\Scripts\python.exe tests\test_deaths.py
.venv\Scripts\python.exe tests\test_champfit.py
.venv\Scripts\python.exe tests\test_simulated_game.py
.venv\Scripts\python.exe tests\test_real_scoreboard.py
```

- `test_shop.py` checks the purchase arithmetic.
- `test_deaths.py` checks the death breakdown against small hand-made fights.
- `test_champfit.py` checks the champion-select ranking.
- `test_simulated_game.py` runs a whole recorded match through the coach with a fake League client and a stub in place of Claude. It costs nothing. Run it after any change to `coach.py`, `pregame.py` or `postgame.py`.
- `test_real_scoreboard.py` checks scoreboard row detection against a real picture in `captures/`. It is skipped when you have no such recording.

## What it does not do

The coach reads the game's local APIs, the League client's local API, and the screen. It does not read or change the game's memory, inject code, or send input to the game. It shows nothing the game does not already show you.

## Known limits

- The game API does not report augments. Other players' augments are known only when you point at them, or when one replaces a summoner spell.
- The game reads the item set once, when the match loads. A later plan can name an item that is not in the set; the panel marks it, and you find it with the shop search. The set written in champion select is built wide to make this rare.
- The augment tooltip reader has been tested on a real scoreboard layout but not yet on a real tooltip.
- The champion-choice ranking reads the bench from the champion-select session. The two champion cards at the start are read from the client's "subset champion list". That source is taken from the client's own type definitions and has not yet been watched in a real champion select.
- The item catalog covers the ARAM shop only.
- Text recognition needs the English game client.

## Disclaimer

ARAM Coach is not endorsed by Riot Games and does not reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games and all associated properties are trademarks or registered trademarks of Riot Games, Inc.
