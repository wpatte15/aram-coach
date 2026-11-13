# ARAM Coach

A local coaching panel for League of Legends ARAM and ARAM: Mayhem. It reads the live game state and asks Claude what to build and how to play, in plain language, for the match you are in.

It is built for players who find the number of items and augments overwhelming. It tells you exactly what to buy with the gold you have, which augment to take, and how to play your champion against the specific enemy team.

## What it does

- **Champion choice.** In champion select the panel ranks the champions you can take: the one you hold, your cards, and the team's bench. Champions you name in `player.txt` as ones you love or like to play come first. The rest are rated for how easy they are for you, from your own description in `player.txt`, with your past results on each and what your team is missing. The ranking is local and instant, and updates as the bench changes. The coach only shows the ranking: you make the swap yourself.
- **How you died.** The coach gives each death a verdict from the kills around it: a fight your team won or traded evenly (not a mistake, and often the job on a front-line champion), alone against three or more enemies, caught with no fight around, a fight that started short-handed, a fight you started below half health, or an even fight your team lost. The panel does not show the verdicts during a match. The next plan uses the counts, and the post-game review lists them. The game's local data does not say which ability killed you or whether your own abilities landed, so a lost even fight is as far as the verdict goes.
- **Before the match.** In champion select it plans a build for your champion and writes it into the in-game shop as an item set named "Coach: ...". The set holds the main build, a group of items per enemy type, a group per direction an augment could push the build, and a pool of other items. On the loading screen, once the enemy team is known, it prepares the full plan so it is ready when you spawn.
- **What to buy now.** When you die, the panel lists the exact items to buy with your current gold, including components. This part is local arithmetic and updates every second.
- **The plan.** A build order with a reason per item, and at most three instructions for this champion against these enemies. On a champion that is not on your `Love to play` or `Like to play` lines, the three instructions are how to press the basic abilities, how to cast the ultimate step by step with keys and mouse, and the main danger. The controls come from a community dataset's ability text, because the game's own descriptions often leave them out. During a match the panel shows four things: the augment to take while an offer is open, what to buy now, the build order, and those instructions.
- **Item checks.** Two rules are decided by a program, not left to Claude. If you never press item buttons, the coach never recommends an item whose only effect is behind its button, such as Locket of the Iron Solari or Zhonya's Hourglass. And it never recommends an item that fires on healing or shielding an ally, such as Moonstone Renewer, for a champion who does that at most once a fight. Both mistakes happened in real games before these checks existed. An item that breaks a rule is removed from the plan and left out of the item set. Two more are decided the same way. Once you own finished boots, the build keeps that pair. And a build holds one item per passive that works from one item only, such as Spellblade.
- **Research done in advance (experimental, off by default).** Set `ARAMCOACH_RESEARCH=saved` to use it. In the two real matches played with it on, its text put an item in the build that the situation did not support; the causes found were fixed, and it stays off until `tests/replay_match.py` shows it does no harm over whole recorded matches. During a match Claude answers in seconds, which is recall, not reasoning. The working-out that finds a combination takes minutes, so the coach does it ahead of time, at high effort, and keeps it. There are two parts. The augment map covers every augment: what it does as a mechanism, what a champion's kit must have for it to pay, which items and which other augments multiply it, and when it does nothing. A playbook per champion holds what on the kit a combination can run through, the combinations the kit supports with what each piece feeds into, and the augments that kit uses unusually well or cannot use. Plans get the playbook and the lines for the augments you hold; an augment offer gets what the research found for each card. All of it is worked out from ability, augment and item text. The coach uses no statistics about what other players pick: a tool that shows the popular picks already exists, and following them pulls the advice toward the average build. During a match, a combination you hold no augment of is listed by name and by the augments that open it, without its items: in the first match played with a playbook, a plan bought an item out of a combination that was never opened.
- **One build, held steady.** A program holds the plan steady, because each answer from Claude is a fresh opinion and a player who follows the plan purchase by purchase experiences the differences as the coach changing its mind. An item you hold parts for is finished first, whatever a new plan says. An ordinary update keeps the build unless it says what it changed and why, or lists a finished item you bought off the plan. Every plan is made with the plan in force in front of it, and with the items earlier plans of the match took out, when and for what reason, so that going back on a swap is a decision and not an accident. For one day a program forbade any return of a removed item. In the next real match a plan took Force of Nature out at 3:40 on a wrong damage estimate, four later plans tried to put it back, and the rule overrode all four: the player finished with five armor items against damage that was 68% magic. The rule was removed. The log now records the build a plan asked for whenever the coach shows a different one (`proposed`, `proposed_change`). Replayed over four recorded matches, no item left the build and came back, and the next item to buy changed up to three times a match, mostly because the recorded purchases differed from the replayed plan. An experimental option, off by default (`ARAMCOACH_PLAN_VOTES=3`), remakes the build from three independent plans at the start of a match and after an augment that matters: with it on, the coach asks Claude for three independent plans at once, none of them shown the earlier plan, and combines them: an item most of them list goes in, a slot they disagree on keeps what the plan had if one of them still lists it, and the rest comes from the plan the others agree with most. Asked the same thing eight times in real matches, Claude gave the same core items and nearly always the same next purchase, but different last slots, and a plan that leans on its last answer can miss a better build. Between those moments the plan is adjusted from the last one as before, so it does not shift under you. The panel announces a change only when one of your next two purchases changes. In one real match with it on, five augments brought five remakes in thirteen minutes and the player's next item changed three times.
- **Item numbers, and arithmetic done by a program.** The game's own item file names every effect and leaves most of the numbers out: Unending Despair "deals magic damage to nearby enemy champions", Sunfire Aegis "deals magic damage per second", Thornmail "deals magic damage to the attacker". The coach could not value what it could not see, and in 35 recorded matches it never once listed Unending Despair. The item list Claude reads now carries the real numbers of each effect, from the Meraki Analytics community dataset (the same source as the champion numbers). They are the standard game's numbers, so one can be slightly off where this mode changes an item. Claude answers a plan in about ten seconds and does not multiply in that time, so for a champion that builds defense a program does it: for every defensive item, on your real health, armor and magic resist, how much longer you would last in a fight with the item's own effect counted (Unending Despair's healing per enemy near you, Jak'Sho's growing resistances, Kaenic Rookern's shield, Randuin's against crits), and how much damage the effect deals. The fight is a model with its assumptions stated in the request: three enemies in reach, an enemy team that kills you in twelve seconds as you stand. Run on five real moments, the order at the top moved with those assumptions and the bottom did not: the item the coach had named next was in the lower half every time. The figures are information for the plan. An augment or a combination that needs a particular item still comes first. Damage dealers have no such figures in the request; their arithmetic is in the calculations below.
- **Calculations Claude can run (experimental, off by default).** Set `ARAMCOACH_TOOLS=plan` to use them. Before a plan that sets the build, Claude can call a program with the builds it is weighing and get back numbers worked out on your real stats: what basic attacks do with each build, what every ability of your kit does, how long a set of defensive items keeps you alive, or the result of a formula it writes for a rule of your kit. It then reasons from those numbers instead of from an item's name. Replayed over four recorded matches it added 2 to 6 seconds to about five plans a match and changed the builds; the replays do not show whether the changed builds win more. See Calculations.
- **What is killing you.** The game reports no damage during a match, so the coach estimates how the damage that gets through to you divides between physical and magic. It works in two steps: what the enemies aim at you, from each enemy's champion and items and from who has killed you, and then how much of each kind your own armor and magic resist stop. The second step matters most on a champion that stacks one resistance. A player with 460 armor and 70 magic resist takes 18% of the physical damage aimed at them and 59% of the magic damage, so most of what kills them is magic even against a team of attackers. The first version left that step out: it told a Malphite who was stacking armor that the damage on them was 60 to 75% physical for a whole match in which the post-game record measured 32%, and the plan swapped its one magic resist item for more armor. Every plan is given that estimate, what you hold against it, and, from your real stats, how much more of that damage you could take with each defensive item for its price. This is information, not a rule: the combination comes first, and dying does not by itself move a defensive item up. It is there so that a defensive item, when the build takes one, is the right kind, and so that a champion stacking health gets the resistance that multiplies it. An earlier version forced a defensive item next after three deaths outside won fights. Replayed over eleven recorded matches it fired in nine and would have broken up the crit combination this coach was designed around, so it was removed. Enemies whose ability text says true damage are named, because no resistance reduces it and only health answers it. All of that is for champions that build defense: the ones that stand in front, and the ones the game classes as tanks, which includes the hook supports. A champion that is in the match to deal damage or to back up teammates is told the kind of damage and then the player's instruction: no item bought only for armor, magic resist or health, because on a fragile champion it does not prevent the death and it delays every item that makes the kit work. Such a champion is shown only defensive items that also carry its own damage stat, and a plain defensive item belongs in its build only when an augment turns health or resistances into damage or healing. The list of items by survivability used to be shown to every champion, with Randuin's Omen, Warmog's Armor and Jak'Sho at the top, and the plan took one for a Vel'Koz, a Zilean and a Tryndamere "because physical damage keeps killing you": 3 of 5 matches on such champions, against 0 of 4 before the estimate existed. The post-game review is told the same instruction, so it no longer calls a mage's build without armor a mistake.
- **Combinations.** In ARAM: Mayhem the coach looks for augments, items and a part of your champion's kit that multiply each other, such as crit augments plus Infinity Edge on a Garen whose spin can crit. It prefers augment cards that start or extend one, rebuilds the item order around it, and names the combination and its next missing piece at the top of the build card. When nothing supports a combination, it keeps the plain build.
- **Augments.** The game does not report augments, so the coach reads them off the screen with Windows' built-in text recognition. When the three augment cards appear, the panel shows them and Claude's pick follows in about five seconds. No key press is needed.
- **Your augments.** When the cards close, the coach records its pick as the one you took, marked "assumed". Tap a different card on the panel if you took that one. The top of the panel lists what is recorded. One choice gives one augment: a tap replaces the assumption for that choice. When a card changes after the pick and you choose before the coach can answer again, it assumes nothing, says so, and waits for your tap. When all three cards change at once, the coach has to guess between two things: you took a card and a second choice followed, or you rerolled all three. What a reroll can and cannot do settles most cases. Each card has one reroll (in 103 recorded choices no card changed twice), a rerolled card keeps its tier (76 of 78), and stat shards and ability upgrades only ever follow a pick. So it is a second choice, and the pick is recorded, when the new cards are shards or upgrades, when one of the earlier cards had already been rerolled, or when the tier is a different one. Anything else is read as a reroll of all three and nothing is recorded. Checked against the 11 recorded moments with a post-game record, that is right in 10; the miss is a second choice of the same tier with no reroll before it, which leaves one augment unrecorded. The earlier rule always read a second choice: it was right in 9, and its two misses left the coach believing in augments you never held (Celestial Body on a Tryndamere, planned around to the end). The coach cannot see which card you click, so what it believes you hold is only as good as these sources. The post-game review is told when the game's own record shows you never held an augment the coach assumed.
- **Other players' augments (optional).** Hold Tab and rest the mouse on an augment icon on the scoreboard. The coach reads the tooltip and records the augment against that player, and later plans and augment picks take it into account. The panel does not list other players' augments.
- **Questions and instructions.** Type a question into the panel, such as "is anti-heal worth it now?". What you type about your build or how you want to play is an instruction for the rest of the match: the coach agrees, makes the plan again at once with it, and every later plan and pick of that match is told what you typed. Before this, one message asked for no defensive items on a mage; the answer began "Your teammates are half right" and the armor item stayed in the build.
- **After the match.** A review that reasons from everything recorded about the match: every player's measured numbers and augments, every kill grouped into fights with your part in each, the gold lead minute by minute, when each player finished each item, how you died, and what the coach itself told you to buy and pick. It does not grade or rank anyone, since the game and other tools already do. It says what decided the match, what your part in it was, which items and augments the record shows working, and where the coach's own advice was wrong. It takes about a minute to appear.

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

