# Turbo - desktop racing buddy (hackathon project)

A Bonzi-Buddy-style desktop pet for Windows: a chibi racing driver (black/orange helmet
and one-piece race suit) that lives on top of the desktop.

## Files
- `desktop_pet.py` - the whole app (single file, Python 3 + tkinter + Pillow)
- `dev_run.py` / `dev_run.bat` - live reload: restarts the pet whenever desktop_pet.py is saved
- `run_pet.bat` - run without a console (pythonw)
- `turbo_stats.json` - saved records (best reaction time, best lap)

## How it works
- Borderless, always-on-top tkinter window; `#ff00fe` is the transparent colour key.
- The character is drawn with Pillow at 3x supersampling (`Renderer`, `Painter` classes),
  cached as layers (body, helmet, right arm, car) and composited into frames.
  Edges are flattened against the dark outline colour and hard-cut to the colour key,
  so no pink fringe. Common poses are pre-rendered at startup (`warm_list`).
- Speech bubble, start-light gantry, lap board, smoke and Zzz are plain tkinter canvas items.
- `Pet` holds the state machine: idle / walk / drive / sleep / drag / fall (with throw physics).
- Runs at ~60 fps (`FPS_MS` 16, `timeBeginPeriod(1)` for a fine Windows timer). Movement is
  time-based: `self.dt` is measured in 30 fps ticks, so speeds keep their tuned values.
  `Pet.ease()` ramps walk / drive speed up and brakes near the target. Pre-rendering
  (`warm`) pauses while Turbo moves so it never stutters.

## Features
Poke, drag and throw, team-radio chatter, jokes, racing facts, timer, 45-minute pit-stop
reminders, start-lights reaction test, stopwatch with laps, driving the #26 car,
chequered-flag celebrations, sound effects (engine rev/loop/wind-down while driving, a beep per
start light; toggle in the menu, saved as `sound` in turbo_stats.json).

## Menu
`RaceMenu` is a custom canvas-drawn popup (not tk.Menu) in Turbo's colours. Items are tuples:
`("cmd", label, fn)`, `("check", label, BooleanVar, fn)`, `("sub", label, items)`, `("sep",)`.
Submenus open in place; clicking the header goes back. Closes on focus loss, Esc or clicking the pet.
`("radio", label, StringVar, value, fn, (accent, suit))` items keep the menu open (used for liveries).

## Liveries
`LIVERIES` maps a name to (accent, accent shade, suit, helmet) hex colours. `apply_livery()`
rewrites the palette globals (`ORANGE`, `C_ORANGE`, `C_ORANGE_D`, `C_SUIT`, `C_HELM`);
`Pet.set_livery` then builds a fresh `Renderer` so the cached layers are repainted.
The choice is saved as `livery` in turbo_stats.json.
`Garage` (menu: Livery colours > Livery garage...) is a canvas-drawn editor in the menu style:
add / duplicate / rename / delete / reset liveries and pick colours (tk colorchooser); the
selected livery is applied to Turbo live. Edited schemes are saved as `liveries` in
turbo_stats.json (falls back to `DEFAULT_LIVERIES` if missing or invalid).
Speech bubbles use the menu colours too (`MENU_BG`, accent outline, `MENU_TEXT`).

## Live data
`fetch()` (urllib, cached) + small functions returning board dicts `{"title", "lines", "key", ...}`:
F1 via Jolpica (api.jolpi.ca, Ergast successor), MotoGP via api.motogp.pulselive.com,
F2 / F3 standings parsed from fiaformula2.com / fiaformula3.com `/Standings/Driver|Team` tables
(`feeder_standings`), WEC standings from the fiawec.com season page (`wec_standings`),
Formula Student via fs-world.org JSON (`/ranking/<cls>/<event>/data`; licence requires the
source note shown on the board, non-commercial), jokes via icanhazdadjoke, F1 history facts
from Jolpica. `Pet.fetch_bg` runs them on a thread and hands results back through `self.jobs`.
Followed leagues are checked every 30 min; `stats["seen"]` stores the last result key per league.
The window is 440 px tall; the see-through space above Turbo holds bubbles and results boards.
Boards show `BOARD_ROWS` (10) rows at a time; longer lists (full F1 / MotoGP standings and race
results) flip pages every 7 s and scroll with the mouse wheel over Turbo.

## Sound
`Sound` synthesises WAVs at startup (stdlib `wave`, into `%TEMP%\turbo_sounds`) and plays them
with `winsound` async. winsound plays one sound at a time; missing winsound = silent no-op.
Clicking Turbo (or Racing > Famous team radio) says a `MEME_RADIO` line out loud: `radio_voice()`
renders it with Piper (optional, `piper/piper/piper.exe` + first `piper/*.onnx` voice, currently
en_GB-alan-medium from github.com/rhasspy/piper + huggingface rhasspy/piper-voices), falling back to
Windows System.Speech via PowerShell (only Windows voice here: Zira, en-US),
pitches it down and applies a band-pass / drive / squelch radio effect, cached in
`%TEMP%	urbo_soundsadio`. All lines are pre-rendered in the background at startup.
With "Voice (read bubbles aloud)" on (stats `voice`), `say()` speaks every bubble the same way,
except while driving so the engine loop is not cut off.

## Conventions
- Keep it one file with no dependencies beyond Pillow.
- Avoid non-BMP characters (emoji) in tkinter text; Tk on Windows can choke on them.
- The user keeps `dev_run.bat` running, so every save reloads the pet live.

## Formula Student results
`FSResults` panel (Live results > Formula Student > Competition results...) parses fs-world.org
competition/event pages (`fs_competitions`, `fs_competition_events`, `fs_event_results` read the
result tooltips). Pick competition, class, year, discipline; "Follow this" saves `fs_follow`
(cid, cls, disc, name) which the Formula Student league follow then uses. `Panel` is the shared
base class for the garage and this window.

## Telemetry
`Telemetry` panel (menu: Telemetry console) samples once a second while open: CPU from
`time.process_time()` (shown as % of all cores and of one core), RAM from `process_memory()`
(psapi GetProcessMemoryInfo via ctypes: working set + private bytes), FPS from `Pet.frames`,
smoothed frame time `Pet.frame_ms`, threads, cached frames, uptime; 60 s graphs for CPU and RAM.
