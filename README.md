# Turbo – desktop racing buddy

Turbo is a Bonzi-Buddy-style desktop pet for Windows: a chibi racing driver in a helmet and
one-piece race suit who lives on top of your desktop. He walks around, drives his #26 car,
chats over "team radio", tells jokes, runs reaction tests and stopwatches, and shows live results
from F1, F2, F3, MotoGP, WEC and Formula Student.

Everything is in one Python file (`desktop_pet.py`, standard library + Pillow).

---

## Contents

1. [Quick start](#quick-start)
2. [Files](#files)
3. [Controls](#controls)
4. [Behaviour](#behaviour)
5. [The menu](#the-menu)
6. [Racing features](#racing-features)
7. [Live results](#live-results)
8. [Formula Student results window](#formula-student-results-window)
9. [Following leagues](#following-leagues)
10. [Liveries and the livery garage](#liveries-and-the-livery-garage)
11. [Sound and voice](#sound-and-voice)
12. [Telemetry console](#telemetry-console)
13. [Saved data](#saved-data)
14. [How it works](#how-it-works)
15. [Data sources and licences](#data-sources-and-licences)
16. [Customising](#customising)
17. [Troubleshooting](#troubleshooting)

---

## Quick start

Requirements: Windows 10/11 and Python 3 with tkinter (the normal python.org install).

| Start with | What it does |
|---|---|
| `run_pet.bat` | Installs Pillow if needed and starts Turbo without a console window (`pythonw`). |
| `dev_run.bat` | Live reload for development: starts Turbo and restarts him whenever `desktop_pet.py` is saved. Errors show in the console. |
| `python desktop_pet.py` | Plain start from a terminal. |

If Pillow is missing, `desktop_pet.py` installs it into the Python that is running it and carries on.

To quit: right-click Turbo → **Goodbye**. With `dev_run.bat`, choosing Goodbye or pressing Ctrl+C in the
console stops everything.

---

## Files

| File / folder | Purpose |
|---|---|
| `desktop_pet.py` | The whole app: rendering, behaviour, menus, windows, sound, voice, live data. |
| `dev_run.py`, `dev_run.bat` | Live-reload runner (restarts on save). |
| `run_pet.bat` | Start without a console. |
| `turbo_stats.json` | Your saved records and settings (created automatically, see [Saved data](#saved-data)). |
| `piper/` | Optional offline neural voice ([Piper](https://github.com/rhasspy/piper)) and the `en_GB-alan-medium` voice model, about 98 MB. Turbo falls back to the Windows voice without it. |
| `CLAUDE.md` | Short technical notes for developers / AI assistants. |
| `README.md` | This file. |

Generated at runtime (safe to delete): `%TEMP%\turbo_sounds\` (sound effects) and
`%TEMP%\turbo_sounds\radio\` (cached voice lines).

---

## Controls

| Action | Result |
|---|---|
| **Left-click** | Pokes Turbo: he hops, says a famous F1 radio line and plays it out loud. Five quick pokes make him angry. |
| **Left-click during the start lights** | Your reaction (see [reaction test](#start-lights-reaction-test)). |
| **Left-click while the stopwatch runs** | Sets a lap. |
| **Left-click on a results board** | Dismisses the board. |
| **Drag and release** | Picks Turbo up and throws him. He bounces off the screen edges and lands with a thud. |
| **Mouse wheel over Turbo** | Scrolls a long results board. |
| **Right-click** | Opens the menu. |
| **Esc** | Closes the menu or any open window. |

The see-through parts of Turbo's window let clicks pass through to the desktop.

---

## Behaviour

Turbo runs a small state machine: **idle, walk, drive, sleep, drag, fall**.

- **Idle:** stands and bobs, looks towards your mouse pointer, blinks. Sometimes gives a thumbs-up.
- **Walk:** strolls to a random spot, easing in and out.
- **Drive:** jumps into the #26 car and drives to the other side of the screen, with speed lines,
  exhaust smoke, engine sound and gentle acceleration and braking. Sometimes celebrates on arrival
  ("P1! Get in there!").
- **Sleep:** after three minutes without interaction he may take a nap (Zzz). Poke him to wake him up.
- **Drag / fall:** real throw physics with gravity, bounces, squash-and-stretch and landing reactions
  ("Oof! Big crash.").
- **Expressions:** open, blink, happy, surprised (when flying), angry (red helmet stripe, shaking) and sleeping.
- **Team radio chatter:** every 45–150 seconds while idle or walking he says something on his own,
  mixing normal radio lines and famous F1 meme lines.
- **Waiting while you read:** when you ask for something from the menu (a joke, fact, results...),
  Turbo stops walking or driving and stays put until the answer has been shown.
- **Greeting:** says good morning / afternoon / evening at start-up.

---

## The menu

The right-click menu is drawn in Turbo's colours: a dark body, a border in the accent colour, a chequered
flag in the header. Submenus open inside the same menu; click the header (◂) to go back.

```
TURBO #26
├── Racing ▸
│   ├── Start lights reaction test
│   ├── Stopwatch: start / lap
│   ├── Stopwatch: stop
│   ├── Go for a drive
│   ├── Racing fact
│   ├── Famous team radio
│   └── My records
├── Live results ▸
│   ├── Formula 1 ▸        Last race · Drivers' championship · Teams' championship · Next race
│   ├── Formula 2 ▸        Drivers' championship · Teams' championship
│   ├── Formula 3 ▸        Drivers' championship · Teams' championship
│   ├── MotoGP ▸           Last race · Riders' championship · Teams' championship
│   ├── WEC ▸              Hypercar Manufacturers · Hypercar Drivers · LMGT3 Teams · LMGT3 Drivers
│   ├── Formula Student ▸  World ranking EV / CV / Driverless · Competition results... ·
│   │                      My followed competition · My team's ranking · Set my team...
│   ├── Latest from my leagues
│   ├── Follow F1  [ ]
│   ├── Follow MotoGP  [ ]
│   └── Follow Formula Student  [ ]
├── Tell me a joke
├── What time is it?
├── Telemetry console
├── Set a timer...
├── Pit stop reminders (45 min)  [ ]
├── Sound effects  [x]
├── Voice (read bubbles aloud)  [x]
├── Livery colours ▸   (all liveries, then Livery garage...)
├── Jump!
├── Take a nap / wake up
└── Goodbye
```

---

## Racing features

### Start lights reaction test
Five red lights come on one by one, each with an F1-style start beep. After a random 0.2–2.5 s
hold, the lights go out, silently like the real thing. Click Turbo as fast as you can.

| Reaction time | Verdict |
|---|---|
| under 0.200 s | "Superhuman! Are you a bot?" |
| under 0.250 s | "F1 driver pace!" |
| under 0.350 s | "Solid start." |
| under 0.500 s | "Bit sleepy off the line..." |
| slower | "Were you checking your phone?" |

Clicking before the lights go out is a **jump start** (buzzer and a drive-through penalty). A new best time
is saved and celebrated with the chequered flag.

### Stopwatch
**Stopwatch: start / lap** starts it; after that, every click on Turbo sets a lap. A timing board above
his head shows the running lap. The fastest lap of the session is "purple"; a new all-time best lap is saved.
**Stopwatch: stop** shows the session summary.

### Racing facts and jokes
- **Racing fact:** half from the built-in list, half generated from 75 years of real F1 results
  (e.g. "Back in 1978, Mario Andretti won the Dutch Grand Prix for Team Lotus, starting from P1."
  or a past world champion).
- **Tell me a joke:** half from the built-in list, half online from icanhazdadjoke (car, race, engine,
  tyre... themed searches).
- Offline, both fall back to the built-in lists.

### Famous team radio
32 famous F1 radio and meme lines, e.g. "Give me the gloves!", "Must be the water.", "Bwoah.",
"GP2 engine! GP2!", "Multi 21, Seb.", "Valtteri, it's James.", "Is that Glock?!", "Hammer time!".
They play when you click Turbo, from **Racing → Famous team radio**, and in his random chatter.

### Timer and pit-stop reminders
- **Set a timer...:** enter minutes and an optional message, e.g. `10 tea is ready`. When it runs out
  Turbo waves the chequered flag and jumps.
- **Pit stop reminders (45 min):** every 45 minutes Turbo calls you into the pits to stretch, drink water or rest your eyes.

---

## Live results

Results appear on a **timing-screen board** above Turbo's head: title, rows in monospace and small print.

- Long lists (full standings, full race results) show **10 rows per page**, with a counter such as `1-10/23`.
  The pages flip every 7 seconds, and you can scroll with the mouse wheel over Turbo.
- The board stays until all pages have been shown (15 s for a single page). Click to dismiss it.
- Your Formula Student team is highlighted in the accent colour.
- While data loads Turbo says "Checking the timing screens..."; when offline, "No signal from the pit wall."

| Series | Available | Source |
|---|---|---|
| **Formula 1** | Last race (all finishers), drivers' and teams' championships, next race (with your local start time and a countdown) | Jolpica API |
| **Formula 2** | Drivers' and teams' championships | fiaformula2.com standings pages |
| **Formula 3** | Drivers' and teams' championships | fiaformula3.com standings pages |
| **MotoGP** | Last race, riders' championship, teams' championship (the sum of each team's riders' points) | MotoGP results API |
| **WEC** | Hypercar manufacturers, Hypercar drivers (car number + crew), LMGT3 teams, LMGT3 drivers | fiawec.com season page |
| **Formula Student** | World ranking (EV / CV / Driverless), your team's ranking, any competition's results by discipline | fs-world.org |

Results are cached for a few minutes, so asking twice doesn't hit the servers twice.

---

## Formula Student results window

**Live results → Formula Student → Competition results...** opens a window in the menu's style:

1. **Competition list** (left, scroll with the mouse wheel): all 27 competitions on fs-world.org,
   e.g. Formula Student Germany, FS Austria, FSAE Italy, Formula SAE Michigan, FS Czech Republic...
2. **Class:** EV, CV or Driverless, whichever the competition has.
3. **Year:** the last four editions of that competition.
4. **Discipline:** Overall, Business plan, Cost, Design, Skidpad, Acceleration, Autocross, Endurance,
   Efficiency (Driverless: DV Skidpad, DV Acceleration, ...).
5. **Results table:** positions, teams and points; your team is highlighted even outside the top rows.
6. **Show on Turbo:** puts the results on his board.
7. **Follow this:** makes this competition, class and discipline your followed Formula Student results
   (see below). Click again (**Following ★**) to unfollow.

**Set my team...** stores your team or university (part of the name is enough, e.g. `Aalto`).
**My team's ranking** finds your team in the world ranking, whichever class it races in.

---

## Following leagues

Tick **Follow F1**, **Follow MotoGP** and/or **Follow Formula Student**:

- **Latest from my leagues** shows the latest result of every followed league, one board after another.
- Every **30 minutes** (and 20 s after start-up) Turbo checks the followed leagues. When a result is
  new since the last check he wakes up, says "New results just in!", celebrates and shows the boards.
- Formula Student uses the competition you chose with **Follow this**. Without one it follows the world
  ranking, for your team's class if you set a team.
- F2, F3 and WEC can be viewed but not followed yet.

---

## Liveries and the livery garage

**Livery colours** lists all colour schemes; picking one recolours Turbo, his car, the menu, the
speech bubbles and the results boards at once. The menu stays open so you can try them out live.

Built-in liveries: Turbo orange (default), Racing red, Electric blue, Petrol teal, Lime green,
Hot pink, Gold, Silver arrow.

**Livery garage...** is the editor:

- **Left:** the livery list; click one to select it (Turbo wears it immediately).
- **Right:** the four colours of the selected livery (Accent, Accent shade, Suit, Helmet), with their codes.
  Click one to pick a new colour. Changing the accent also sets a matching darker shade.
- **+ New** (copy of the current one), **Delete**, **Rename**, **Duplicate**, **Reset all** (asks first;
  removes your own liveries and restores the originals).
- Drag the header to move the window; × or Esc closes it.

Your liveries and the current choice are saved in `turbo_stats.json`.

---

## Sound and voice

All sound effects are **generated by code at start-up** (no audio files) and played with
Windows' `winsound`. Windows plays one sound at a time, so a new sound replaces the current one.

| Sound | When |
|---|---|
| Engine rev → engine loop → wind-down | Driving |
| Start beep (450 Hz, F1 style) | Each start light |
| Buzzer | Jump start |
| Jump "boing" | Jump! (menu, timers, pit reminders) |
| Thud | Landing from a real fall |
| Blip | Poking Turbo |
| Whoosh | Throwing him hard |
| Chime | Celebrations: records, purple laps, new results |

### Voice
- Turbo reads his bubbles aloud as **team radio**: the text is spoken by a voice engine, then filtered
  (narrow band, a little distortion and hiss) with a beep and static at the start.
- **Voice engine:** Piper with the British male voice *Alan* when the `piper` folder is present
  (offline, about 0.1–0.6 s per line). Without it, the built-in Windows voice (lowered in pitch).
- Voice lines are cached, and all famous radio lines are pre-rendered in the background shortly after start-up,
  so clicks speak instantly.
- He stays quiet while driving so the engine sound isn't cut off.

### Switches
- **Sound effects** off: everything is silent, voice included.
- **Voice (read bubbles aloud)** off: bubbles stay silent, but clicking Turbo still plays the famous radio lines.

---

## Telemetry console

**Telemetry console** is a terminal-style window showing what Turbo himself uses, updated every second:

| Row | Meaning |
|---|---|
| CPU | Share of the whole processor (like Task Manager) and of one core |
| RAM | Working set and private memory of the Turbo process |
| FPS | Frames drawn per second and the average time per frame |
| THREADS | Running Python threads |
| cached | Pre-rendered frames in memory |
| UPTIME / state | How long Turbo has run and what he is doing |

With 60-second graphs for CPU and RAM. Typical numbers: about 0.5–1 % CPU (about 9 % of one core),
around 80 MB of RAM, 60 fps with frames taking under 2 ms. Measuring stops when the window is closed.

---

## Saved data

`turbo_stats.json` (next to `desktop_pet.py`) holds:

| Key | Content |
|---|---|
| `best_reaction` | Best start-lights reaction time (s) |
| `best_lap` | Best stopwatch lap (s) |
| `sound`, `voice` | Sound effects and voice switches |
| `livery`, `liveries` | Current livery and all colour schemes |
| `fs_team` | Your Formula Student team |
| `fs_follow` | Followed FS competition, class and discipline |
| `follow` | Followed leagues |
| `seen` | Last result seen per followed league (for "new results" alerts) |

Delete the file to reset everything.

---

## How it works

- **Window:** a borderless, always-on-top tkinter window 280 × 440 px. The colour `#ff00fe` is made
  transparent by Windows, so everything except Turbo, his bubbles and boards is see-through and click-through.
- **Rendering:** Turbo is drawn with Pillow at 3× resolution and scaled down for smooth edges (`Renderer`,
  `Painter`). Body, helmet, arm and car are cached as layers and combined into frames, which are cached too.
  Edges are flattened against the outline colour so no pink fringe appears.
- **Pre-rendering:** common poses are drawn in small chunks after start-up (`warm_list`); this pauses while
  Turbo moves so it never stutters.
- **Frame rate:** about 60 fps. Windows is asked for a 1 ms timer (`timeBeginPeriod`) so frames come evenly.
  Movement is time-based, so speeds stay the same even if a frame is late; walking and driving ease in and out.
- **Menus and windows:** `RaceMenu` (the popup menu) and `Panel` (base for the livery garage, the Formula Student
  window and the telemetry console) are drawn on canvases in the livery colours.
- **Live data:** fetched with `urllib` on background threads (`Pet.fetch_bg`), results handed back to the
  Tk thread through a queue. Cached with a time limit.
- **Sound:** WAVs are synthesised with the standard `wave` module into `%TEMP%\turbo_sounds`.
- **Voice:** Piper (`piper/piper/piper.exe` + first `piper/*.onnx` model) or Windows `System.Speech`
  via PowerShell, post-processed in Python into a radio sound.
- **Text:** emoji and other non-BMP characters are stripped from online text, as Tk on Windows can't draw them.

---

## Data sources and licences

| Data | Source | Notes |
|---|---|---|
| F1 results, standings, history | [Jolpica F1 API](https://api.jolpi.ca) (Ergast successor) | Free, public |
| MotoGP | Results API behind motogp.com (`api.motogp.pulselive.com`) | Undocumented; may change |
| F2 / F3 | [fiaformula2.com](https://www.fiaformula2.com) / [fiaformula3.com](https://www.fiaformula3.com) standings pages | Page parsing; breaks if the sites are redesigned |
| WEC | [fiawec.com](https://www.fiawec.com) season page | Page parsing; breaks if the site is redesigned |
| Formula Student | [FS World Ranking](https://www.fs-world.org) | **FS-World Data License v1.0**: non-commercial use only, source note required (shown on every FS board) |
| Jokes | [icanhazdadjoke](https://icanhazdadjoke.com) | Free, public |
| Voice | [Piper](https://github.com/rhasspy/piper) + [piper-voices](https://huggingface.co/rhasspy/piper-voices) (`en_GB-alan-medium`) | Open source, runs offline |

Turbo is a personal / hobby project. Don't use the Formula Student data commercially.

---

## Customising

Everything is plain Python constants and lists in `desktop_pet.py`:

| What | Where |
|---|---|
| Speech lines | `RADIO`, `MEME_RADIO`, `POKE_LINES`, `ANGRY_LINES`, `OUCH_LINES`, `THROW_LINES`, `DRIVE_LINES` |
| Jokes and facts | `JOKES`, `FACTS` |
| Speeds and physics | `WALK_SPEED`, `DRIVE_SPEED`, `GRAVITY` |
| Frame rate | `FPS_MS` |
| Default liveries | `LIVERIES` (name: accent, accent shade, suit, helmet) |
| Engine pitch | `ENGINE_HZ` |
| Start-light beep | `_start_beep()` (`freq`, `dur`) |
| Board rows per page | `BOARD_ROWS` |
| Voice | Replace the `.onnx` + `.onnx.json` in `piper/` with any voice from piper-voices |

Rules of thumb: keep it one file, no dependencies beyond Pillow, and no emoji in tkinter text.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Turbo doesn't start | Run `dev_run.bat` to see errors in the console. Check that Python has tkinter. |
| "Pillow not found" | Turbo installs it automatically; if that fails, run `python -m pip install pillow`. |
| No sound | Check **Sound effects** in the menu and your Windows volume. Sound is Windows-only. |
| Voice sounds robotic / female | The `piper` folder is missing, so the Windows voice is used. Restore `piper/` or add a male Windows voice in Settings → Time & language → Speech. |
| "No signal from the pit wall" | No internet, or the data source is down. |
| A series stops working | The site may have changed its page layout; the parser for that series needs updating. |
| Reset everything | Close Turbo and delete `turbo_stats.json` (and optionally `%TEMP%\turbo_sounds`). |