Say which champions you love or like to play, what you do on the rest, and whether you press item buttons. For example:

```
Love to play: Blitzcrank, Thresh
Like to play: Nautilus, Sona
On every other champion I mostly click on enemies and press my abilities whenever they are ready.
I never press item buttons, so do not count on me using them.
```

The two lines that start with `Love to play:` and `Like to play:` are read by a program as well as by Claude. In champion select a champion you love is ranked first, then one you like, then everything else, whatever the team is missing. Write the names separated by commas; a name the game does not have is ignored.

With that, the coach values items by their stats and passive effects only, never recommends an item whose only effect is a button, prefers augments that work by themselves, gives at most three simple rules on a champion you do not know, and judges which fights you can take by your execution. Edits take effect on the next plan; no restart is needed. The file is ignored by git.

The rule about item buttons is read from this file: a sentence that mentions "item buttons" together with "never", "not" or "don't" turns it on. Set `ARAMCOACH_ITEM_BUTTONS=yes` or `no` in `.env` to decide it yourself.

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
- The post-game review runs at high effort. It takes about a minute and costs about $0.15.
- With `ARAMCOACH_TOOLS=plan`, a plan that sets the build waits 2 to 6 seconds longer while Claude runs calculations, and a match costs about $0.20 more. See Calculations below.
- With `ARAMCOACH_PLAN_VOTES=3`, a plan remade from three answers takes as long as the slowest of them, about 16 to 19 seconds, and costs about $0.25. A match has up to five.
- A whole match costs roughly $1.50 to $2.
- With research switched on, it is paid for once per patch at most: about $4 for the augment map and about $0.70 for each champion's playbook. See Research below.

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

