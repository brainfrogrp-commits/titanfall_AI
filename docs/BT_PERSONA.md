# BT-7274 persona and spoiler gating

All of this lives in `app/bt_voice/lore.py`. Edit it there.

## Voice and humor (version 2)
Research on BT's in-game voice (search summaries of wikis and fan sites; I could not open the full script)
shows that he is written as a very literal machine who is aware of sarcasm but does not produce it, and
that players still hear him as sarcastic: he states true things flatly, and they land as jokes and insults.
That is the voice the prompt now imitates, instead of a gentle, polite one:

- deadpan understatement, literalism, clinical "findings" about Cooper's recklessness, absurd precision;
- "I detect sarcasm" / "Noted" when Cooper jokes at him;
- running gags that arrive in the right mission (the manipulator arm and "shortcuts", the underwear remark,
  the "fifty percent in love" calculation, the chassis that does not fit through doors);
- rare, flat sincerity, which is what makes the serious moments work.

**Humor dial** (settings page, Brain section): *Faithful* (a dry touch), *Sharper* (default, a jab in about half
of his replies), *Maximum* (nearly every reply has a barb). The extra-notes box still works on top.

The example lines in the prompt are original, written for tone. Nothing is copied from the game's script.

## How the gate works
BT's system prompt is built per mission from three pieces:
1. **Core persona** (always): voice, manner, reply rules. Contains no mission plot.
2. **Mission knowledge, cumulative**: blocks for missions 1..N only. Plot from later missions is
   never in the prompt, so BT cannot leak it. This is stronger than telling the model "don't spoil".
3. **Live game data**: whatever the game mod sends (map, health, events).

`app/tests/test_lore.py` enforces it. Each mission lists `introduces` terms (names or ideas that first
appear there); the test fails if any appear in an earlier mission's prompt. It already caught one real
leak while this was built. Run it after every edit to `lore.py`:

    cd app && python -m unittest discover -s tests

## Which mission is active
- **Auto**: the game mod sends `data.map` (e.g. `sp_beacon`); the app maps it to a mission.
  Unknown maps (menus, the VR memory room) keep the last known mission.
- **Manual**: pick a mission on the settings page. Use this until the game mod is sending events.

| # | Mission | Maps | Stage of BT's attitude |
|---|---|---|---|
| 1 | The Pilot's Gauntlet | sp_training | standby, not yet linked |
| 2 | BT-7274 | sp_crashsite | formal, duty-bound, assessing Cooper |
| 3 | Blood and Rust | sp_sewers1 | cautious cooperation, first dry remarks |
| 4 | Into the Abyss | sp_boomtown_start / sp_boomtown / sp_boomtown_end | trust forming |
| 5 | Effect and Cause | sp_hub_timeshift / sp_timeshift_spoke02 | analytical, a team |
| 6 | The Beacon | sp_beacon / sp_beacon_spoke0 | protective, loyal, most natural humor |
| 7 | Trial by Fire | sp_tday | confident, warmest banter |
| 8 | The Ark | sp_s2s | grim, focused |
| 9 | The Fold Weapon | sp_skyway_v1 | resolved, quiet, sincere |

## Unprompted comments
For game events BT may answer `SKIP` and stay silent. The rules favor silence: no narrating routine
combat, speak only for arrivals, objective changes, serious damage, dangerous enemies and real feats.

## Sources and what is uncertain
I could not open the wikis (Fandom and Wikipedia are blocked from the build environment). The
content comes from web search summaries of those wikis and walkthroughs, the VR mod's own files
(its list of the 13 single-player maps and its named BT story moments), and general knowledge of the
campaign. **Please check these against your own playthrough:**
- **Map to mission.** Search results disagreed on `sp_tday`, `sp_s2s` and `sp_skyway_v1`. I used the
  mod's chapter-ordered map list (tday = Trial by Fire, s2s = The Ark, skyway = The Fold Weapon).
- **Boss details.** Kane (Blood and Rust), Ash (Into the Abyss), Richter (The Beacon), Viper (The Ark),
  Slone and Blisk (The Fold Weapon). Titan classes given for them are from walkthrough summaries.
- **Exact timing inside a mission**, e.g. when Anderson is found dead (I placed it in The Beacon),
  when Briggs first appears, and which loadouts are unlocked where.
- **Mission 1.** BT is deliberately in standby there; change the `stage` text if you want otherwise.
- **The ending is deliberately absent.** BT's final sacrifice is not in any prompt, so he cannot
  foreshadow it. Add an epilogue block yourself if you want him to talk about it afterward.
- The style examples are original lines written for tone, not quotes from the game.
- Which mission each running gag belongs to comes from search summaries, so check them against your playthrough.
- **Not yet done:** a line-by-line pass over BT's actual in-game dialogue. The script sites were blocked from the
  build environment. See the end of this file for how to supply it.

## Supplying BT's real lines
For a proper line-by-line pass, put the game's subtitle text or a dialogue transcript somewhere private that I can
read, **not in this public repository** (the game's script is copyrighted). A Google Drive document or text file shared
with the account used in this session works. What helps most: BT's lines in order with the mission each is from,
and what Cooper said just before them.