## Research

Research is off by default. With `ARAMCOACH_RESEARCH=saved` the coach uses what is saved, and with `1` it also writes its research by itself: the augment map when there is none, and a playbook for your champion when a match loads and that champion has none. A playbook takes about three minutes, so the first time you play a champion it arrives a few minutes into the match, after the first augment offer. Until then the coach uses the augment map alone. To have a playbook from champion select on, where it also shapes the item set, prepare it ahead.

To prepare ahead, run:

```
.venv\Scripts\python.exe -m aramcoach.research
.venv\Scripts\python.exe -m aramcoach.research Garen "Cho'Gath"
.venv\Scripts\python.exe -m aramcoach.research --show "Cho'Gath"
```

The first form writes whatever the augment map lacks, then a playbook for each champion on your `Love to play` and `Like to play` lines that has none. The second writes playbooks for the champions named. `--show` prints saved playbooks and asks Claude nothing. `--map` writes the whole augment map again, and `--force` writes the named playbooks again.

Measured with Claude Opus 5.5 at high effort: the augment map cost $4 and took 10 minutes; a playbook costs about $0.70. Research is kept in `cache/<patch>/research/` as JSON you can read and edit.

What it changed, measured on Cho'Gath with two or three answers per case, so read it as an indication. Before any augment, both plans named Stackosaurus Rex and Lich Brain as augments to look for, and one named RISE: the augments that multiply the champion's unlimited Feast stacks. Without the research neither answer named any of the three. After an augment, the build followed it: holding two augments that fire on a knock-up, both plans bought Imperial Mandate, which brings Q's cooldown to the augments' five-second limit, and without the research neither did. Those plans took 8 to 12 seconds against 9 to 18. Augment picks did not change: in 12 offers tried, the usual pick was the same card with and without the research, and single answers strayed in three offers, twice without it and once with it. With the cards in front of it, Claude already reads them well.

## Calculations

Calculations are off by default. With `ARAMCOACH_TOOLS=plan` and an API key, Claude can run arithmetic on your real stats before it answers a plan that sets the build: the plan at the start of a match, the plan after each augment, a fresh plan you ask for, and the plan after you type to the coach. Plans made because you died or an enemy bought an item get none, and every other kind of request reads exactly as before.

| Calculation | What it works out |
|---|---|
| `attack_damage` | Basic attacks on one enemy for six seconds with each candidate build: attacks a second, critical strikes, penetration and the on-hit effects of about 25 items, when the enemy dies, and what the enemies beside it take |
| `ability_damage` | Every damage, heal and shield number of your champion's kit at each build's stats, after the enemy's resistances, each cooldown at the build's ability haste, and what each added item does when an ability hits |
| `survival` | How much longer you last in a fight with each set of defensive items bought together. Offered only to champions that build defense |
| `evaluate` | A formula Claude writes, worked out on each build's stats. For a rule of the kit no model covers, such as Garen's spin count, or for what an augment adds |

Each one compares up to four builds against your stats as the game reports them, so runes, augments and stacks are in the starting point as far as they are stats. Each answer says what it measured against, what it counted and what it left out.

Measured by replaying four recorded matches (Jinx, Garen, Zilean, Cho'Gath) with the setting on, and comparing with replays of the same matches without it:

- All 20 plans that were offered calculations called one, in one step each: 23 calls, none failed, and no plan failed.
- Those plans took a median of 12 to 17 seconds, match by match, against 9 to 11 seconds for the other plans of the same matches. The step of calls itself took 2 to 6 seconds. A match has about five such plans.
- A match cost $1.25 on average against $1.03 without.
- The builds changed. Garen went to Phantom Dancer and Infinity Edge once his augments gave critical strike chance, where the replay without the calculations bought Infinity Edge and never listed Phantom Dancer. Zilean bought ability power and penetration and no Rylai's Crystal Scepter. Cho'Gath listed Unending Despair second and Kaenic Rookern fourth. Jinx was told Kraken Slayer first in that replay, when the calculation did not yet count Kraken Slayer's effect. With the effect counted, two plans made at the same moment both put Yun Tal Wildarrows first.
- The next item to buy changed 7 times in the four matches against 5 without, never with parts of the old item in the bag. In one match a plan with calculations moved Titanic Hydra ahead of Unending Despair and the next plan, made without them, moved it back.
- Augment picks matched the card really taken in 14 of 16 offers, against 15 of 16 without. The augment request itself is unchanged; it reads the plan in force, which differed.

What this does not show is whether the changed builds win more. A replay measures whether the coach is steady and what it believes. The arithmetic is right as far as its model goes, and its limits are listed under Known limits.

The definitions of the calculations travel inside the request, not in the API's `tools` field. That field is part of the cached prompt, so using it would give plans a second cached copy of the 49,000-token system prompt, about $0.25 to write each time it went cold.

## Settings

Put these in `.env` as `NAME=value` lines.

| Variable | Default | Meaning |
|---|---|---|
| `ANTHROPIC_API_KEY` | none | Your API key. When set, the API is used |
| `ARAMCOACH_MODEL` | `claude-opus-5-5` | Claude model ID |
| `ARAMCOACH_EFFORT` | `low` | Reasoning effort: `low`, `medium`, `high`, `xhigh`, `max`. Higher is slower |
| `ARAMCOACH_RESEARCH` | `0` | Prepared research, experimental. `1` uses what is saved and writes a playbook when you pick a champion that has none. `saved` uses what is saved and never pays for more. `0` uses none |
| `ARAMCOACH_RESEARCH_EFFORT` | `high` | Reasoning effort for writing research |
| `ARAMCOACH_AUGMENT_TEXT` | `1` | `0` never contacts arammayhem.com, which supplies the effect text of a few augments the wiki leaves out |
| `ARAMCOACH_PLAN_VOTES` | `1` | Experimental. `3` remakes the build from three independent plans at the start of a match and after an augment that matters |
| `ARAMCOACH_TOOLS` | `0` | Experimental. `plan` lets Claude run calculations on your real stats before a plan that sets the build. API key only. See Calculations |
| `ARAMCOACH_DEBRIEF_EFFORT` | `high` | Reasoning effort for the post-game review |
| `ARAMCOACH_ITEM_BUTTONS` | from `player.txt` | `no`: never recommend an item whose only effect is behind its button. `yes`: allow them |
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
| `deaths.py` | Gives each of your deaths a verdict from the kills around it, who was alive, and your health beforehand |
| `ocr.py`, `screen.py` | Screen capture, text recognition, augment offers and scoreboard tooltips |
| `research.py` | Research prepared ahead of a match: the augment map and a playbook per champion |
| `augtext.py` | Reads effect text from arammayhem.com for the few augments the wiki table leaves out |
| `threats.py` | Estimates what kind of damage is killing you and what each defensive item would add against it |
| `itemworth.py` | How much longer a front-line champion lasts in a fight with an item or a set of items, effects counted |
| `calc.py` | Arithmetic on your real stats: the stats a build would give, basic-attack damage with on-hit effects, every number of your kit, and formulas Claude writes |
| `tools.py` | The calculations Claude can call before a plan: what it is told about them and the text of each answer |
| `itemcheck.py` | Item rules a program decides: button-only items, and items that need an ally heal or shield |
| `postgame.py` | The post-game record, the match reduced to fights, gold lead and purchase times, and the review |
| `static_data.py` | Item, champion, ability and augment data, cached per patch |
| `server.py`, `web/index.html` | The panel |

The coach makes a plan at game start, when you die (if the plan is more than 45 seconds old or an enemy has finished an item since), and when you take an augment.

Estimated enemy stats come from base stats, level and item stat lines. They leave out champion passives, augments and item passives, so they are minimums. The fight-alone table and cost-benefit answers are estimates, not measurements.

## Files written

- `cache/<patch>/`: item, champion, augment and ability data, downloaded once per patch. `kits.json` holds every champion's ability numbers for the calculations and `item_numbers.json` the numbers inside item effects.
- `cache/champion_fit.json`: Claude's rating of every champion for you. It is written once, in about a minute, and again whenever you edit `player.txt`.
- `cache/history.json`: your champion, result and deaths in recent matches, copied from the client's match history.
- `captures/champselect/`: a few raw champion-select sessions per match, with player identities removed, kept to check the client's data format.
- `captures/<game start time>/`: raw game API payloads, screenshots taken for augment reads and scoreboard reads, the post-game record, the kill timeline and the review. In ARAM: Mayhem it also keeps a picture of the screen three seconds after each of your first eight deaths, to find out whether the game's death recap can be read. These contain other players' names. They are ignored by git; do not share them.
- `logs/coach.log`: one line per event. Read this to find out what happened in a game.
- `Config\Global\Recommended\!!!aramcoach-0.json` in the League folder: the in-game item set. It is removed when the match ends.

## Data sources

| Data | Source |
|---|---|
| Live game state | The game's Live Client Data API on port 2999 |
| Champion select, loading screen, post-game record | The League client's local API |
| Items, champion text, base stats | Riot Data Dragon |
| Attack damage growth, ability numbers by rank, the numbers inside item effects, whether a champion is melee or ranged | Meraki Analytics community dataset. Can lag a patch |
| Augment ids and names | CommunityDragon |
| Augment descriptions | League of Legends Wiki. A copy is bundled in `aramcoach/data` under CC BY-SA 3.0; see the note in that folder |
| Effect text of augments the wiki table leaves out (quests and a few others) | [arammayhem.com](https://arammayhem.com). Only the effect text is read |

From arammayhem.com the coach reads the augment list, to find each augment's page, and the pages of augments it has no text for. The text is kept in `cache/<patch>/augment_text.json`. The site's `robots.txt` allows this. A request carries only an augment name. The site's pick rates and build statistics are not read, kept or used.

## Tests

```
.venv\Scripts\python.exe tests\test_shop.py
.venv\Scripts\python.exe tests\test_deaths.py
.venv\Scripts\python.exe tests\test_champfit.py
.venv\Scripts\python.exe tests\test_itemcheck.py
.venv\Scripts\python.exe tests\test_threats.py
.venv\Scripts\python.exe tests\test_consensus.py
.venv\Scripts\python.exe tests\test_research.py
.venv\Scripts\python.exe tests\test_augtext.py
.venv\Scripts\python.exe tests\test_postgame.py
.venv\Scripts\python.exe tests\test_itemworth.py
.venv\Scripts\python.exe tests\test_calc.py
.venv\Scripts\python.exe tests\test_simulated_game.py
.venv\Scripts\python.exe tests\test_real_scoreboard.py
```

- `test_shop.py` checks the purchase arithmetic.
- `test_deaths.py` checks the death verdicts against small hand-made fights.
- `test_champfit.py` checks the champion-select ranking.
- `audit_matches.py` is not a test either. It reads the last few recorded matches for mistakes nobody has reported: augments the coach believed that the game's record does not list, plain defensive items asked of a fragile champion, plans whose stated change the coach overrode, what you typed to the coach, the damage estimate against the measured split, and every sentence of the coach's own review that blames the coach. That part is free. With `--independent` it also asks Claude without any of the coach's instructions what a strong player would object to, at about $0.10 a match. Every large mistake so far was found by the player or their friends and not by a check, which is why this exists. Its limit is stated in the file: a second opinion from the same model finds errors of fact (an item whose effect the champion cannot trigger, a false reason) and misses differences of judgment (it thought a tank item on a mage was right). Run it after a session: `.venv\Scripts\python.exe tests\audit_matches.py --last 6 --independent`.
- `replay_match.py` is not a test that passes or fails. It replays a recorded match from `captures/` through the whole coach with real Claude calls, at about the cost of that match, and prints every build the player would have seen, the build a plan asked for whenever the coach overrode it, how often the next item changed, and what the coach believed about your augments against the post-game record. Run it on a few recorded matches before switching on an experimental setting or after changing how plans are made: `.venv\Scripts\python.exe tests\replay_match.py captures\<match> --research saved --votes 3 --tools plan`. It also prints the wait for each plan and, with `--tools plan`, which calculations each plan called.
- `test_research.py` checks the prepared research on made-up answers: names the game does not have are dropped, saved research reaches plan and offer requests, a run cut short resumes, and nothing is written unless the setting allows it.
- `test_augtext.py` checks the reading of augment text against made-up pages, and that no rank or pick rate is kept. It does not use the network.
- `test_consensus.py` checks how several plans are combined into one, and that the plans it combines are asked for together without the earlier plan.
- `test_itemworth.py` checks that item text keeps its numbers and loses its markup, that each formula in the fight arithmetic still matches the text of its item (so a patch that changes an item is noticed), and the arithmetic itself on a made-up tank.
- `test_calc.py` checks the calculations: that each item formula still matches the text of its item, the stat sheet, the attack model on round numbers, the kit numbers and their units, that a formula can hold arithmetic and nothing else, the text Claude gets back, that only a plan that sets the build is offered them and every other request reads exactly as before, and the loop that runs them against a fake API.
- `plan_moment.py` is not a test either. It asks for the plan at one moment of a recorded match with and without the calculations and prints the wait, the cost, what was called and both builds, at about $0.05 to $0.10 a plan: `.venv\Scripts\python.exe tests\plan_moment.py captures\<match> 420 --runs 2 --augments "Deft,Goliath"`.
- `test_threats.py` checks the damage estimate and the arithmetic for defensive items on a made-up match, and that a plan's item order is never changed by it.
- `test_itemcheck.py` checks the item rules against the cached game data: which items are button-only, which champions heal or shield allies, and that a plan loses an item that breaks a rule.
- `test_postgame.py` checks what the review is given, on a small made-up match: fights, gold lead, purchase times and the coach's own advice.
- `test_simulated_game.py` runs a whole recorded match through the coach with a fake League client and a stub in place of Claude. It costs nothing. Run it after any change to `coach.py`, `pregame.py` or `postgame.py`.
- `test_real_scoreboard.py` checks scoreboard row detection against a real picture in `captures/`. It is skipped when you have no such recording.

## What it does not do

The coach reads the game's local APIs, the League client's local API, and the screen. It does not read or change the game's memory, inject code, or send input to the game. It shows nothing the game does not already show you.

## Known limits

- The game API does not report augments. Other players' augments are known only when you point at them, or when one replaces a summoner spell.
- The game reads the item set once, when the match loads. A later plan can name an item that is not in the set; the panel marks it, and you find it with the shop search. The set written in champion select is built wide to make this rare.
- The augment tooltip reader has been tested on a real scoreboard layout but not yet on a real tooltip.
- The champion-choice ranking reads the bench from the champion-select session. The two champion cards at the start are read from the client's "subset champion list". That source is taken from the client's own type definitions and has not yet been watched in a real champion select.
- The research is Claude's reasoning from text, not a measurement. It can be wrong where the text leaves a mechanic open, such as whether an effect counts as a hit. The research requests are told to say so and not to assume the favourable reading, a program drops any augment or item name the game does not have, and the live request is told that current effect text wins. Nothing measured yet says the research wins more matches.
- Research is written for one patch. On a new patch the files from the last one are still used, and the request says which patch they were written on. Run the research command again to redo them.
- A build never holds two items with the same Spellblade, Lifeline, Immolate, Annul, Cleave or Manaflow passive, because a player gets each of those from one item only. A program removes the second one from a plan. That is the standard game's rule. It was not confirmed for ARAM: Mayhem.
- Combining three plans steadies the core of the build and the next purchase. The last two slots can still differ from one remake to the next: in one test the fourth to sixth items always included an item that cuts healing, but which one varied.
- The damage estimate is an estimate. Against 42 recorded matches it was off by 6 points on average and by 18 at worst, and within 12 points in 37. Its constants were tuned on 34 of those matches, so expect a little worse. Asked only which kind of damage is the larger, it was right in 18 of the 42 and said "a mix" in the other 24. It cannot see who an enemy chooses to attack, and it treats every enemy with the same item gold as dealing the same amount of damage: in the match above two mages dealt twice the damage of the two attackers on equal gold.
- The coach does not predict enemy healing. From kits and items it picked the heavy healers of those matches correctly only 20 to 50% of the time, because most healing in ARAM: Mayhem comes from augments the game does not show. A plan is told only whether a teammate already holds an item that cuts healing. The post-game review compares the enemy's measured healing with the usual amount in your recorded matches.
- The calculations model part of a fight. Basic attacks are counted on one enemy who stands still for six seconds, with effects that build up starting empty. Your champion's own abilities and passives are not in the attack model, and its ability numbers are listed line by line, not added up into a fight, because how often each ability lands is not known. Enemy health and resistances are estimates from champion, level and items, so they are minimums. An augment counts only as far as the game adds it to a stat, or as far as Claude adds it by hand. Stormrazor's charged attack has no number in the data the coach holds, so it is left out and said to be. Item numbers are the standard game's. An enemy below the level a build is worked out at is taken to that level with the items they hold now, not with the items they will have by then.
- A formula for `evaluate` is written by Claude from the kit text, and it can be wrong. Asked twice about Garen's spin it wrote two different readings of the critical strike rule. Both gave the same order of builds, because an error in a formula applies to every build alike, but the size of a gain from such a formula is less sure than its direction.
- The item checks cover two kinds of mistake only. Whether a champion heals or shields allies is read from ability text, which is vague for a few champions: Hwei's shield is not detected.
- The review's fight list comes from kill times. It cannot see fights without a kill, or what any ability did.
- The item catalog covers the ARAM shop only.
- Text recognition needs the English game client.

## Disclaimer

ARAM Coach is not endorsed by Riot Games and does not reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games and all associated properties are trademarks or registered trademarks of Riot Games, Inc.
