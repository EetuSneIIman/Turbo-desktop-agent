"""
Turbo - a tiny racing buddy for your desktop.

Run:  python desktop_pet.py        (or dev_run.bat for live reload while coding)

Controls
  Left-click          poke Turbo  (or set a lap when the stopwatch runs,
                                   or react when the start lights go out)
  Drag & release      pick Turbo up and throw it
  Right-click         menu: reaction test, stopwatch, drive, jokes, live results, timers, quit

Python 3 + Pillow (python -m pip install pillow). Made for Windows.
"""

import array
import html
import json
import math
import os
import queue
import random
import re
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import urllib.parse
import urllib.request
import wave
import zlib
from collections import OrderedDict
from tkinter import simpledialog

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageTk
except ImportError:
    # install Pillow into the exact Python that is running Turbo, then retry
    import importlib
    import site
    import subprocess
    print(f"Pillow not found for {sys.executable} - installing it now...", flush=True)
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    cmd = [sys.executable, "-m", "pip", "install", "pillow"] + ([] if in_venv else ["--user"])
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("\nAutomatic install failed (see pip output above). Try manually:\n"
              f'  "{sys.executable}" -m pip install pillow')
        sys.exit(1)
    user_site = site.getusersitepackages()
    if user_site not in sys.path:
        sys.path.append(user_site)
    importlib.invalidate_caches()
    from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageTk

# ---------------------------------------------------------------- settings
NAME = "Turbo"
TRANSPARENT = "#ff00fe"          # colour key that Windows makes see-through
W, H = 280, 440                  # tall window: the see-through space above is for bubbles / boards
BOARD_ROWS = 10                  # rows per page on the results board; longer lists page through
CEILING = H - 225                # how far the window may poke above the screen top
CX = 140                         # pet centre x inside the window
FOOT = H - 10                    # ground line inside the window
FPS_MS = 16                      # ~60 fps; movement is time-based, tuned in 30 fps "ticks"
TICK = 1 / 30
GRAVITY = 1.2
WALK_SPEED = 2.0
DRIVE_SPEED = 7.0
FONT = ("Segoe UI", 10)
STATS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "turbo_stats.json")

BLACK = "#1c1c21"
LINE = "#050505"
ORANGE = "#ff7a1a"
VISOR = "#0b0d10"
WHITE = "#f5f5f5"
ANGRY_ORANGE = "#ff3030"

JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "Why did the race car go to therapy? Too many issues with its brakes.",
    "What do you call a sleeping race car? A NAP-scar.",
    "Why can't bicycles win races? They're two-tired.",
    "My engineer said the car was balanced. It understeers AND oversteers.",
    "I told my computer I needed a break. It said: 'No problem, I'll go to sleep.'",
    "What's a racer's favourite meal? Fast food.",
    "There are 10 kinds of people: those who get binary and those who don't.",
]

FACTS = [
    "F1 cars can pull over 5 g in fast corners.",
    "A modern F1 pit stop can take under 2 seconds.",
    "The first F1 World Championship race was at Silverstone in 1950.",
    "Formula Student grew out of Formula SAE, started in the US in 1981.",
    "Drivers can lose 2-3 kg of body weight in a hot race.",
    "The Nurburgring Nordschleife is about 20.8 km long.",
    "Le Mans winners drive over 5000 km in 24 hours.",
    "F1 brake discs can run at over 1000 degrees C.",
    "Finland has three F1 World Champions: Keke Rosberg, Mika Hakkinen and Kimi Raikkonen.",
    "Monaco's hairpin is taken at around 50 km/h - the slowest corner in F1.",
]

RADIO = [
    "Box box! ...just kidding.", "Tyres feel good, pushing now.", "Copy that.",
    "Is that rain I see?", "Leave me alone, I know what I'm doing!",
    "Gap to the leader? Don't tell me.", "Purple sector!", "We are checking...",
    "Plan B. Plan B!", "Smooth is fast.", "Keep the tyres in the window.",
    "Small steps, big laps.", "Build, tune, race, repeat.", "Right-click me for a reaction test!",
]

# famous team radio and F1 meme lines
MEME_RADIO = [
    "Give me the gloves!", "Must be the water.", "Bwoah.", "GP2 engine! GP2! Aaargh!",
    "Multi 21, Seb. Multi 21.", "Valtteri, it's James.", "To whom it may concern...",
    "Get in there, Lewis!", "Bono, my tyres are gone!", "No Mikey, no! That was so not right!",
    "Smooth operator.", "I am stupid. I am stupid.", "Fernando is faster than you.",
    "Hammer time!", "Checo is a legend.", "Is that Glock?!", "Karma.",
    "No drink the whole race...", "Box box, box box.", "Stay out, stay out!",
    "Push push push!", "Understood. Understood.", "What are we doing here?!",
    "This is a joke! This is a JOKE!", "Kimi, are you there? ...Bwoah.",
    "We are checking... still checking.", "Plan F? What is plan F?!",
    "It's hammer time, let's go!", "Mamma mia!", "Simply lovely.",
    "Copy, we'll look into it after the race.", "Why are you so slow?! Oh wait, that's me.",
]

POKE_LINES = ["Hey!", "Hehe!", "Yes, engineer?", "Boop!", "Radio check: loud and clear.", "I'm focusing here!"]
ANGRY_LINES = ["STOP POKING ME!", "That's a penalty!", "I'm not a button!!", "Stewards, did you see that?!"]
OUCH_LINES = ["Ouch!", "Oof! Big crash.", "Good thing I wear a helmet.", "Red flag! Red flag!", "Is the car OK?"]
THROW_LINES = ["Wheee!", "Aaaah!", "Put me down!", "Is this a new corner?"]
DRIVE_LINES = ["Vroom!", "Lights out and away we go!", "Pushing now!", "Full send!"]


def work_area(root):
    """Screen area excluding the taskbar (left, top, right, bottom)."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            rect = wintypes.RECT()
            ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
            return rect.left, rect.top, rect.right, rect.bottom
        except Exception:
            pass
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight() - 40


def round_rect(canvas, x1, y1, x2, y2, r, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


def fmt_time(sec):
    m, s = divmod(sec, 60)
    return f"{int(m)}:{s:06.3f}"


def load_stats():
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_stats(stats):
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)
    except OSError:
        pass


# ====================================================================== sound
# Sound effects are synthesised at startup into small WAV files in the temp dir
# and played asynchronously with winsound (Windows only; silently off elsewhere).
# winsound plays one sound at a time, so a new sound replaces the current one.

try:
    import winsound
except ImportError:
    winsound = None

RATE = 22050
ENGINE_HZ = 150                  # cruising pitch; the loop holds a whole number of cycles


def _engine_wave(freqs, amp=0.55, rumble=25):
    """Engine-ish tone: sawtooth-ish harmonics, firing rumble, a little grit."""
    out, ph = [], 0.0
    rng = random.Random(26)
    n = len(freqs)
    for i, f in enumerate(freqs):
        ph += f / RATE
        a = ph * 2 * math.pi
        s = sum(math.sin(a * k) / k for k in range(1, 7))
        s *= 0.75 + 0.25 * math.sin(2 * math.pi * rumble * i / RATE)
        s += rng.uniform(-0.15, 0.15)
        out.append(math.tanh(1.6 * s) * amp)
    return out, n


def _beep(freq=880, dur=0.22, amp=0.45):
    n = int(RATE * dur)
    out = []
    for i in range(n):
        env = min(1.0, i / 200, (n - i) / 600)
        s = math.sin(2 * math.pi * freq * i / RATE)
        out.append(max(-1.0, min(1.0, 1.4 * s)) * amp * env)   # slightly squared-off
    return out


def _tone(f0, f1, dur, amp=0.4, square=False, noise=0.0, decay=3.0, seed=1):
    """Pitch glide from f0 to f1 with an exponential fade; optional squareness and noise."""
    rng = random.Random(seed)
    n, ph, out = int(RATE * dur), 0.0, []
    for i in range(n):
        t = i / n
        ph += (f0 + (f1 - f0) * t) / RATE
        s = math.sin(2 * math.pi * ph)
        if square:
            s = max(-1.0, min(1.0, 3 * s))
        s = s * (1 - noise) + rng.uniform(-1, 1) * noise
        out.append(s * amp * math.exp(-decay * t) * min(1.0, i / 60))
    return out


def _start_beep(freq=450, dur=0.34, amp=0.5):
    """F1 start-light tone: low, flat and slightly buzzy, with a clean start and stop."""
    n = int(RATE * dur)
    out = []
    for i in range(n):
        env = min(1.0, i / 150, (n - i) / 900)
        a = 2 * math.pi * freq * i / RATE
        s = math.sin(a) + 0.35 * math.sin(2 * a) + 0.15 * math.sin(3 * a)
        out.append(math.tanh(1.8 * s) * amp * env)
    return out


# Team radio voice: Windows' built-in speech (System.Speech via PowerShell), then pitched
# down and squashed through a narrow, crunchy "radio" band with a squelch and beep.
PS_SPEAK = (
    "Add-Type -AssemblyName System.Speech;"
    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
    "try { $s.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::Male) } catch {};"
    "$s.Rate = 2;"
    "$f = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(22050,"
    " [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono);"
    "$s.SetOutputToWaveFile($env:TURBO_WAV, $f); $s.Speak($env:TURBO_SAY); $s.Dispose()"
)
RADIO_DIR = os.path.join(tempfile.gettempdir(), "turbo_sounds", "radio")
# Piper (github.com/rhasspy/piper): offline neural voice, preferred when present in ./piper
PIPER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "piper")
PIPER_EXE = os.path.join(PIPER_DIR, "piper", "piper.exe")


def piper_model():
    try:
        return next((os.path.join(PIPER_DIR, f) for f in sorted(os.listdir(PIPER_DIR)) if f.endswith(".onnx")), None)
    except OSError:
        return None


def radio_voice(text):
    """Path to a team-radio style WAV of text (cached). Windows only; raises if speech fails."""
    model = piper_model() if os.path.exists(PIPER_EXE) else None
    engine = os.path.basename(model)[:-5] if model else "sapi"
    path = os.path.join(RADIO_DIR, f"{engine}-{zlib.crc32(text.encode('utf-8')):08x}.wav")
    if os.path.exists(path):
        return path
    os.makedirs(RADIO_DIR, exist_ok=True)
    raw = path + ".tmp.wav"
    quiet = dict(timeout=30, check=True, capture_output=True,
                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if model:
        subprocess.run([PIPER_EXE, "--model", model, "--output_file", raw], input=text.encode("utf-8"), **quiet)
    else:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", PS_SPEAK],
                       env=dict(os.environ, TURBO_SAY=text, TURBO_WAV=raw), **quiet)
    with wave.open(raw) as w:
        rate = w.getframerate()
        x = array.array("h", w.readframes(w.getnframes()))
    os.remove(raw)
    # match our sample rate; the Windows voice is also pitched down ~15%
    k = (1.0 if model else 0.85) * rate / RATE
    x = [x[min(len(x) - 1, int(i * k))] / 32768 for i in range(int(len(x) / k))]
    # band-pass ~350-2800 Hz, drive, a little hiss
    rng = random.Random(5)
    hp = lp1 = lp2 = prev = 0.0
    a_hp = math.exp(-2 * math.pi * 350 / RATE)
    a_lp = 1 - math.exp(-2 * math.pi * 2800 / RATE)
    voice = []
    for v in x:
        hp = a_hp * (hp + v - prev)
        prev = v
        lp1 += a_lp * (hp - lp1)
        lp2 += a_lp * (lp1 - lp2)
        voice.append(math.tanh(4 * lp2) * 0.55 + rng.uniform(-0.025, 0.025))
    squelch = [rng.uniform(-0.3, 0.3) * (1 - i / 1300) for i in range(1300)]
    out = _beep(1250, 0.09, 0.3) + squelch + voice + [rng.uniform(-0.2, 0.2) for _ in range(900)]
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(array.array("h", (int(max(-1.0, min(1.0, v)) * 32000) for v in out)).tobytes())
    return path


def _sweep(segments):
    """[(seconds, f_from, f_to), ...] -> per-sample frequency list."""
    freqs = []
    for dur, f0, f1 in segments:
        n = int(RATE * dur)
        freqs += [f0 + (f1 - f0) * (1 - (1 - i / n) ** 2) for i in range(n)]
    return freqs


class Sound:
    REV_MS = 750

    def __init__(self, enabled=True):
        self.enabled = enabled and winsound is not None
        self.files = {}
        self.current = None
        if winsound is None:
            return
        import tempfile
        import wave
        folder = os.path.join(tempfile.gettempdir(), "turbo_sounds")
        try:
            os.makedirs(folder, exist_ok=True)
            loop_n = int(RATE * 0.4 // (RATE / ENGINE_HZ) * (RATE / ENGINE_HZ))
            rev, n = _engine_wave(_sweep([(0.3, 60, 250), (0.45, 250, ENGINE_HZ)]))
            rev = [s * min(1.0, i / 800) for i, s in enumerate(rev)]
            stop, n = _engine_wave(_sweep([(0.55, ENGINE_HZ, 45)]))
            stop = [s * (1 - i / n) ** 1.5 for i, s in enumerate(stop)]
            clips = {
                "rev": rev,
                "engine": _engine_wave([ENGINE_HZ] * loop_n, rumble=ENGINE_HZ / 6)[0],
                "stop": stop,
                "beep": _start_beep(),
                "jump": _tone(220, 760, 0.22, amp=0.35, square=True, decay=2),
                "land": _tone(110, 40, 0.18, amp=0.6, noise=0.35, decay=6),
                "poke": _tone(900, 1300, 0.07, amp=0.3, decay=4),
                "whoosh": _tone(300, 120, 0.35, amp=0.4, noise=0.8, decay=2.5, seed=7),
                "buzz": _tone(140, 120, 0.45, amp=0.35, square=True, decay=1),
                "chime": _beep(784, 0.12) + _beep(988, 0.12) + _beep(1175, 0.12) + _beep(1568, 0.3),
            }
            for name, samples in clips.items():
                path = os.path.join(folder, name + ".wav")
                with wave.open(path, "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(RATE)
                    w.writeframes(b"".join(int(s * 32000).to_bytes(2, "little", signed=True)
                                           for s in samples))
                self.files[name] = path
        except OSError:
            self.files = {}

    def play(self, name, loop=False):
        if not self.enabled or name not in self.files:
            return
        flags = winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT
        if loop:
            flags |= winsound.SND_LOOP
        try:
            winsound.PlaySound(self.files[name], flags)
            self.current = name
        except RuntimeError:
            pass

    def play_file(self, path):
        if not self.enabled:
            return
        try:
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            self.current = "voice"
        except RuntimeError:
            pass

    def stop(self):
        if winsound is not None and self.current:
            try:
                winsound.PlaySound(None, 0)
            except RuntimeError:
                pass
        self.current = None


# ====================================================================== live data
# Results, facts and jokes from free public APIs. Everything here runs on a
# worker thread (see Pet.fetch_bg) and returns plain dicts / strings.
#   F1 .............. Jolpica, the Ergast successor   https://api.jolpi.ca
#   MotoGP .......... the results API behind motogp.com
#   Formula Student . FS World Ranking List           https://fs-world.org
#   Jokes ........... icanhazdadjoke                  https://icanhazdadjoke.com

F1_API = "https://api.jolpi.ca/ergast/f1"
MOTOGP_API = "https://api.motogp.pulselive.com/motogp/v1/results"
FS_WORLD = "https://fs-world.org"
JOKE_API = "https://icanhazdadjoke.com/search"
HTTP_HEADERS = {"User-Agent": f"{NAME}-desktop-pet/1.0", "Accept": "application/json"}
FS_CLASSES = {"ev": ("2", "EV"), "cv": ("1", "CV"), "dc": ("3", "Driverless")}
JOKE_TERMS = ["car", "race", "drive", "tire", "engine", "wheel", "speed", "brake", "road", "fast"]
_cache = {}


def fetch(url, as_json=True, ttl=600):
    hit = _cache.get(url)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    req = urllib.request.Request(url, headers=HTTP_HEADERS)
    with urllib.request.urlopen(req, timeout=12) as r:
        data = r.read().decode("utf-8", "replace")
    if as_json:
        data = json.loads(data)
    _cache[url] = (time.time(), data)
    return data


def bmp(text):
    """Drop characters outside the BMP (emoji); Tk on Windows can't draw them."""
    return "".join(ch for ch in text if ord(ch) < 0x10000)


def f1_last_race():
    race = fetch(f"{F1_API}/current/last/results.json")["MRData"]["RaceTable"]["Races"][0]
    lines = [f"{r['position']:>2}. {r['Driver']['familyName'][:13]:<13} {r['Constructor']['name'][:15]}"
             for r in race["Results"]]
    return {"title": f"F1 R{race['round']}  {race['raceName']}", "lines": lines,
            "key": f"{race['season']}-{race['round']}"}


def f1_standings():
    table = fetch(f"{F1_API}/current/driverStandings.json")["MRData"]["StandingsTable"]
    st = table["StandingsLists"][0]
    lines = [f"{d['position']:>2}. {d['Driver']['familyName'][:16]:<16} {d['points']:>4} pts"
             for d in st["DriverStandings"]]
    return {"title": f"F1 {st['season']} drivers after R{st['round']}", "lines": lines}


def f1_constructors():
    st = fetch(f"{F1_API}/current/constructorStandings.json")["MRData"]["StandingsTable"]["StandingsLists"][0]
    lines = [f"{c['position']:>2}. {c['Constructor']['name'][:16]:<16} {c['points']:>4} pts"
             for c in st["ConstructorStandings"]]
    return {"title": f"F1 {st['season']} teams after R{st['round']}", "lines": lines}


def f1_next_race():
    race = fetch(f"{F1_API}/current/next.json")["MRData"]["RaceTable"]["Races"][0]
    start = time.mktime(time.strptime(race["date"] + " " + race.get("time", "12:00:00Z"),
                                      "%Y-%m-%d %H:%M:%SZ")) - time.timezone
    days = (start - time.time()) / 86400
    when = "today!" if days < 1 else "tomorrow" if days < 2 else f"in {int(days)} days"
    loc = race["Circuit"]["Location"]
    return {"title": f"F1 R{race['round']}  {race['raceName']}",
            "lines": [race["Circuit"]["circuitName"], f"{loc['locality']}, {loc['country']}",
                      time.strftime("%a %d %b  %H:%M", time.localtime(start)) + " your time",
                      f"Lights out {when}"]}


def f1_history_fact():
    """A random fact from 75 years of F1 results."""
    year = random.randint(1950, time.localtime().tm_year - 1)
    if random.random() < 0.3:
        st = fetch(f"{F1_API}/{year}/driverStandings/1.json", ttl=86400)
        champ = st["MRData"]["StandingsTable"]["StandingsLists"][0]["DriverStandings"][0]
        d = champ["Driver"]
        return (f"In {year}, {d['givenName']} {d['familyName']} was F1 world champion "
                f"with {champ['wins']} wins for {champ['Constructors'][0]['name']}.")
    races = fetch(f"{F1_API}/{year}/results/1.json?limit=100", ttl=86400)["MRData"]["RaceTable"]["Races"]
    race = random.choice(races)
    r = race["Results"][0]
    d = r["Driver"]
    start = "from the pit lane" if r["grid"] == "0" else f"from P{r['grid']}"
    return (f"Back in {year}, {d['givenName']} {d['familyName']} won the {race['raceName']} "
            f"for {r['Constructor']['name']}, starting {start}.")


def motogp_last_race():
    seasons = fetch(f"{MOTOGP_API}/seasons", ttl=86400)
    season = next(x for x in seasons if x["current"])
    events = fetch(f"{MOTOGP_API}/events?seasonUuid={season['id']}&isFinished=true")
    event = max((e for e in events if not e.get("test")), key=lambda e: e["date_end"])
    cats = fetch(f"{MOTOGP_API}/categories?seasonUuid={season['id']}", ttl=86400)
    cat = next(c for c in cats if c["name"].startswith("MotoGP"))
    sessions = fetch(f"{MOTOGP_API}/sessions?eventUuid={event['id']}&categoryUuid={cat['id']}")
    race = [x for x in sessions if x["type"] == "RAC"][-1]
    cl = fetch(f"{MOTOGP_API}/session/{race['id']}/classification?test=false")["classification"]
    lines = [f"{r['position']:>2}. {r['rider']['full_name'][:18]:<18} {r['constructor']['name'][:10]}"
             for r in cl if r.get("position")]
    name = event["name"].strip().title().replace(" Of ", " of ")
    return {"title": f"MotoGP  {name}", "lines": lines, "key": event["id"]}


def motogp_standings(teams=False):
    """Riders' championship, or the teams' one (sum of each team's riders' points)."""
    seasons = fetch(f"{MOTOGP_API}/seasons", ttl=86400)
    season = next(x for x in seasons if x["current"])
    cats = fetch(f"{MOTOGP_API}/categories?seasonUuid={season['id']}", ttl=86400)
    cat = next(c for c in cats if c["name"].startswith("MotoGP"))
    cl = fetch(f"{MOTOGP_API}/standings?seasonUuid={season['id']}&categoryUuid={cat['id']}")["classification"]
    if teams:
        pts = {}
        for r in cl:
            pts[r["team"]["name"]] = pts.get(r["team"]["name"], 0) + (r.get("points") or 0)
        top = sorted(pts.items(), key=lambda t: -t[1])
        lines = [f"{i:>2}. {bmp(n)[:22]:<22} {p:>4.0f}" for i, (n, p) in enumerate(top, 1)]
    else:
        lines = [f"{r['position']:>2}. {bmp(r['rider']['full_name'])[:22]:<22} {r['points']:>4.0f}"
                 for r in cl if r.get("position")]
    return {"title": f"MotoGP {season['year']} {'teams' if teams else 'riders'}", "lines": lines}


FEEDER_SITES = {"f2": ("F2", "https://www.fiaformula2.com"), "f3": ("F3", "https://www.fiaformula3.com")}


def feeder_standings(series="f2", teams=False):
    """F2 / F3 standings, read from the championship tables on the official sites."""
    label, site = FEEDER_SITES[series]
    page = fetch(f"{site}/Standings/{'Team' if teams else 'Driver'}", as_json=False, ttl=1800)
    page = re.sub(r' (?:class|style|alt|src)="[^"]*"', "", page)
    lines = []
    for pos, who, pts in re.findall(r"<tr><th><span>(\d+)</span>(.*?)</th>.*?<th>([^<]*)</th></tr>", page):
        name = html.unescape(re.findall(r"<span>([^<]+)</span>", who)[-1]).strip()
        lines.append(f"{pos:>2}. {bmp(name)[:22]:<22} {pts:>4}")
    return {"title": f"{label} {time.localtime().tm_year} {'teams' if teams else 'drivers'}", "lines": lines}


WEC_TABLES = {"hyper_makers": "Hypercar Manufacturers", "hyper_drivers": "Hypercar Drivers",
              "gt3_teams": "LMGT3 Teams", "gt3_drivers": "LMGT3 Drivers"}


def wec_standings(table="hyper_makers"):
    """WEC championship tables from the season page on fiawec.com."""
    year = time.localtime().tm_year
    page = fetch(f"https://www.fiawec.com/en/season/{year}", as_json=False, ttl=1800)
    titles = re.findall(r'data-bs-target="#(results-\d+)">\s*([^<]+?)\s*<', page)
    want = {"hyper_makers": ("Hypercar", "Manufacturers"), "hyper_drivers": ("Hypercar", "Drivers"),
            "gt3_teams": ("LMGT3", "Teams"), "gt3_drivers": ("LMGT3", "Drivers")}[table]
    block_id = next(bid for bid, t in titles if all(w in t for w in want))
    start = page.index(f'id="{block_id}"')
    block = page[start:page.index("</tbody>", start)]
    lines = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", block, re.S):
        cells = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", td))).strip()
                 for td in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) < 3 or not cells[0].isdigit():
            continue
        car = next((c for c in cells[1:] if c.startswith("#")), "")
        name = next((c for c in cells[1:-1] if c and not c.startswith("#")), "?")
        if "," in name:                       # crew: "RENE RAST , ROBIN FRIJNS" -> "Rast/Frijns"
            name = "/".join(n.split()[-1].title() for n in name.split(",") if n.split())
        elif table.endswith("drivers"):
            name = name.title()
        lines.append(f"{cells[0]:>2}. {bmp((car + ' ' + name).strip())[:22]:<22} {cells[-1]:>4}")
    return {"title": f"WEC {year} {WEC_TABLES[table]}", "lines": lines}


def fs_latest_events():
    """{class: (event id, label)} for the newest ranking update of each class."""
    page = fetch(f"{FS_WORLD}/ranking/latest", as_json=False)
    events = re.findall(r'<option value="(\d+)"\s+id="event" data-class="(\d+)"[^>]*>\s*([^<]*?)\s*</option>', page)
    out = {}
    for cls, (num, _) in FS_CLASSES.items():
        eid, _, label = max((e for e in events if e[1] == num), key=lambda e: e[2])
        out[cls] = (eid, html.unescape(label))
    return out


def fs_ranking(cls="ev", team=""):
    eid, label = fs_latest_events()[cls]
    rows = sorted(fetch(f"{FS_WORLD}/ranking/{cls}/{eid}/data")["list"], key=lambda r: r["rank"])
    row = lambda r: f"{r['rank']:>3}. {bmp(r['university_name'])[:23]:<23} {r['total']:>4.0f}"
    lines = [row(r) for r in rows[:5]]
    found = True
    if team:
        mine = [r for r in rows if team.lower() in r["university_name"].lower()]
        found = bool(mine)
        if mine and mine[0]["rank"] > 5:
            lines.append(row(mine[0]))
        elif not mine:
            lines.append(f"({team[:20]} not ranked in {FS_CLASSES[cls][1]})")
    return {"title": f"FS World Ranking {FS_CLASSES[cls][1]}", "lines": lines, "key": eid,
            "mark": team, "found": found, "foot": f"after {label}",
            "source": "FS-World.org, FS-World Data License v1.0, " + time.strftime("%Y-%m-%d %H:%M")}


def fs_my_team(team):
    """World ranking for your team, in whichever class it races."""
    for cls in FS_CLASSES:
        board = fs_ranking(cls, team)
        if board["found"]:
            return board
    return fs_ranking("ev", team)


FS_DISCIPLINES = {            # discipline name in fs-world.org tooltips -> short label
    "Total Points": "Overall",
    "Business Plan Presentation": "Business plan",
    "Cost & Manufacturing": "Cost",
    "Engineering Design": "Design",
    "Skidpad": "Skidpad",
    "Acceleration": "Acceleration",
    "Driverless Vehicle Skidpad": "DV Skidpad",
    "Driverless Vehicle Acceleration": "DV Acceleration",
    "Autocross": "Autocross",
    "Endurance": "Endurance",
    "Efficiency": "Efficiency",
}


def fs_competitions():
    """[(competition id, name)] sorted by name."""
    page = fetch(f"{FS_WORLD}/competition", as_json=False, ttl=86400)
    found = re.findall(r'<a href="/competition/(\d+)">\s*(?:<span.*?</span>)?\s*([^<]+?)\s*</a>', page, re.S)
    comps = {cid: bmp(html.unescape(name)) for cid, name in found}
    return sorted(comps.items(), key=lambda c: c[1].lower())


def fs_event_index():
    """{event id: (date, short name)} from the world ranking's event picker."""
    page = fetch(f"{FS_WORLD}/ranking/latest", as_json=False)
    events = re.findall(r'<option value="(\d+)"\s+id="event" data-class="\d+"[^>]*>\s*([^<]*?)\s*</option>', page)
    out = {}
    for eid, label in events:
        date, _, short = html.unescape(label).partition(" - ")
        out[eid] = (date, short)
    return out


def fs_competition_events(cid):
    """{class: [(event id, date, short name)] newest first} for one competition."""
    page = fetch(f"{FS_WORLD}/competition/{cid}", as_json=False, ttl=3600)
    index = fs_event_index()
    out = {}
    for eid, cls in re.findall(rf'href="/competition/{cid}/event/(\d+)">\s*<span class="team-class (\w+)"', page):
        out.setdefault(cls, []).append((eid,) + index.get(eid, ("", "")))
    for evs in out.values():
        evs.sort(key=lambda e: (e[1], int(e[0])), reverse=True)
    return out


def fs_event_results(cid, eid):
    """{discipline: [(rank, team, points)]} parsed from the event page's result tooltips."""
    page = fetch(f"{FS_WORLD}/competition/{cid}/event/{eid}", as_json=False, ttl=3600)
    out = {}
    for tip in re.findall(r'data-tooltip=\s*"([^"]*)"', page):
        parts = html.unescape(tip).split("\n")
        if len(parts) < 3 or parts[0] not in FS_DISCIPLINES:
            continue
        fields = dict(p.split(": ", 1) for p in parts[2:] if ": " in p)
        if "Points" in fields and "Rank" in fields:
            out.setdefault(parts[0], []).append((int(fields["Rank"]), bmp(parts[1]), float(fields["Points"])))
    for rows in out.values():
        rows.sort()
    return {d: out[d] for d in FS_DISCIPLINES if d in out}


def fs_load(cid, cls=None, eid=None):
    """Events of a competition plus the results of one of them (newest of cls by default)."""
    events = fs_competition_events(cid)
    out = {"cid": cid, "events": events, "cls": None, "eid": None, "date": "", "short": "", "results": {}}
    if not events:
        return out
    if cls not in events:
        cls = next((c for c in ("ev", "cv", "dc") if c in events), next(iter(events)))
    ev = next((e for e in events[cls] if e[0] == eid), events[cls][0])
    out.update(cls=cls, eid=ev[0], date=ev[1], short=ev[2], results=fs_event_results(cid, ev[0]))
    return out


def fs_board(data, disc, name, team=""):
    rows = data["results"].get(disc, [])
    row = lambda r: f"{r[0]:>3}. {r[1][:24]:<24} {r[2]:>5.1f}"
    lines = [row(r) for r in rows[:5]]
    mine = [r for r in rows if team and team.lower() in r[1].lower()]
    if mine and mine[0][0] > 5:
        lines.append(row(mine[0]))
    cls = FS_CLASSES.get(data["cls"], ("", (data["cls"] or "").upper()))[1]
    return {"title": f"{data['short'] or name[:14]} {cls}: {FS_DISCIPLINES.get(disc, disc)}",
            "lines": lines or ["No results yet."], "key": f"{data['eid']}", "mark": team,
            "foot": f"{name}  {data['date']}".strip(),
            "source": "FS-World.org, FS-World Data License v1.0, " + time.strftime("%Y-%m-%d %H:%M")}


def online_joke():
    term = random.choice(JOKE_TERMS)
    res = fetch(f"{JOKE_API}?term={urllib.parse.quote(term)}&limit=30", ttl=3600)["results"]
    return random.choice([bmp(j["joke"]) for j in res if len(j["joke"]) < 150])


# ====================================================================== menu
# A popup menu drawn on a canvas in Turbo's colours: dark suit, orange trim,
# a chequered flag in the header. Submenus open in place; the header goes back.

MENU_BG = "#1c1c21"
MENU_HEAD = "#0e0e11"
MENU_TEXT = "#f2f2f2"
MENU_DIM = "#8a8a94"


class RaceMenu:
    WIDTH, ROW, SEP, HEAD = 250, 28, 11, 38

    # items: ("cmd", label, fn) | ("check", label, BooleanVar, fn) | ("sub", label, items or fn) | ("sep",)
    #        | ("radio", label, StringVar, value, fn, swatch colours) - keeps the menu open
    def __init__(self, root, items, title=f"{NAME.upper()}  #26", on_pick=None):
        self.root, self.items, self.title = root, items, title
        self.on_pick = on_pick         # called before any command / checkbox runs
        self.win = None
        self.hover = None

    def popup(self, x, y):
        self.close()
        self.stack = [(self.title, self.items)]
        self.anchor = (x, y)
        self.hover = None
        w = self.win = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        try:
            w.attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            pass
        w.config(bg=TRANSPARENT)
        c = self.c = tk.Canvas(w, width=self.WIDTH, height=10, bg=TRANSPARENT, highlightthickness=0)
        c.pack()
        c.bind("<Motion>", lambda e: self.set_hover(self.hit(e.y)))
        c.bind("<Leave>", lambda e: self.set_hover(None))
        c.bind("<ButtonRelease-1>", self.on_click)
        w.bind("<Escape>", lambda e: self.close())
        w.bind("<FocusOut>", lambda e: self.root.after(80, self.check_focus))
        self.render()
        w.focus_force()

    def close(self):
        if self.win:
            self.win.destroy()
            self.win = None

    def check_focus(self):
        if self.win and self.win.focus_displayof() is None:
            self.close()

    def layout(self):
        rows, y = [], self.HEAD + 6
        for it in self.stack[-1][1]:
            h = self.SEP if it[0] == "sep" else self.ROW
            rows.append((y, y + h, it))
            y += h
        return rows, y + 6

    def render(self):
        c, w = self.c, self.WIDTH
        c.delete("all")
        title = self.stack[-1][0]
        rows, height = self.layout()
        c.config(height=height)
        round_rect(c, 1, 1, w - 1, height - 1, 14, fill=MENU_BG, outline=ORANGE, width=2)
        # header: dark visor strip, orange helmet stripe, chequered flag
        round_rect(c, 5, 5, w - 5, self.HEAD, 10, fill=MENU_HEAD, outline="")
        c.create_rectangle(5, self.HEAD - 4, w - 5, self.HEAD, fill=ORANGE, outline="")
        sub = len(self.stack) > 1
        c.create_text(16, self.HEAD / 2, anchor="w", text=("◂  " + title) if sub else title,
                      fill=MENU_TEXT if self.hover == "head" else ORANGE, font=("Segoe UI", 11, "bold"))
        sq = 5
        for row in range(3):
            for col in range(6):
                if (row + col) % 2 == 0:
                    x0, y0 = w - 46 + col * sq, 10 + row * sq
                    c.create_rectangle(x0, y0, x0 + sq, y0 + sq, fill=MENU_TEXT, outline="")
        for i, (y0, y1, it) in enumerate(rows):
            ym = (y0 + y1) / 2
            if it[0] == "sep":
                c.create_line(16, ym, w - 16, ym, fill="#34343c")
                continue
            hot = self.hover == i
            if hot:
                round_rect(c, 8, y0 + 2, w - 8, y1 - 2, 9, fill=ORANGE, outline="")
            fg = "#111111" if hot else MENU_TEXT
            tx = 20
            if it[0] == "radio":
                accent, suit = it[5]
                c.create_oval(18, ym - 8, 34, ym + 8, fill=suit, outline="#111111" if hot else MENU_DIM)
                c.create_oval(22, ym - 4, 30, ym + 4, fill=accent, outline="")
                tx = 44
            c.create_text(tx, ym, anchor="w", text=it[1], fill=fg, font=FONT)
            if it[0] == "sub":
                c.create_text(w - 20, ym, anchor="e", text="▸", fill=fg if hot else ORANGE,
                              font=("Segoe UI", 11))
            elif it[0] == "check":
                on = it[2].get()
                bx = w - 34
                box = "#111111" if hot else ORANGE
                round_rect(c, bx, ym - 7, bx + 14, ym + 7, 4, width=2, fill=box if on else "",
                           outline=box if (on or hot) else MENU_DIM)
                if on:
                    c.create_text(bx + 7, ym, text="✓", font=("Segoe UI", 8, "bold"),
                                  fill=ORANGE if hot else "#111111")
            elif it[0] == "radio" and it[2].get() == it[3]:
                c.create_text(w - 22, ym, anchor="e", text="✓", font=("Segoe UI", 11, "bold"),
                              fill=fg if hot else ORANGE)
        self.place(height)

    def place(self, height):
        x, y = self.anchor
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x = min(x, sw - self.WIDTH - 4)
        if y + height > sh - 4:
            y = max(4, y - height)
        self.win.geometry(f"{self.WIDTH}x{height}+{int(x)}+{int(y)}")

    def hit(self, y):
        if y < self.HEAD:
            return "head" if len(self.stack) > 1 else None
        for i, (y0, y1, it) in enumerate(self.layout()[0]):
            if y0 <= y < y1 and it[0] != "sep":
                return i
        return None

    def set_hover(self, h):
        if h != self.hover:
            self.hover = h
            self.render()

    def on_click(self, e):
        h = self.hit(e.y)
        if h is None:
            return
        if h == "head":
            self.stack.pop()
        else:
            it = self.stack[-1][1][h]
            if it[0] == "radio":
                it[2].set(it[3])
                it[4]()
                self.render()
                return
            if it[0] != "sub":
                self.close()
                if self.on_pick:
                    self.on_pick()
                if it[0] == "check":
                    it[2].set(not it[2].get())
                    self.root.after(1, it[3])
                else:
                    self.root.after(1, it[2])
                return
            self.stack.append((it[1], it[2]() if callable(it[2]) else it[2]))
        self.hover = None
        self.render()


# ====================================================================== panels
# Borderless windows in the menu's style: header with title, chequered flag and
# close button (drag the header to move), and click regions registered while drawing.

class Panel:
    WIDTH, HEAD = 470, 38
    TITLE = ""
    BTN = "#2a2a31"

    def __init__(self, pet):
        self.pet = pet
        self.win = None
        self.hover = None
        self.hits = []
        self.drag = None

    def open(self):
        if self.win:
            self.win.lift()
            return
        w = self.win = tk.Toplevel(self.pet.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        try:
            w.attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            pass
        w.config(bg=TRANSPARENT)
        c = self.c = tk.Canvas(w, width=self.WIDTH, height=10, bg=TRANSPARENT, highlightthickness=0)
        c.pack()
        c.bind("<Motion>", lambda e: self.set_hover(self.hit(e.x, e.y)))
        c.bind("<Leave>", lambda e: self.set_hover(None))
        c.bind("<ButtonPress-1>", self.on_press)
        c.bind("<B1-Motion>", self.on_drag)
        c.bind("<ButtonRelease-1>", self.on_release)
        c.bind("<MouseWheel>", self.on_wheel)
        w.bind("<Escape>", lambda e: self.close())
        self.render()
        # park next to Turbo, feet level with his
        pet, sw = self.pet, w.winfo_screenwidth()
        x = pet.x - self.WIDTH + 30 if pet.x > self.WIDTH else pet.x + W - 30
        y = pet.y + FOOT - int(c["height"])
        w.geometry(f"+{int(max(0, min(x, sw - self.WIDTH)))}+{int(max(0, y))}")
        w.focus_force()
        self.on_open()

    def on_open(self):
        pass

    def close(self):
        if self.win:
            self.win.destroy()
            self.win = None

    def refresh(self):
        if self.win:
            self.render()

    # ---------------------------------------------------------- drawing
    def frame(self, height):
        """Clear and draw the window body and header; returns the canvas."""
        c, w, head = self.c, self.WIDTH, self.HEAD
        c.delete("all")
        self.hits = []
        c.config(height=height)
        round_rect(c, 1, 1, w - 1, height - 1, 14, fill=MENU_BG, outline=ORANGE, width=2)
        round_rect(c, 5, 5, w - 5, head, 10, fill=MENU_HEAD, outline="")
        c.create_rectangle(5, head - 4, w - 5, head, fill=ORANGE, outline="")
        c.create_text(16, head / 2, anchor="w", text=self.TITLE, fill=ORANGE, font=("Segoe UI", 11, "bold"))
        for row in range(3):
            for col in range(6):
                if (row + col) % 2 == 0:
                    x0, y0 = w - 76 + col * 5, 10 + row * 5
                    c.create_rectangle(x0, y0, x0 + 5, y0 + 5, fill=MENU_TEXT, outline="")
        c.create_text(w - 22, head / 2 - 2, text="×", font=("Segoe UI", 15, "bold"),
                      fill=ORANGE if self.hover == ("close",) else MENU_TEXT)
        self.hits.append(((w - 38, 5, w - 6, head - 4), ("close",)))
        return c

    def button(self, x0, y0, x1, label, action, enabled=True):
        hot = enabled and self.hover == action
        round_rect(self.c, x0, y0, x1, y0 + 28, 9, fill=ORANGE if hot else self.BTN, outline="")
        self.c.create_text((x0 + x1) / 2, y0 + 14, text=label, font=FONT,
                           fill="#111111" if hot else MENU_TEXT if enabled else "#55555e")
        if enabled:
            self.hits.append(((x0, y0, x1, y0 + 28), action))

    def chip(self, x, y, label, action, selected=False):
        """Small pill button; returns the x where the next chip can start."""
        x1 = x + 6 * len(label) + 16
        hot = self.hover == action
        round_rect(self.c, x, y, x1, y + 24, 11, fill=ORANGE if selected else "#3a3a44" if hot else self.BTN,
                   outline="")
        self.c.create_text((x + x1) / 2, y + 12, text=label, font=("Segoe UI", 9),
                           fill="#111111" if selected else MENU_TEXT)
        self.hits.append(((x, y, x1, y + 24), action))
        return x1 + 6

    # ---------------------------------------------------------- mouse
    def hit(self, x, y):
        for (x0, y0, x1, y1), action in self.hits:
            if x0 <= x < x1 and y0 <= y < y1:
                return action
        return None

    def set_hover(self, h):
        if h != self.hover:
            self.hover = h
            self.render()

    def on_press(self, e):
        self.drag = None
        if e.y < self.HEAD and self.hit(e.x, e.y) is None:
            self.drag = (e.x_root - self.win.winfo_x(), e.y_root - self.win.winfo_y())

    def on_drag(self, e):
        if self.drag:
            self.win.geometry(f"+{e.x_root - self.drag[0]}+{e.y_root - self.drag[1]}")

    def on_release(self, e):
        if self.drag:
            self.drag = None
            return
        action = self.hit(e.x, e.y)
        if action:
            getattr(self, "do_" + action[0])(*action[1:])

    def on_wheel(self, e):
        pass

    def do_close(self):
        self.close()


# ====================================================================== livery garage
# Editor for the colour schemes. Whatever livery is selected is applied to
# Turbo immediately, so Turbo is the live preview.

LIVERY_PARTS = ("Accent", "Accent shade", "Suit", "Helmet")
HEX_COLOUR = re.compile(r"^#[0-9a-fA-F]{6}$")


def shade_of(colour, k=0.8):
    r, g, b = hex_rgba(colour)[:3]
    return "#%02x%02x%02x" % (int(r * k), int(g * k), int(b * k))


class Garage(Panel):
    WIDTH, ROW, LIST_W = 470, 28, 190
    TITLE = "LIVERY GARAGE"

    def render(self):
        w, head, row = self.WIDTH, self.HEAD, self.ROW
        names = list(LIVERIES)
        cur = self.pet.livery_var.get()
        colours = LIVERIES[cur]
        list_h = len(names) * row
        height = head + 10 + max(list_h + 44, 272) + 10
        c = self.frame(height)

        # livery list
        y = head + 10
        for name in names:
            sel, hot = name == cur, self.hover == ("pick", name)
            if sel or hot:
                round_rect(c, 8, y + 2, self.LIST_W, y + row - 2, 9, fill=ORANGE if sel else self.BTN, outline="")
            ym = y + row / 2
            c.create_oval(18, ym - 8, 34, ym + 8, fill=LIVERIES[name][2], outline="#111111" if sel else MENU_DIM)
            c.create_oval(22, ym - 4, 30, ym + 4, fill=LIVERIES[name][0], outline="")
            c.create_text(44, ym, anchor="w", text=name[:18], font=FONT,
                          fill="#111111" if sel else MENU_TEXT)
            self.hits.append(((8, y, self.LIST_W, y + row), ("pick", name)))
            y += row
        by = y + 10
        mid = (8 + self.LIST_W) / 2
        self.button(8, by, mid - 3, "+  New", ("new",))
        self.button(mid + 3, by, self.LIST_W, "Delete", ("delete",), enabled=len(names) > 1)
        c.create_line(self.LIST_W + 12, head + 14, self.LIST_W + 12, height - 14, fill="#34343c")

        # editor for the selected livery
        x0, x1 = self.LIST_W + 28, w - 12
        c.create_text(x0, head + 26, anchor="w", text=cur[:22], fill=ORANGE, font=("Segoe UI", 12, "bold"))
        y = head + 50
        for i, part in enumerate(LIVERY_PARTS):
            hot = self.hover == ("colour", i)
            if hot:
                round_rect(c, x0 - 8, y, x1, y + 30, 9, fill=self.BTN, outline="")
            c.create_text(x0, y + 15, anchor="w", text=part, fill=MENU_TEXT, font=FONT)
            round_rect(c, x1 - 118, y + 5, x1 - 80, y + 25, 6, fill=colours[i],
                       outline=MENU_TEXT if hot else MENU_DIM, width=1)
            c.create_text(x1 - 72, y + 15, anchor="w", text=colours[i].upper(), fill=MENU_DIM,
                          font=("Consolas", 9))
            self.hits.append(((x0 - 8, y, x1, y + 30), ("colour", i)))
            y += 34
        c.create_text(x0, y + 6, anchor="nw", width=x1 - x0, fill=MENU_DIM, font=("Segoe UI", 8),
                      text="Click a colour to change it. Turbo wears the selected livery "
                           "while you edit, and the shade follows the accent.")
        by = height - 10 - 28 - 4
        third = (x1 - x0 + 8) / 3
        self.button(x0 - 8, by, x0 - 8 + third - 4, "Rename", ("rename",))
        self.button(x0 - 8 + third, by, x0 - 8 + 2 * third - 4, "Duplicate", ("duplicate",))
        self.button(x0 - 8 + 2 * third, by, x1, "Reset all", ("reset",))

    # ---------------------------------------------------------- actions
    def changed(self, name=None):
        if name is not None:
            self.pet.livery_var.set(name)
        self.pet.set_livery(quiet=True)
        self.pet.save_liveries()
        self.refresh()

    def unique(self, base):
        name, n = base, 2
        while name in LIVERIES:
            name, n = f"{base} {n}", n + 1
        return name

    def do_pick(self, name):
        self.changed(name)

    def do_colour(self, i):
        from tkinter import colorchooser
        cur = self.pet.livery_var.get()
        colours = list(LIVERIES[cur])
        picked = colorchooser.askcolor(colours[i], parent=self.win, title=f"{cur}: {LIVERY_PARTS[i]}")[1]
        if not picked or not self.win:
            return
        colours[i] = picked
        if i == 0:
            colours[1] = shade_of(picked)
        LIVERIES[cur] = tuple(colours)
        self.changed()

    def do_new(self):
        name = self.unique("My livery")
        LIVERIES[name] = LIVERIES[self.pet.livery_var.get()]
        self.changed(name)

    def do_duplicate(self):
        cur = self.pet.livery_var.get()
        name = self.unique(cur + " copy")
        LIVERIES[name] = LIVERIES[cur]
        self.changed(name)

    def do_delete(self):
        names = list(LIVERIES)
        cur = self.pet.livery_var.get()
        if len(names) < 2:
            return
        i = names.index(cur)
        del LIVERIES[cur]
        self.changed(list(LIVERIES)[min(i, len(LIVERIES) - 1)])

    def do_rename(self):
        cur = self.pet.livery_var.get()
        new = simpledialog.askstring("Rename livery", "New name:", initialvalue=cur, parent=self.win)
        new = (new or "").strip()[:30]
        if not new or new == cur or new in LIVERIES or not self.win:
            return
        items = [(new if k == cur else k, v) for k, v in LIVERIES.items()]
        LIVERIES.clear()
        LIVERIES.update(items)
        self.changed(new)

    def do_reset(self):
        from tkinter import messagebox
        if not messagebox.askyesno("Reset liveries", "Remove your own liveries and restore the "
                                   "original colour schemes?", parent=self.win) or not self.win:
            return
        cur = self.pet.livery_var.get()
        LIVERIES.clear()
        LIVERIES.update(DEFAULT_LIVERIES)
        self.changed(cur if cur in LIVERIES else DEFAULT_LIVERY)


# ====================================================================== telemetry
# A little console showing what Turbo himself costs: CPU, RAM, frame rate.

def process_memory():
    """(working set, private bytes) of this process in bytes; None where unknown."""
    try:
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (n, ctypes.c_size_t) for n in (
                    "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
                    "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage",
                    "PeakPagefileUsage", "PrivateUsage")]
        c = Counters()
        c.cb = ctypes.sizeof(c)
        k32 = ctypes.windll.kernel32
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        get = ctypes.windll.psapi.GetProcessMemoryInfo
        get.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        if get(k32.GetCurrentProcess(), ctypes.byref(c), c.cb):
            return c.WorkingSetSize, c.PrivateUsage
    except (AttributeError, OSError):
        try:
            import resource
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024, None
        except ImportError:
            pass
    return None, None


class Telemetry(Panel):
    WIDTH = 380
    TITLE = "TELEMETRY"
    HISTORY = 60                       # seconds of graph

    def __init__(self, pet):
        super().__init__(pet)
        self.cpu, self.ram = [], []
        self.stats = {}
        self.job = None
        self.last = None

    def on_open(self):
        self.last = (time.perf_counter(), time.process_time(), self.pet.frames)
        self.tick()

    def close(self):
        if self.job:
            self.pet.root.after_cancel(self.job)
            self.job = None
        super().close()

    def tick(self):
        """Sample once a second while the console is open."""
        wall, cpu, frames = time.perf_counter(), time.process_time(), self.pet.frames
        w0, c0, f0 = self.last
        span = max(1e-6, wall - w0)
        one_core = 100 * (cpu - c0) / span
        ws, private = process_memory()
        self.last = (wall, cpu, frames)
        self.stats = {"core": one_core, "all": one_core / (os.cpu_count() or 1), "ws": ws,
                      "private": private, "fps": (frames - f0) / span}
        self.cpu = (self.cpu + [self.stats["all"]])[-self.HISTORY:]
        if ws:
            self.ram = (self.ram + [ws / 2 ** 20])[-self.HISTORY:]
        self.refresh()
        self.job = self.pet.root.after(1000, self.tick)

    def graph(self, x0, y0, x1, y1, values, top, colour, label):
        c = self.c
        c.create_rectangle(x0, y0, x1, y1, outline="#26262d", fill="#0b0b0e")
        for k in (0.25, 0.5, 0.75):
            y = y1 - (y1 - y0) * k
            c.create_line(x0 + 1, y, x1 - 1, y, fill="#18181d")
        if len(values) > 1:
            step = (x1 - x0 - 4) / (self.HISTORY - 1)
            start = x1 - 2 - step * (len(values) - 1)
            pts = []
            for i, v in enumerate(values):
                pts += [start + i * step, y1 - 2 - (y1 - y0 - 4) * min(1.0, v / top)]
            c.create_line(*pts, fill=colour, width=2, smooth=True)
        c.create_text(x0 + 6, y0 + 4, anchor="nw", text=label, fill=MENU_DIM, font=("Consolas", 8))

    def render(self):
        w, head = self.WIDTH, self.HEAD
        height = head + 238
        c = self.frame(height)
        # console screen
        x0, y0, x1, y1 = 10, head + 8, w - 10, height - 10
        round_rect(c, x0, y0, x1, y1, 8, fill="#08080a", outline="#26262d")
        s, pet = self.stats, self.pet
        mb = lambda b: f"{b / 2 ** 20:6.1f} MB" if b else "   n/a"
        up = int(time.time() - pet.started)
        rows = [
            ("> turbo --telemetry", ORANGE, ""),
            ("CPU", f"{s.get('all', 0):5.1f} %", f"one core {s.get('core', 0):5.1f} %"),
            ("RAM", mb(s.get("ws")), f"private {mb(s.get('private')).strip()}"),
            ("FPS", f"{s.get('fps', 0):5.0f}", f"frame {pet.frame_ms:4.1f} ms"),
            ("THREADS", f"{threading.active_count():5d}",
             f"cached {len(pet.renderer.frames)} frames"),
            ("UPTIME", f"{up // 3600:02d}:{up // 60 % 60:02d}:{up % 60:02d}", f"state {pet.state}"),
        ]
        y = y0 + 12
        for label, value, extra in rows:
            if extra == "":            # prompt line
                cursor = "_" if int(time.time() * 2) % 2 else " "
                c.create_text(x0 + 12, y, anchor="w", text=label + " " + cursor, fill=value,
                              font=("Consolas", 10, "bold"))
            else:
                c.create_text(x0 + 12, y, anchor="w", text=f"{label:<8}", fill=ORANGE, font=("Consolas", 10))
                c.create_text(x0 + 84, y, anchor="w", text=value, fill=MENU_TEXT, font=("Consolas", 10, "bold"))
                c.create_text(x0 + 180, y, anchor="w", text=extra, fill=MENU_DIM, font=("Consolas", 9))
            y += 19
        # graphs: CPU scaled to the busiest second (min 5 %), RAM to the largest sample
        gy0, gy1 = y + 4, y1 - 10
        mid = (x0 + x1) / 2
        cpu_top = max([5.0] + self.cpu) * 1.2
        ram_top = max([1.0] + self.ram) * 1.2
        self.graph(x0 + 10, gy0, mid - 5, gy1, self.cpu, cpu_top, ORANGE, f"CPU  0-{cpu_top:.0f}%")
        self.graph(mid + 5, gy0, x1 - 10, gy1, self.ram, ram_top, MENU_TEXT, f"RAM  0-{ram_top:.0f} MB")


# ====================================================================== FS results
# Pick a Formula Student competition, class, year and discipline; show the
# results here, put them on Turbo's board, or follow them for new-result alerts.

class FSResults(Panel):
    WIDTH, ROW, LIST_W, VISIBLE = 620, 24, 214, 15
    TITLE = "FORMULA STUDENT RESULTS"

    def __init__(self, pet):
        super().__init__(pet)
        self.comps = None              # [(competition id, name)]
        self.cid = None
        self.data = None               # fs_load() result for the selected competition
        self.disc = "Total Points"
        self.scroll = 0
        self.status = "Loading competitions..."

    def on_open(self):
        if self.comps is None:
            self.pet.fetch_bg(fs_competitions, self.got_comps)
        pick = self.pet.stats.get("fs_follow")
        if pick and self.cid is None:
            self.disc = pick["disc"]
            self.load(pick["cid"], pick["cls"])

    # ---------------------------------------------------------- data
    def got_comps(self, res):
        if isinstance(res, Exception):
            self.status = "No signal from the pit wall. Are we offline?"
        else:
            self.comps = res
            ids = [cid for cid, _ in res]
            if self.cid in ids:
                self.scroll = max(0, min(ids.index(self.cid) - 3, len(ids) - self.VISIBLE))
        self.refresh()

    def load(self, cid, cls=None, eid=None):
        if cid != self.cid:
            self.data = None
        self.cid = cid
        self.status = "Loading results..."
        self.refresh()
        self.pet.fetch_bg(lambda: fs_load(cid, cls, eid), self.got_data)

    def got_data(self, res):
        if isinstance(res, Exception):
            self.status = "No signal from the pit wall. Are we offline?"
        elif res["cid"] == self.cid:
            self.data = res
            self.status = "" if res["results"] else "No results published for this one."
            if res["results"] and self.disc not in res["results"]:
                self.disc = "Total Points"
        self.refresh()

    def comp_name(self):
        return dict(self.comps or []).get(self.cid) or (self.data or {}).get("name") or ""

    def pick(self):
        d = self.data
        return {"cid": self.cid, "cls": d["cls"], "disc": self.disc, "name": self.comp_name()}

    def following(self):
        f = self.pet.stats.get("fs_follow")
        return bool(f and self.data and (f["cid"], f["cls"], f["disc"]) == (self.cid, self.data["cls"], self.disc))

    # ---------------------------------------------------------- drawing
    def render(self):
        w, head, row = self.WIDTH, self.HEAD, self.ROW
        height = head + 10 + self.VISIBLE * row + 10
        c = self.frame(height)

        # competition list
        y = head + 10
        if not self.comps:
            c.create_text(18, y + 12, anchor="w", text=self.status if self.comps is None else "",
                          fill=MENU_DIM, font=("Segoe UI", 9))
        for cid, name in (self.comps or [])[self.scroll:self.scroll + self.VISIBLE]:
            sel, hot = cid == self.cid, self.hover == ("comp", cid)
            if sel or hot:
                round_rect(c, 8, y + 1, self.LIST_W, y + row - 1, 9, fill=ORANGE if sel else self.BTN, outline="")
            c.create_text(18, y + row / 2, anchor="w", text=name[:30], font=("Segoe UI", 9),
                          fill="#111111" if sel else MENU_TEXT)
            self.hits.append(((8, y, self.LIST_W, y + row), ("comp", cid)))
            y += row
        n = len(self.comps or [])
        if n > self.VISIBLE:                   # scroll bar
            top, span = head + 12, self.VISIBLE * row - 4
            y0 = top + span * self.scroll / n
            c.create_line(self.LIST_W + 5, y0, self.LIST_W + 5, y0 + span * self.VISIBLE / n,
                          fill=MENU_DIM, width=3, capstyle="round")
        c.create_line(self.LIST_W + 14, head + 14, self.LIST_W + 14, height - 14, fill="#34343c")

        x0, x1 = self.LIST_W + 30, w - 14
        if self.cid is None:
            c.create_text(x0, head + 26, anchor="w", text="Pick a competition on the left.",
                          fill=MENU_DIM, font=FONT)
            return
        c.create_text(x0, head + 22, anchor="w", text=self.comp_name()[:40], fill=ORANGE,
                      font=("Segoe UI", 12, "bold"))
        d = self.data
        if not d or not d["events"]:
            c.create_text(x0, head + 50, anchor="w", text=self.status or "No events found.",
                          fill=MENU_DIM, font=FONT)
            return
        events = d["events"][d["cls"]]
        teams = len(d["results"].get("Total Points", []))
        c.create_text(x0, head + 44, anchor="w", fill=MENU_DIM, font=("Segoe UI", 9),
                      text=f"{FS_CLASSES.get(d['cls'], ('', d['cls'].upper()))[1]}  ·  "
                           f"{d['date'] or 'date unknown'}  ·  {teams} teams"
                           + (f"   {self.status}" if self.status else ""))

        # class + year chips
        y = head + 60
        x = x0
        for cls in ("ev", "cv", "dc"):
            if cls in d["events"]:
                x = self.chip(x, y, FS_CLASSES[cls][1], ("cls", cls), cls == d["cls"])
        x += 12
        for eid, date, _ in events[:4]:
            x = self.chip(x, y, date[:4] or f"#{eid}", ("eid", eid), eid == d["eid"])

        # discipline chips, wrapping
        y, x = y + 32, x0
        for disc in d["results"]:
            label = FS_DISCIPLINES[disc]
            if x + 6 * len(label) + 16 > x1:
                x, y = x0, y + 30
            x = self.chip(x, y, label, ("disc", disc), disc == self.disc)

        # results table
        by = height - 10 - 28 - 4
        y += 36
        c.create_text(x0, y, anchor="w", text="  #  Team", fill=MENU_DIM, font=("Consolas", 9))
        c.create_text(x1, y, anchor="e", text="Points", fill=MENU_DIM, font=("Consolas", 9))
        y += 16
        team = self.pet.fs_team().lower()
        rows = d["results"].get(self.disc, [])
        room = max(1, int((by - 8 - y) // 17))
        shown = rows[:room]
        mine = [r for r in rows if team and team in r[1].lower()]
        if mine and mine[0] not in shown:
            shown = shown[:room - 1] + [mine[0]]
        for rank, name, pts in shown:
            hot = bool(team) and team in name.lower()
            f = ("Consolas", 9, "bold" if hot else "normal")
            fg = ORANGE if hot else MENU_TEXT
            c.create_text(x0, y, anchor="w", text=f"{rank:>3}  {name[:34]}", fill=fg, font=f)
            c.create_text(x1, y, anchor="e", text=f"{pts:.1f}", fill=fg, font=f)
            y += 17

        half = (x1 - x0 + 8) / 2
        self.button(x0 - 8, by, x0 - 8 + half - 4, "Show on Turbo", ("show",), enabled=bool(rows))
        self.button(x0 - 8 + half, by, x1, "Following ★" if self.following() else "Follow this",
                    ("follow",), enabled=bool(rows))

    # ---------------------------------------------------------- actions
    def on_wheel(self, e):
        if self.comps and e.x < self.LIST_W + 14:
            step = -3 if e.delta > 0 else 3
            self.scroll = max(0, min(self.scroll + step, len(self.comps) - self.VISIBLE))
            self.render()

    def do_comp(self, cid):
        self.load(cid, self.data["cls"] if self.data else None)

    def do_cls(self, cls):
        self.load(self.cid, cls)

    def do_eid(self, eid):
        self.load(self.cid, self.data["cls"], eid)

    def do_disc(self, disc):
        self.disc = disc
        self.render()

    def do_show(self):
        self.pet.bubble_until = 0
        self.pet.show_board(fs_board(self.data, self.disc, self.comp_name(), self.pet.fs_team()))

    def do_follow(self):
        pet = self.pet
        if self.following():
            del pet.stats["fs_follow"]
            pet.say("OK, back to the world ranking for Formula Student.")
        else:
            pet.stats["fs_follow"] = self.pick()
            pet.follow["fs"].set(True)
            pet.stats["follow"] = [k for k, var in pet.follow.items() if var.get()]
            pet.say(f"Following {self.comp_name()} {FS_DISCIPLINES[self.disc].lower()} results!", happy=True)
        pet.stats.get("seen", {}).pop("fs", None)     # new source: don't announce it as news
        save_stats(pet.stats)
        pet.check_leagues(reschedule=False)
        self.render()


# ====================================================================== renderer
# The character is painted with Pillow at SS x resolution and downsampled, which
# gives smooth anti-aliased shapes and soft shading. Finished frames are cached.

SS = 3                              # supersampling factor
SW, SH = 220, 250                   # sprite size (1x)
SCX, SF, SHY = 110, 242, 110        # sprite centre x, ground line, helmet centre y
SPRITE_X, SPRITE_Y = CX - SCX, FOOT - SF   # where the sprite sits in the window

C_OUT = (6, 6, 8, 255)
C_SUIT = (27, 28, 34, 255)
C_HELM = (22, 22, 27, 255)
C_ORANGE = (255, 122, 26, 255)
C_ORANGE_D = (214, 92, 14, 255)
C_RED = (255, 48, 48, 255)
C_WHITE = (246, 246, 246, 255)
C_VISOR = (10, 11, 14, 255)
KEY_RGB = tuple(int(TRANSPARENT[i:i + 2], 16) for i in (1, 3, 5))

# Liveries recolour Turbo, the car, the menu and the boards.
# name: (accent, accent shade, suit, helmet)
LIVERIES = {
    "Turbo orange":  ("#ff7a1a", "#d65c0e", "#1b1c22", "#16161b"),
    "Racing red":    ("#ff2d3a", "#c01622", "#1b1c22", "#16161b"),
    "Electric blue": ("#2f8bff", "#1a5fd0", "#161a24", "#12151d"),
    "Petrol teal":   ("#12d3bf", "#0a9a8b", "#1a1f22", "#14181a"),
    "Lime green":    ("#9be22a", "#6fae14", "#1b1d1a", "#161815"),
    "Hot pink":      ("#ff4fae", "#d02a86", "#1e1a20", "#18151a"),
    "Gold":          ("#ffc02e", "#d0911a", "#1d1b17", "#171512"),
    "Silver arrow":  ("#12d3bf", "#0a9a8b", "#8e939c", "#a5aab2"),
}
DEFAULT_LIVERY = "Turbo orange"
DEFAULT_LIVERIES = dict(LIVERIES)


def hex_rgba(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


def apply_livery(name):
    """Swap the palette globals; renderers built afterwards paint in the new colours."""
    global ORANGE, C_ORANGE, C_ORANGE_D, C_SUIT, C_HELM
    accent, shade, suit, helmet = LIVERIES.get(name) or next(iter(LIVERIES.values()))
    ORANGE = accent
    C_ORANGE, C_ORANGE_D, C_SUIT, C_HELM = map(hex_rgba, (accent, shade, suit, helmet))


def _font(size):
    for name in ("arialbd.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


def smooth(pts, n=6):
    """Closed Catmull-Rom spline through pts."""
    out, m = [], len(pts)
    for i in range(m):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[(i + 1) % m], pts[(i + 2) % m]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(tuple(
                0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                       + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in (0, 1)))
    return out


def capsule(p1, p2, r1, r2, n=10):
    (x1, y1), (x2, y2) = p1, p2
    a = math.atan2(y2 - y1, x2 - x1)
    pts = [(x2 + math.cos(a - math.pi / 2 + math.pi * k / n) * r2,
            y2 + math.sin(a - math.pi / 2 + math.pi * k / n) * r2) for k in range(n + 1)]
    pts += [(x1 + math.cos(a + math.pi / 2 + math.pi * k / n) * r1,
             y1 + math.sin(a + math.pi / 2 + math.pi * k / n) * r1) for k in range(n + 1)]
    return pts


class Painter:
    """Draws in 1x coordinates onto an SS x RGBA layer."""

    def __init__(self, w=SW, h=SH):
        self.w, self.h = w, h
        self.img = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    def new(self):
        return Painter(self.w, self.h)

    def poly(self, pts, fill=None, outline=None, width=0):
        P = [(x * SS, y * SS) for x, y in pts]
        if fill is not None:
            self.d.polygon(P, fill=fill)
        if outline is not None and width:
            self.d.line(P + P[:2], fill=outline, width=max(1, round(width * SS)), joint="curve")

    def ellipse(self, cx, cy, rx, ry, fill=None, outline=None, width=0):
        box = [(cx - rx) * SS, (cy - ry) * SS, (cx + rx) * SS, (cy + ry) * SS]
        if outline is not None and width:
            self.d.ellipse(box, fill=fill, outline=outline, width=max(1, round(width * SS)))
        else:
            self.d.ellipse(box, fill=fill)

    def rrect(self, x1, y1, x2, y2, r, fill=None, outline=None, width=0):
        r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
        box = [x1 * SS, y1 * SS, x2 * SS, y2 * SS]
        if outline is not None and width:
            self.d.rounded_rectangle(box, radius=r * SS, fill=fill, outline=outline, width=max(1, round(width * SS)))
        else:
            self.d.rounded_rectangle(box, radius=r * SS, fill=fill)

    def line(self, pts, fill, width, caps=True):
        P = [(x * SS, y * SS) for x, y in pts]
        w = max(1, round(width * SS))
        self.d.line(P, fill=fill, width=w, joint="curve")
        if caps:
            r = w / 2
            for x, y in (P[0], P[-1]):
                self.d.ellipse([x - r, y - r, x + r, y + r], fill=fill)

    def arc(self, cx, cy, rx, ry, start, end, fill, width):
        box = [(cx - rx) * SS, (cy - ry) * SS, (cx + rx) * SS, (cy + ry) * SS]
        self.d.arc(box, start, end, fill=fill, width=max(1, round(width * SS)))

    def text(self, x, y, s, size, fill):
        self.d.text((x * SS, y * SS), s, font=_font(int(size * SS)), fill=fill, anchor="mm")

    def mask(self):
        return self.img.getchannel("A")

    def comp(self, other, clip=None, blur=0):
        im = other.img
        if blur:
            im = im.filter(ImageFilter.GaussianBlur(blur * SS))
        if clip is not None:
            im = im.copy()
            im.putalpha(ImageChops.multiply(im.getchannel("A"), clip))
        self.img.alpha_composite(im)

    def final(self):
        return self.img.resize((self.w, self.h), Image.LANCZOS)


class LRU(OrderedDict):
    def __init__(self, size):
        super().__init__()
        self.size = size

    def get_or(self, key, fn):
        if key in self:
            self.move_to_end(key)
            return self[key]
        val = self[key] = fn()
        if len(self) > self.size:
            self.popitem(last=False)
        return val


class Renderer:
    def __init__(self):
        self.layers = LRU(400)
        self.frames = LRU(160)

    # ---------------------------------------------------------- shared parts
    def glove(self, p, hand, elbow, thumb=False):
        ux, uy = hand[0] - elbow[0], hand[1] - elbow[1]
        L = math.hypot(ux, uy) or 1
        ux, uy = ux / L, uy / L
        cuff = (hand[0] - ux * 4, hand[1] - uy * 4)
        fist = (hand[0] + ux * 2, hand[1] + uy * 2)
        p.ellipse(*cuff, 7.4, 7.4, fill=C_ORANGE_D, outline=C_OUT, width=1.3)
        if thumb:
            p.poly(capsule((fist[0] - 1, fist[1] - 3), (fist[0] - 1, fist[1] - 14), 5.2, 4.9), fill=C_OUT)
        p.ellipse(*fist, 9.2, 8.6, fill=C_OUT)
        p.ellipse(*fist, 8.0, 7.4, fill=(24, 24, 29, 255))
        if thumb:
            p.poly(capsule((fist[0] - 1, fist[1] - 3), (fist[0] - 1, fist[1] - 14), 3.9, 3.6), fill=(24, 24, 29, 255))
            p.line([(fist[0] - 1, fist[1] - 7), (fist[0] - 1, fist[1] - 12)], fill=C_ORANGE, width=1.8)
        kn = p.new()
        kn.ellipse(fist[0], fist[1] - 2.5, 6.5, 3.2, fill=C_ORANGE)
        kn.ellipse(fist[0] - 3, fist[1] - 4, 2.5, 1.5, fill=(255, 255, 255, 90))
        m = p.new()
        m.ellipse(*fist, 8.0, 7.4, fill=(255, 255, 255, 255))
        p.comp(kn, clip=m.mask())

    def arm(self, p, shoulder, hand, side, thumb=False):
        mx, my = (shoulder[0] + hand[0]) / 2, (shoulder[1] + hand[1]) / 2
        elbow = (mx + side * 4, my)
        p.poly(capsule(shoulder, elbow, 8.5, 7.5), fill=C_OUT)
        p.poly(capsule(elbow, hand, 7.5, 6.8), fill=C_OUT)
        s = p.new()
        s.poly(capsule(shoulder, elbow, 7.2, 6.2), fill=C_SUIT)
        s.poly(capsule(elbow, hand, 6.2, 5.5), fill=C_SUIT)
        mask = s.mask()
        det = p.new()
        det.line([(shoulder[0] + side * 5, shoulder[1]), (elbow[0] + side * 5, elbow[1]),
                  (hand[0] + side * 4.5, hand[1])], fill=C_ORANGE, width=2.2)
        hl = p.new()
        hl.line([(shoulder[0] - 3, shoulder[1]), (elbow[0] - 3, elbow[1])], fill=(255, 255, 255, 45), width=3)
        p.comp(s)
        p.comp(det, clip=mask)
        p.comp(hl, clip=mask, blur=1.5)
        self.glove(p, hand, elbow, thumb)

    # ---------------------------------------------------------- body layer
    def body(self, pose, ph, d):
        return self.layers.get_or(("body", pose, ph, d), lambda: self._body(pose, ph, d))

    def _body(self, pose, ph, d):
        p = Painter()
        cx, F, hipy = SCX, SF, 204
        a = ph / 8 * 2 * math.pi
        legs = []
        for s in (-1, 1):
            hip = (cx + s * 11, hipy)
            if pose == "walk":
                ang = math.sin(a) * 0.45 * s
                lift = max(0.0, math.sin(a) * s) * 5
                ankle = (hip[0] + math.sin(ang) * d * 22, hipy + math.cos(ang) * 22 - lift)
            elif pose == "air":
                ankle = (hip[0] + s * 6, hipy + 22)
            else:
                ankle = (hip[0] + s * 1, hipy + 23)
            legs.append((s, hip, ankle))

        torso = smooth([(cx - 13, 143), (cx - 24, 149), (cx - 29, 160), (cx - 27, 182), (cx - 24, 196),
                        (cx - 25, 207), (cx, 213), (cx + 25, 207), (cx + 24, 196), (cx + 27, 182),
                        (cx + 29, 160), (cx + 24, 149), (cx + 13, 143)])

        # left arm first (behind the body)
        if pose == "air":
            lh = (cx - 46, 128)
        else:
            lh = (cx - 34, 196 + (math.sin(a) * 6 if pose == "walk" else 0))
        self.arm(p, (cx - 23, 156), lh, -1)

        # one-piece suit: shared outline, then fill
        p.poly(torso, fill=C_OUT, outline=C_OUT, width=2.6)
        for s, hip, ankle in legs:
            p.poly(capsule(hip, ankle, 10.3, 8.8), fill=C_OUT)
        suit = p.new()
        suit.poly(torso, fill=C_SUIT)
        for s, hip, ankle in legs:
            suit.poly(capsule(hip, ankle, 9.0, 7.5), fill=C_SUIT)
        mask = suit.mask()
        p.comp(suit)

        det = p.new()
        for s, hip, ankle in legs:          # knee stretch panels
            kx, ky = hip[0] + (ankle[0] - hip[0]) * 0.55, hip[1] + (ankle[1] - hip[1]) * 0.55
            det.ellipse(kx, ky, 5.5, 4.2, fill=(38, 39, 47, 255))
        for s in (-1, 1):                   # waist stretch ribs
            for y in (189, 192.5, 196):
                det.line([(cx + s * 25, y), (cx + s * 16, y)], fill=(48, 49, 58, 255), width=1.2, caps=False)
        for s, hip, ankle in legs:          # side stripe: armpit -> ankle
            det.line([(cx + s * 26.5, 156), (cx + s * 26.5, 180), (cx + s * 23.5, 198),
                      (hip[0] + s * 7.6, hip[1] + 3), (ankle[0] + s * 6.2, ankle[1])],
                     fill=C_ORANGE, width=3.4)
        det.line([(cx, 150), (cx, 200)], fill=(62, 63, 72, 255), width=1.6)       # zipper
        det.rrect(cx - 1.8, 150, cx + 1.8, 157, 1, fill=(150, 155, 165, 255))
        for i in range(3):                  # chequered chest patch
            for j in range(2):
                col = C_ORANGE if (i + j) % 2 == 0 else (12, 12, 14, 255)
                det.rrect(cx + 9 + i * 4, 161 + j * 4, cx + 13 + i * 4, 165 + j * 4, 0.5, fill=col)
        det.rrect(cx - 22, 162, cx - 10, 167, 2, fill=(215, 218, 226, 255))        # badge
        det.line([(cx - 20, 164.5), (cx - 12, 164.5)], fill=C_ORANGE, width=1.2)
        p.comp(det, clip=mask)

        shade = p.new()
        shade.ellipse(cx + 27, 186, 13, 44, fill=(0, 0, 0, 120))
        shade.ellipse(cx, 216, 7, 10, fill=(0, 0, 0, 140))
        p.comp(shade, clip=mask, blur=5)
        hl = p.new()
        hl.ellipse(cx - 11, 168, 12, 24, fill=(255, 255, 255, 38))
        for s, hip, ankle in legs:
            hl.line([(hip[0] - 4, hip[1] + 2), (ankle[0] - 4, ankle[1] - 2)], fill=(255, 255, 255, 26), width=4)
        p.comp(hl, clip=mask, blur=4)

        # epaulettes + collar
        for s in (-1, 1):
            p.line([(cx + s * 13, 147.5), (cx + s * 25, 152)], fill=C_OUT, width=4.6)
            p.line([(cx + s * 13, 147.5), (cx + s * 25, 152)], fill=C_ORANGE, width=2.6)
        p.rrect(cx - 16, 138, cx + 16, 150, 5, fill=C_ORANGE, outline=C_OUT, width=1.3)

        # ankle cuffs + boots
        for s, hip, ankle in legs:
            bx, by = ankle[0] + d * 3, ankle[1] + 8
            p.rrect(ankle[0] - 8, ankle[1] - 2.5, ankle[0] + 8, ankle[1] + 3, 2,
                    fill=C_ORANGE, outline=C_OUT, width=1.2)
            p.ellipse(bx, by, 13.6, 8.8, fill=C_OUT)
            boot = p.new()
            boot.ellipse(bx, by, 12.3, 7.5, fill=(22, 22, 27, 255))
            bm = boot.mask()
            p.comp(boot)
            bd = p.new()
            bd.ellipse(bx + d * 10, by, 7, 9, fill=C_ORANGE)
            bd.ellipse(bx - d * 12, by - 2, 4, 6, fill=C_ORANGE)
            bd.line([(bx - 13, by + 6.2), (bx + 13, by + 6.2)], fill=(70, 72, 82, 255), width=2.4, caps=False)
            bd.ellipse(bx - d * 2, by - 4, 5, 2, fill=(255, 255, 255, 60))
            p.comp(bd, clip=bm)
        return p.final()

    # ---------------------------------------------------------- right arm layer
    def rarm(self, pose, ph):
        return self.layers.get_or(("rarm", pose, ph), lambda: self._rarm(pose, ph))

    def _rarm(self, pose, ph):
        p = Painter()
        cx = SCX
        a = ph / 8 * 2 * math.pi
        sh = (cx + 23, 156)
        if pose == "air":
            self.arm(p, sh, (cx + 46, 128), 1)
        elif pose == "thumb":
            self.arm(p, sh, (cx + 45, 150), 1, thumb=True)
        elif pose == "flag":
            hand = (cx + 44, 134)
            self.flag(p, hand, a)
            self.arm(p, sh, hand, 1)
        else:
            self.arm(p, sh, (cx + 34, 196 - math.sin(a) * 6), 1)
        return p.final()

    def flag(self, p, hand, a):
        hx, hy = hand
        top = (hx + 4, hy - 66)
        p.line([(hx, hy + 6), top], fill=C_OUT, width=4)
        p.line([(hx, hy + 6), top], fill=(200, 204, 212, 255), width=2.2)
        cell, cols, rows = 7.5, 5, 3
        wave = lambda c: math.sin(a - c * 0.9) * 3.2
        x0, y0 = top[0] + 1, top[1] + 1
        border = [(x0 + c * cell, y0 + wave(c)) for c in range(cols + 1)] + \
                 [(x0 + c * cell, y0 + rows * cell + wave(c)) for c in range(cols, -1, -1)]
        p.poly(border, fill=C_OUT, outline=C_OUT, width=2)
        for c in range(cols):
            for r in range(rows):
                col = C_WHITE if (r + c) % 2 == 0 else (17, 17, 20, 255)
                p.poly([(x0 + c * cell, y0 + r * cell + wave(c)), (x0 + (c + 1) * cell, y0 + r * cell + wave(c + 1)),
                        (x0 + (c + 1) * cell, y0 + (r + 1) * cell + wave(c + 1)),
                        (x0 + c * cell, y0 + (r + 1) * cell + wave(c))], fill=col)

    # ---------------------------------------------------------- helmet layer
    def helmet(self, mode, look, s, hcx, hcy):
        key = ("helmet", mode, look, s, hcx, hcy)
        return self.layers.get_or(key, lambda: self._helmet(mode, look, s, hcx, hcy))

    def _helmet(self, mode, look, s, cx, hy):
        p = Painter()
        rx, ry = 48 * s, 44 * s
        stripe = C_RED if mode == "angry" else C_ORANGE
        p.ellipse(cx, hy, rx + 1.8, ry + 1.8, fill=C_OUT)
        shell = p.new()
        shell.ellipse(cx, hy, rx, ry, fill=C_HELM)
        hm = shell.mask()
        p.comp(shell)

        st = p.new()                        # double racing stripe + cheek stripes
        st.ellipse(cx, hy - ry * 0.32, rx * 0.40, ry * 0.72, fill=stripe)
        st.ellipse(cx, hy - ry * 0.32, rx * 0.20, ry * 0.74, fill=C_HELM)
        for a0 in (122, 22):
            st.arc(cx, hy, rx - 5 * s, ry - 5 * s, a0, a0 + 36, fill=stripe, width=7 * s)
        st.arc(cx, hy, rx - 2 * s, ry - 2 * s, 62, 118, fill=stripe, width=5 * s)
        st.rrect(cx - 4 * s, hy - ry + 6 * s, cx + 4 * s, hy - ry + 15 * s, 2 * s, fill=(46, 47, 54, 255))
        p.comp(st, clip=hm)

        shade = p.new()
        shade.ellipse(cx + rx * 0.45, hy + ry * 0.45, rx * 0.7, ry * 0.6, fill=(0, 0, 0, 120))
        p.comp(shade, clip=hm, blur=7 * s)
        hl = p.new()
        hl.ellipse(cx - rx * 0.38, hy - ry * 0.55, rx * 0.36, ry * 0.2, fill=(255, 255, 255, 70))
        p.comp(hl, clip=hm, blur=4 * s)
        rim = p.new()
        rim.arc(cx, hy, rx - 2 * s, ry - 2 * s, 190, 250, fill=(255, 255, 255, 80), width=2 * s)
        p.comp(rim, clip=hm, blur=0.8 * s)

        # visor
        fx = look * 5 * s
        vx, vy = cx + fx, hy + ry * 0.25
        vrx, vry = rx * 0.82, ry * 0.51
        p.ellipse(vx, vy, vrx + 2.4 * s, vry + 2.4 * s, fill=(84, 90, 100, 255))
        p.ellipse(vx, vy, vrx + 1.0 * s, vry + 1.0 * s, fill=C_OUT)
        vis = p.new()
        vis.ellipse(vx, vy, vrx, vry, fill=C_VISOR)
        vm = vis.mask()
        p.comp(vis)

        eyes = p.new()
        ey = hy + ry * 0.24
        for side in (-1, 1):
            ex = vx + side * 16 * s
            ew, eh = 11 * s, 13 * s
            if mode == "happy":
                eyes.rrect(ex - ew, ey - eh, ex + ew, ey + eh, 7 * s, fill=C_WHITE)
                eyes.arc(ex, ey + eh * 0.55, ew * 0.72, eh * 0.62, 180, 360, fill=C_VISOR, width=3.6 * s)
            elif mode == "sleep":
                eyes.arc(ex, ey - eh * 0.2, ew * 0.8, eh * 0.55, 10, 170, fill=C_WHITE, width=3 * s)
            elif mode == "blink":
                eyes.rrect(ex - ew, ey - 1.8 * s, ex + ew, ey + 1.8 * s, 1.8 * s, fill=C_WHITE)
            elif mode == "angry":
                inner, outer = ex - side * ew, ex + side * ew
                eyes.poly(smooth([(outer, ey - eh * 0.75), (inner, ey - eh * 0.05), (inner, ey + eh * 0.85),
                                  (ex, ey + eh * 0.95), (outer, ey + eh * 0.85)], 4), fill=C_WHITE)
            elif mode == "surprised":
                eyes.rrect(ex - ew * 1.15, ey - eh * 1.15, ex + ew * 1.15, ey + eh * 1.15, 9 * s, fill=C_WHITE)
                eyes.ellipse(ex, ey, 3 * s, 3 * s, fill=C_VISOR)
            else:
                eyes.rrect(ex - ew, ey - eh, ex + ew, ey + eh, 7 * s, fill=C_WHITE)
        p.comp(eyes, clip=vm)
        glare = p.new()
        glare.poly([(vx - vrx * 0.1, vy - vry), (vx + vrx * 0.2, vy - vry), (vx - vrx * 0.35, vy + vry),
                    (vx - vrx * 0.62, vy + vry)], fill=(255, 255, 255, 34))
        glare.arc(vx, vy, vrx - 2 * s, vry - 2 * s, 200, 330, fill=(190, 205, 225, 110), width=2 * s)
        p.comp(glare, clip=vm, blur=0.8 * s)

        for side in (-1, 1):                # visor hinge bolts
            bx, by = cx + side * rx * 0.87, hy + ry * 0.2
            p.ellipse(bx, by, 5 * s, 5 * s, fill=C_OUT)
            p.ellipse(bx, by, 3.8 * s, 3.8 * s, fill=(70, 75, 84, 255))
            p.ellipse(bx - 1 * s, by - 1 * s, 1.5 * s, 1.5 * s, fill=(170, 176, 186, 255))
        return p.final()

    # ---------------------------------------------------------- car layers
    def car(self, d, wph):
        return self.layers.get_or(("car", d, wph), lambda: self._car(d, wph))

    def _car(self, d, wph):
        p = Painter()
        F = SF
        X = lambda lx: SCX + d * lx
        P = lambda pts: [(X(lx), F + ly) for lx, ly in pts]
        # rear wing
        p.line(P([(-64, -60), (-58, -40)]), fill=C_OUT, width=5)
        p.poly(P([(-94, -76), (-60, -76), (-60, -64), (-94, -62)]), fill=C_SUIT, outline=C_OUT, width=2)
        p.line(P([(-94, -64), (-60, -66)]), fill=C_ORANGE, width=2.4)
        p.poly(P([(-96, -82), (-88, -82), (-88, -50), (-96, -50)]), fill=C_ORANGE, outline=C_OUT, width=1.8)
        # airbox / engine cover
        p.poly(smooth(P([(-60, -40), (-40, -60), (-28, -62), (-20, -48)]), 5), fill=C_SUIT, outline=C_OUT, width=2)
        # main body
        body = smooth(P([(-74, -20), (-72, -40), (-44, -48), (-18, -48), (-8, -44), (24, -42),
                         (64, -31), (90, -22), (84, -16), (-74, -16)]), 5)
        p.poly(body, fill=C_OUT, outline=C_OUT, width=2.6)
        b = p.new()
        b.poly(body, fill=C_SUIT)
        bm = b.mask()
        p.comp(b)
        det = p.new()
        det.ellipse(X(-30), F - 29, 28, 11, fill=(36, 37, 45, 255))           # sidepod
        det.line(P([(-70, -33), (-20, -37), (26, -36), (74, -24)]), fill=C_ORANGE, width=4)
        det.line(P([(-60, -24), (-6, -26)]), fill=C_ORANGE_D, width=2)
        det.ellipse(X(8), F - 29, 8.5, 8.5, fill=C_WHITE)
        p.comp(det, clip=bm)
        hl = p.new()
        hl.line(P([(-68, -42), (-20, -46), (30, -40), (70, -29)]), fill=(255, 255, 255, 60), width=3)
        p.comp(hl, clip=bm, blur=2)
        p.text(X(8), F - 29, "26", 9, (15, 15, 18, 255))
        # front wing + plank
        p.poly(P([(66, -13), (100, -13), (102, -6), (60, -6)]), fill=C_ORANGE, outline=C_OUT, width=1.8)
        p.poly(P([(98, -20), (104, -20), (104, -5), (98, -5)]), fill=C_SUIT, outline=C_OUT, width=1.5)
        # wheels
        for wx, r in ((-48, 17), (56, 15)):
            x0, y0 = X(wx), F - r
            p.ellipse(x0, y0, r + 1.5, r + 1.5, fill=C_OUT)
            p.ellipse(x0, y0, r, r, fill=(20, 20, 24, 255))
            p.ellipse(x0, y0, r * 0.72, r * 0.72, fill=(44, 45, 52, 255))
            p.ellipse(x0, y0, r * 0.52, r * 0.52, fill=C_ORANGE)
            p.ellipse(x0, y0, r * 0.38, r * 0.38, fill=(30, 30, 36, 255))
            for k in range(5):
                ang = wph / 4 * (2 * math.pi / 5) * d + k * 2 * math.pi / 5
                p.line([(x0, y0), (x0 + math.cos(ang) * r * 0.5, y0 + math.sin(ang) * r * 0.5)],
                       fill=C_ORANGE, width=2)
            p.ellipse(x0, y0, 2.2, 2.2, fill=(190, 195, 205, 255))
            tl = p.new()
            tl.arc(x0, y0, r - 1.5, r - 1.5, 200, 260, fill=(255, 255, 255, 70), width=1.6)
            p.comp(tl)
        return p.final()

    def car_front(self, d):
        return self.layers.get_or(("carfront", d), lambda: self._car_front(d))

    def _car_front(self, d):
        p = Painter()
        X = lambda lx: SCX + d * lx
        F = SF
        # arm to the steering wheel + cockpit rim in front of the driver
        p.line([(X(-8), F - 50), (X(12), F - 52)], fill=C_OUT, width=9)
        p.line([(X(-8), F - 50), (X(12), F - 52)], fill=C_SUIT, width=6.5)
        p.ellipse(X(13), F - 52, 5.6, 5.6, fill=C_OUT)
        p.ellipse(X(13), F - 52, 4.4, 4.4, fill=C_ORANGE)
        p.line([(X(-34), F - 46), (X(6), F - 45)], fill=C_OUT, width=6)
        p.line([(X(-34), F - 46), (X(6), F - 45)], fill=(40, 41, 49, 255), width=3.5)
        return p.final()

    def warm_list(self):
        jobs = []
        for mode in ("open", "blink", "happy", "surprised", "angry", "sleep"):
            for look in (0.0, -0.5, 0.5, -1.0, 1.0):
                jobs.append(lambda m=mode, lk=look: self.helmet(m, lk, 1.0, SCX, SHY))
        for d in (1, -1):
            jobs.append(lambda d=d: self.body("stand", 0, d))
            jobs.append(lambda d=d: self.body("air", 0, d))
            for ph in range(8):
                jobs.append(lambda d=d, ph=ph: self.body("walk", ph, d))
        for arm in ("down", "flag"):
            for ph in range(8):
                jobs.append(lambda a=arm, ph=ph: self.rarm(a, ph))
        jobs += [lambda: self.rarm("thumb", 0), lambda: self.rarm("air", 0)]
        for d in (1, -1):
            for mode in ("open", "blink", "happy"):
                jobs.append(lambda d=d, m=mode: self.helmet(m, d, 0.72, SCX - d * 12, SF - 76))
            jobs.append(lambda d=d: self.car_front(d))
            for w in range(4):
                jobs.append(lambda d=d, w=w: self.car(d, w))
                for mode in ("open", "blink", "happy"):
                    jobs.append(lambda d=d, w=w, m=mode: self.frame(("car", d, w, m)))
        return jobs

    # ---------------------------------------------------------- frame assembly
    def frame(self, spec):
        return self.frames.get_or(spec, lambda: ImageTk.PhotoImage(self._frame(spec)))

    def _frame(self, spec):
        base = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
        if spec[0] == "car":
            _, d, wph, mode = spec
            base.alpha_composite(self.car(d, wph))
            base.alpha_composite(self.helmet(mode, d, 0.72, SCX - d * 12, SF - 76))
            base.alpha_composite(self.car_front(d))
        else:
            _, pose, ph, d, mode, look, arm, aph, sq = spec
            base.alpha_composite(self.body(pose, ph, d))
            base.alpha_composite(self.helmet(mode, look, 1.0, SCX, SHY), dest=(0, sq))
            base.alpha_composite(self.rarm(arm, aph))
        # flatten against the dark outline colour, then hard-cut to the colour key
        flat = Image.alpha_composite(Image.new("RGBA", (SW, SH), (10, 10, 12, 255)), base).convert("RGB")
        cut = base.getchannel("A").point(lambda a: 255 if a >= 100 else 0)
        out = Image.new("RGB", (SW, SH), KEY_RGB)
        out.paste(flat, (0, 0), cut)
        return out


class Pet:
    def __init__(self):
        self.root = root = tk.Tk()
        root.title(NAME)
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        try:
            root.attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            pass
        root.config(bg=TRANSPARENT)

        self.canvas = tk.Canvas(root, width=W, height=H, bg=TRANSPARENT, highlightthickness=0)
        self.canvas.pack()

        self.left, self.top, self.right, self.bottom = work_area(root)
        self.ground_y = self.bottom - FOOT - 2

        # position / physics
        self.x = random.randint(self.left, max(self.left, self.right - W))
        self.y = self.top - CEILING
        self.vx = self.vy = 0.0
        self.dir = 1
        self.target_x = self.x
        self.squash = 0.0
        self.wheel_rot = 0.0
        self.puffs = []                # exhaust smoke: [x, y, age]

        # state
        self.t = 0
        self.state = "fall"            # idle | walk | drive | sleep | drag | fall
        self.state_until = 0
        self.blink_until = 0
        self.happy_until = 0
        self.thumb_until = 0
        self.flag_until = 0
        self.angry_until = 0
        self.bubble_text = ""
        self.bubble_until = 0
        self.pokes = []
        self.last_interaction = time.time()
        self.next_chat = time.time() + random.uniform(40, 90)

        # racing features
        self.stats = load_stats()
        saved = self.stats.get("liveries")
        if isinstance(saved, dict) and saved and all(
                isinstance(v, list) and len(v) == 4 and all(HEX_COLOUR.match(str(x)) for x in v)
                for v in saved.values()):
            LIVERIES.clear()
            LIVERIES.update((str(k), tuple(v)) for k, v in saved.items())
        livery = self.stats.get("livery", DEFAULT_LIVERY)
        self.livery_var = tk.StringVar(value=livery if livery in LIVERIES else next(iter(LIVERIES)))
        apply_livery(self.livery_var.get())
        self.garage = Garage(self)
        self.fs_panel = FSResults(self)
        self.telemetry = Telemetry(self)
        self.started = time.time()
        self.frames = 0                # frames drawn, for the telemetry FPS
        self.frame_ms = 0.0            # smoothed update + draw time
        self.lights = None             # start-light reaction test
        self.sw = None                 # stopwatch

        # mouse
        self.press_pos = None
        self.grab_off = (0, 0)
        self.dragging = False

        # helpers
        self.renderer = Renderer()
        self._photo = None
        self.pit_var = tk.BooleanVar(value=False)
        self.pit_job = None
        self.sound = Sound(self.stats.get("sound", True))
        self.sound_var = tk.BooleanVar(value=self.sound.enabled)
        self.voice_var = tk.BooleanVar(value=self.stats.get("voice", True))
        follow = self.stats.get("follow", [])
        self.follow = {k: tk.BooleanVar(value=k in follow) for k in ("f1", "motogp", "fs")}
        self.board = None              # results board on screen: {"title", "lines", "until", ...}
        self.boards = []               # boards waiting their turn
        self.jobs = queue.Queue()      # finished background fetches: (callback, result)
        self.pending = 0               # fetches still running
        self.reading = None            # time an answer was asked for; Turbo stays parked meanwhile
        self.build_menu()

        c = self.canvas
        c.bind("<ButtonPress-1>", self.on_press)
        c.bind("<B1-Motion>", self.on_motion)
        c.bind("<ButtonRelease-1>", self.on_release)
        c.bind("<Button-3>", self.on_menu)
        c.bind("<MouseWheel>", self.on_wheel)

        root.geometry(f"{W}x{H}+{int(self.x)}+{int(self.y)}")
        root.after(2000, lambda: self.say(self.greeting(), happy=True))
        self.warm_jobs = self.renderer.warm_list()
        root.after(300, self.warm)
        root.after(20_000, self.check_leagues)
        if winsound is not None:
            root.after(5_000, self.prepare_radio)
        self.last_frame = time.perf_counter()
        self.speed_k = 0.0             # 0..1 ease-in / ease-out for walking and driving
        self.puff_acc = 0.0
        try:
            import ctypes
            ctypes.windll.winmm.timeBeginPeriod(1)
        except (AttributeError, OSError):
            pass
        self.loop()

    # ------------------------------------------------------------ talking
    def greeting(self):
        h = time.localtime().tm_hour
        part = "Good morning" if h < 12 else "Good afternoon" if h < 18 else "Good evening"
        return f"{part}! {NAME} here, ready to race. Right-click me!"

    def say(self, text, happy=False, secs=None):
        now = time.time()
        self.bubble_text = text
        self.bubble_until = now + (secs or max(2.5, len(text) / 12))
        if happy:
            self.happy_until = now + 3
            self.thumb_until = now + 2.5
        self.speak(text)

    def speak(self, text):
        """Read a bubble aloud as team radio (not while the engine is running)."""
        if not (self.voice_var.get() and self.sound.enabled) or self.state == "drive"                 or self.sound.current in ("rev", "engine"):
            return

        def done(res):
            if not isinstance(res, Exception) and self.bubble_text == text and time.time() < self.bubble_until:
                self.sound.play_file(res)
        self.fetch_bg(lambda: radio_voice(text), done)

    def toggle_voice(self):
        self.stats["voice"] = self.voice_var.get()
        save_stats(self.stats)
        self.say("Radio check: loud and clear." if self.voice_var.get() else "Going radio silent.")

    def celebrate(self, secs=4):
        now = time.time()
        self.sound.play("chime")
        self.flag_until = now + secs
        self.happy_until = now + secs

    # ------------------------------------------------------------ menu
    def build_menu(self):
        racing = [
            ("cmd", "Start lights reaction test", self.start_lights),
            ("cmd", "Stopwatch: start / lap", self.sw_lap),
            ("cmd", "Stopwatch: stop", self.sw_stop),
            ("cmd", "Go for a drive", self.start_drive),
            ("cmd", "Racing fact", self.racing_fact),
            ("cmd", "Famous team radio", lambda: self.radio(random.choice(MEME_RADIO))),
            ("cmd", "My records", self.show_records),
        ]
        fs = [
            ("cmd", "World ranking: EV", lambda: self.show_result(lambda: fs_ranking("ev", self.fs_team()))),
            ("cmd", "World ranking: CV", lambda: self.show_result(lambda: fs_ranking("cv", self.fs_team()))),
            ("cmd", "World ranking: Driverless", lambda: self.show_result(lambda: fs_ranking("dc", self.fs_team()))),
            ("sep",),
            ("cmd", "Competition results...", self.fs_panel.open),
            ("cmd", "My followed competition", self.fs_followed),
            ("sep",),
            ("cmd", "My team's ranking", self.fs_team_ranking),
            ("cmd", "Set my team...", self.ask_fs_team),
        ]
        show = lambda fn, *args: (lambda: self.show_result(lambda: fn(*args)))
        f1 = [
            ("cmd", "Last race", show(f1_last_race)),
            ("cmd", "Drivers' championship", show(f1_standings)),
            ("cmd", "Teams' championship", show(f1_constructors)),
            ("cmd", "Next race", show(f1_next_race)),
        ]
        feeder = lambda key: [
            ("cmd", "Drivers' championship", show(feeder_standings, key)),
            ("cmd", "Teams' championship", show(feeder_standings, key, True)),
        ]
        motogp = [
            ("cmd", "Last race", show(motogp_last_race)),
            ("cmd", "Riders' championship", show(motogp_standings)),
            ("cmd", "Teams' championship", show(motogp_standings, True)),
        ]
        wec = [("cmd", label, show(wec_standings, key)) for key, label in WEC_TABLES.items()]
        results = [
            ("sub", "Formula 1", f1),
            ("sub", "Formula 2", feeder("f2")),
            ("sub", "Formula 3", feeder("f3")),
            ("sub", "MotoGP", motogp),
            ("sub", "WEC", wec),
            ("sub", "Formula Student", fs),
            ("sep",),
            ("cmd", "Latest from my leagues", self.my_leagues),
            ("check", "Follow F1", self.follow["f1"], self.save_follow),
            ("check", "Follow MotoGP", self.follow["motogp"], self.save_follow),
            ("check", "Follow Formula Student", self.follow["fs"], self.save_follow),
        ]
        self.menu = RaceMenu(self.root, [
            ("sub", "Racing", racing),
            ("sub", "Live results", results),
            ("cmd", "Tell me a joke", self.joke),
            ("cmd", "What time is it?", self.tell_time),
            ("cmd", "Telemetry console", self.telemetry.open),
            ("sep",),
            ("cmd", "Set a timer...", self.ask_timer),
            ("check", "Pit stop reminders (45 min)", self.pit_var, self.toggle_pit),
            ("check", "Sound effects", self.sound_var, self.toggle_sound),
            ("check", "Voice (read bubbles aloud)", self.voice_var, self.toggle_voice),
            ("sub", "Livery colours", self.livery_items),
            ("sep",),
            ("cmd", "Jump!", self.jump),
            ("cmd", "Take a nap / wake up", self.toggle_sleep),
            ("sep",),
            ("cmd", "Goodbye", self.quit),
        ], on_pick=self.start_reading)

    def start_reading(self):
        """Something was asked: park until the answer has been shown and read."""
        self.reading = time.time()

    def on_menu(self, event):
        self.last_interaction = time.time()
        self.menu.popup(event.x_root, event.y_root)

    def tell_time(self):
        self.say(time.strftime("It's %H:%M. ") + random.choice(
            ["Time flies!", "Still time for a few laps.", "Just saying.", "Coffee o'clock?"]))

    def show_records(self):
        rt = self.stats.get("best_reaction")
        lap = self.stats.get("best_lap")
        self.say("Records -- reaction: " + (f"{rt:.3f} s" if rt else "none yet") +
                 ", best lap: " + (fmt_time(lap) if lap else "none yet"), secs=6)

    def ask_timer(self):
        ans = simpledialog.askstring(
            f"{NAME}'s timer", "Minutes and an optional message\n(e.g.  10 tea is ready)", parent=self.root)
        if not ans:
            return
        parts = ans.strip().split(maxsplit=1)
        try:
            minutes = float(parts[0].replace(",", "."))
        except ValueError:
            self.say("Hmm, I need a number of minutes first.")
            return
        msg = parts[1] if len(parts) > 1 else "Time's up!"
        self.root.after(int(minutes * 60_000), lambda: self.alarm(msg))
        self.say(f"Copy. Reminder in {minutes:g} min.", happy=True)

    def alarm(self, msg):
        self.wake()
        self.root.bell()
        self.say("Chequered flag! " + msg, secs=12)
        self.celebrate(8)
        self.jump()
        self.root.after(900, self.jump)

    def toggle_pit(self):
        if self.pit_job:
            self.root.after_cancel(self.pit_job)
            self.pit_job = None
        if self.pit_var.get():
            self.say("I'll call you into the pits every 45 minutes!", happy=True)
            self.schedule_pit()
        else:
            self.say("OK, no more pit calls.")

    def toggle_sound(self):
        on = self.sound_var.get()
        if not on:
            self.sound.stop()
        self.sound.enabled = on and winsound is not None
        self.stats["sound"] = on
        save_stats(self.stats)
        self.say("Engine sounds on. Vroom!" if on else "Going silent. Stealth mode.")

    def schedule_pit(self):
        self.pit_job = self.root.after(45 * 60_000, self.pit_reminder)

    def pit_reminder(self):
        self.wake()
        self.root.bell()
        self.say(random.choice(["BOX BOX! Pit stop: stand up and stretch.",
                                "Box this lap: grab some water!",
                                "Pit window open: look away from the screen for 20 s."]), secs=10)
        self.jump()
        self.schedule_pit()

    def toggle_sleep(self):
        if self.state == "sleep":
            self.wake()
            self.say("I'm up, I'm up!")
        else:
            self.go_sleep()

    def quit(self):
        self.say("Bye bye! See you on track.")
        self.state = "idle"
        self.state_until = time.time() + 10
        self.sound.stop()
        self.root.after(1500, self.root.destroy)

    # ------------------------------------------------------------ live data
    def fetch_bg(self, fn, done, busy=None):
        """Run fn() on a worker thread; done(result or exception) runs on the Tk thread."""
        if busy:
            self.say(busy, secs=4)

        def work():
            try:
                res = fn()
            except Exception as e:     # offline, API changed... never crash the pet
                res = e
            self.jobs.put((done, res))
        self.pending += 1
        threading.Thread(target=work, daemon=True).start()

    def show_result(self, fn):
        self.fetch_bg(fn, self.got_board, "Checking the timing screens...")

    def got_board(self, res):
        if isinstance(res, Exception):
            self.say("No signal from the pit wall. Are we offline?")
            return
        self.bubble_until = 0
        self.show_board(res)

    def show_board(self, board):
        self.boards.append(board)
        self.happy_until = time.time() + 3

    def say_online(self, fn, fallback):
        """Say something fetched online, or a local line if the network is down."""
        def done(res):
            self.say(random.choice(fallback) if isinstance(res, Exception) else res, happy=True)
        self.fetch_bg(fn, done)

    def radio(self, line):
        """A famous team radio line: bubble plus voice (voice even if bubbles aren't read aloud)."""
        self.say(line, happy=True)
        if not self.voice_var.get() and self.sound.enabled:
            self.fetch_bg(lambda: radio_voice(line),
                          lambda res: None if isinstance(res, Exception) else self.sound.play_file(res))

    def prepare_radio(self):
        """Pre-render every radio line in the background so clicks speak instantly."""
        def work():
            for line in MEME_RADIO:
                try:
                    radio_voice(line)
                except Exception:
                    return          # no speech engine: stay silent, bubbles still work
        threading.Thread(target=work, daemon=True).start()

    def racing_fact(self):
        if random.random() < 0.5:
            self.say(random.choice(FACTS), happy=True)
        else:
            self.say_online(f1_history_fact, FACTS)

    def joke(self):
        if random.random() < 0.5:
            self.say(random.choice(JOKES), happy=True)
        else:
            self.say_online(online_joke, JOKES)

    def fs_team(self):
        return self.stats.get("fs_team", "")

    def ask_fs_team(self):
        ans = simpledialog.askstring(f"{NAME}'s pit wall", "Your Formula Student team or university\n"
                                     "(part of the name is fine, e.g.  Aalto)",
                                     initialvalue=self.fs_team(), parent=self.root)
        if ans is None:
            return False
        self.stats["fs_team"] = ans.strip()
        save_stats(self.stats)
        self.say(f"Go {ans.strip()}! I'll keep an eye on your ranking." if ans.strip()
                 else "OK, no favourite team.", happy=bool(ans.strip()))
        return bool(ans.strip())

    def fs_followed(self):
        pick = self.stats.get("fs_follow")
        if not pick:
            self.fs_panel.open()
            return
        team = self.fs_team()
        self.show_result(lambda: fs_board(fs_load(pick["cid"], pick["cls"]), pick["disc"], pick["name"], team))

    def fs_team_ranking(self):
        if self.fs_team() or self.ask_fs_team():
            team = self.fs_team()
            self.show_result(lambda: fs_my_team(team))

    def followed(self):
        team = self.fs_team()
        pick = self.stats.get("fs_follow")
        if pick:
            fs = lambda: fs_board(fs_load(pick["cid"], pick["cls"]), pick["disc"], pick["name"], team)
        else:
            fs = (lambda: fs_my_team(team)) if team else (lambda: fs_ranking("ev"))
        fns = {"f1": f1_last_race, "motogp": motogp_last_race, "fs": fs}
        return [(k, fns[k]) for k, var in self.follow.items() if var.get()]

    @staticmethod
    def collect(leagues):
        out = []
        for key, fn in leagues:
            try:
                out.append((key, fn()))
            except Exception:
                pass
        return out

    def save_follow(self):
        self.stats["follow"] = [k for k, var in self.follow.items() if var.get()]
        save_stats(self.stats)
        self.say("Copy, following " + ", ".join(
            {"f1": "F1", "motogp": "MotoGP", "fs": "Formula Student"}[k] for k in self.stats["follow"])
            + ". I'll shout when new results land!" if self.stats["follow"] else "Not following any leagues.")
        self.check_leagues(reschedule=False)

    def my_leagues(self):
        leagues = self.followed()
        if not leagues:
            self.say("Tick 'Follow ...' under Live results first!")
            return

        def done(res):
            if isinstance(res, Exception) or not res:
                self.say("No signal from the pit wall. Are we offline?")
                return
            self.bubble_until = 0
            for _, board in res:
                self.show_board(board)
        self.fetch_bg(lambda: self.collect(leagues), done, "Checking the timing screens...")

    def check_leagues(self, reschedule=True):
        """Every 30 min: announce results that are new since the last check."""
        if reschedule:
            self.root.after(30 * 60_000, self.check_leagues)
        leagues = self.followed()
        if leagues:
            self.fetch_bg(lambda: self.collect(leagues), self.got_league_news)

    def got_league_news(self, res):
        if isinstance(res, Exception):
            return
        seen = self.stats.setdefault("seen", {})
        fresh = [board for key, board in res if seen.get(key) not in (None, board["key"])]
        for key, board in res:
            seen[key] = board["key"]
        save_stats(self.stats)
        if fresh:
            self.wake()
            self.say("New results just in!", happy=True, secs=2)
            self.celebrate(3)
            for board in fresh:
                self.show_board(board)

    # ------------------------------------------------------------ racing features
    def start_lights(self):
        self.wake()
        if self.state not in ("idle", "walk", "drive"):
            return
        self.set_idle(60)
        now = time.time()
        self.lights = {"start": now + 0.8, "out": now + 0.8 + 5 * 0.9 + random.uniform(0.2, 2.5),
                       "beeps": 0}
        self.bubble_until = 0
        self.say("Click me when the lights go out!", secs=0.8)

    def lights_click(self, t_click):
        L, self.lights = self.lights, None
        self.set_idle()
        if t_click < L["out"]:
            self.say("JUMP START! That's a drive-through penalty.")
            self.sound.play("buzz")
            self.angry_until = time.time() + 2
            return
        rt = t_click - L["out"]
        if rt < 0.2:
            verdict = "Superhuman! Are you a bot?"
        elif rt < 0.25:
            verdict = "F1 driver pace!"
        elif rt < 0.35:
            verdict = "Solid start."
        elif rt < 0.5:
            verdict = "Bit sleepy off the line..."
        else:
            verdict = "Were you checking your phone?"
        msg = f"{rt:.3f} s - {verdict}"
        best = self.stats.get("best_reaction")
        if best is None or rt < best:
            self.stats["best_reaction"] = rt
            save_stats(self.stats)
            msg += " NEW RECORD!"
            self.celebrate()
        elif rt < 0.35:
            self.happy_until = time.time() + 3
            self.thumb_until = time.time() + 2.5
        self.say(msg, secs=5)

    def sw_lap(self, now=None):
        now = now or time.time()
        if not self.sw:
            self.sw = {"lap_start": now, "laps": []}
            self.say("Stopwatch running! Click me to set a lap.", happy=True)
            return
        lap = now - self.sw["lap_start"]
        laps = self.sw["laps"]
        laps.append(lap)
        self.sw["lap_start"] = now
        msg = f"Lap {len(laps)}: {fmt_time(lap)}"
        best_session = min(laps)
        if len(laps) > 1:
            if lap == best_session:
                msg += " - purple, best lap!"
                self.celebrate(3)
            else:
                msg += f" (+{lap - best_session:.3f})"
        best = self.stats.get("best_lap")
        if best is None or lap < best:
            self.stats["best_lap"] = lap
            save_stats(self.stats)
            if best is not None:
                msg += " ALL-TIME BEST!"
                self.celebrate()
        self.say(msg, secs=4)

    def sw_stop(self):
        if not self.sw:
            self.say("The stopwatch isn't running.")
            return
        laps, self.sw = self.sw["laps"], None
        if laps:
            self.say(f"Session over: {len(laps)} laps, best {fmt_time(min(laps))}.", happy=True, secs=5)
        else:
            self.say("Stopwatch stopped. No laps set.")

    def start_drive(self):
        self.reading = None
        self.wake()
        if self.state not in ("idle", "walk", "drive"):
            return
        mid = (self.left + self.right - W) / 2
        lo, hi = self.left, max(self.left, self.right - W)
        self.target_x = random.randint(lo, int(lo + (hi - lo) * 0.25)) if self.x > mid \
            else random.randint(int(lo + (hi - lo) * 0.75), hi)
        self.dir = 1 if self.target_x > self.x else -1
        self.state = "drive"
        self.say(random.choice(DRIVE_LINES), secs=2)
        self.sound.play("rev")
        self.root.after(Sound.REV_MS, self.engine_loop)

    def engine_loop(self):
        if self.state == "drive" and self.sound.current == "rev":
            self.sound.play("engine", loop=True)

    # ------------------------------------------------------------ states
    def ease(self, dt, brake):
        """Speed factor: ramps up from a standstill, slows down over the last `brake` px."""
        self.speed_k = min(1.0, self.speed_k + 0.07 * dt)
        start = 0.5 - 0.5 * math.cos(math.pi * self.speed_k)
        stop = min(1.0, abs(self.target_x - self.x) / brake) ** 0.6
        return max(0.12, min(start, stop))

    def set_idle(self, seconds=None):
        self.speed_k = 0.0
        self.state = "idle"
        self.vx = self.vy = 0
        self.state_until = time.time() + (seconds or random.uniform(3, 8))

    def pick_next(self):
        now = time.time()
        r = random.random()
        if now - self.last_interaction > 180 and r < 0.3:
            self.go_sleep()
        elif r < 0.45:
            self.state = "walk"
            self.target_x = random.randint(self.left, max(self.left, self.right - W))
            self.dir = 1 if self.target_x > self.x else -1
        elif r < 0.6:
            self.start_drive()
        else:
            self.set_idle()
            if random.random() < 0.25:
                self.thumb_until = now + 2
                self.happy_until = now + 2

    def go_sleep(self):
        self.state = "sleep"
        self.vx = self.vy = 0
        self.lights = None
        self.state_until = time.time() + random.uniform(60, 180)
        self.bubble_until = 0

    def wake(self):
        if self.state == "sleep":
            self.set_idle(2)

    def jump(self):
        if self.state in ("idle", "walk", "sleep", "drive"):
            self.sound.play("jump")
            self.state = "fall"
            self.vy = -12
            self.vx = random.choice([-2, 2])

    # ------------------------------------------------------------ mouse
    def on_press(self, e):
        now = time.time()
        self.last_interaction = now
        self.menu.close()
        if self.lights:
            self.lights_click(now)
            self.press_pos = None
            return
        if self.board and now < self.board["until"]:
            self.board["until"] = 0        # click dismisses the results board
            self.press_pos = None
            return
        self.press_time = now
        self.press_pos = (e.x_root, e.y_root)
        self.grab_off = (e.x_root - self.x, e.y_root - self.y)
        self.dragging = False

    def on_motion(self, e):
        if self.press_pos is None:
            return
        if not self.dragging:
            if math.hypot(e.x_root - self.press_pos[0], e.y_root - self.press_pos[1]) < 5:
                return
            self.dragging = True
            was_driving = self.state == "drive"
            self.state = "drag"
            self.say("Hey, my car!" if was_driving else random.choice(THROW_LINES))
        nx = e.x_root - self.grab_off[0]
        ny = e.y_root - self.grab_off[1]
        self.vx = 0.5 * self.vx + 0.5 * (nx - self.x)
        self.vy = 0.5 * self.vy + 0.5 * (ny - self.y)
        self.x, self.y = nx, ny

    def on_release(self, e):
        if self.press_pos is None:
            return
        if self.dragging:
            self.state = "fall"
            self.vx = max(-35, min(35, self.vx))
            if math.hypot(self.vx, self.vy) > 15:
                self.sound.play("whoosh")
            self.vy = max(-35, min(35, self.vy))
        elif self.sw and self.state != "sleep":
            self.sw_lap(self.press_time)
        else:
            self.poke()
        self.dragging = False
        self.press_pos = None

    def poke(self):
        now = time.time()
        if self.state == "sleep":
            self.wake()
            self.say(random.choice(["Huh?! Is it race day?", "Five more laps... I mean minutes.", "Zzz- what? Oh, hi."]))
            return
        if self.state == "drive":
            self.say("Hey, I'm driving here!")
            return
        self.pokes = [p for p in self.pokes if now - p < 8] + [now]
        if len(self.pokes) >= 5:
            self.angry_until = now + 8
            self.happy_until = self.thumb_until = 0
            self.say(random.choice(ANGRY_LINES))
            self.pokes = []
        elif now < self.angry_until:
            self.say("Hmph.")
        else:
            self.radio(random.choice(MEME_RADIO))
        if self.state in ("idle", "walk"):
            self.sound.play("poke")
            self.state = "fall"
            self.vy = -6
            self.vx = 0

    def livery_items(self):
        return [("radio", name, self.livery_var, name, self.set_livery, (c[0], c[2]))
                for name, c in LIVERIES.items()] + [("sep",), ("cmd", "Livery garage...", self.garage.open)]

    def save_liveries(self):
        self.stats["liveries"] = {k: list(v) for k, v in LIVERIES.items()}
        save_stats(self.stats)

    def set_livery(self, quiet=False):
        name = self.livery_var.get()
        apply_livery(name)
        idle = not self.warm_jobs
        self.renderer = Renderer()          # fresh caches, painted in the new colours
        self.warm_jobs = self.renderer.warm_list()
        if idle:
            self.warm()
        self.stats["livery"] = name
        save_stats(self.stats)
        if self.garage.win:
            self.garage.render()
        if not quiet:
            self.say(f"{name} livery! How do I look?", happy=True, secs=2.5)

    def warm(self):
        """Pre-render common poses in small chunks so first use never stutters."""
        if self.warm_jobs:
            if self.state in ("walk", "drive", "drag") or (self.state == "fall" and self.y < self.ground_y):
                self.root.after(150, self.warm)     # never stutter a moving Turbo
                return
            self.warm_jobs.pop(0)()
            self.root.after(15, self.warm)

    # ------------------------------------------------------------ main loop
    def loop(self):
        start = time.perf_counter()
        # dt in 30 fps ticks, so all speeds keep their old meaning at any frame rate
        self.dt = max(0.1, min(3.0, (start - self.last_frame) / TICK))
        self.last_frame = start
        try:
            self.update()
            self.draw()
        except tk.TclError:
            return  # window closed
        spent = (time.perf_counter() - start) * 1000
        self.frames += 1
        self.frame_ms += (spent - self.frame_ms) * 0.05
        self.root.after(max(1, int(FPS_MS - spent)), self.loop)

    def update(self):
        dt = self.dt
        self.t += dt
        now = time.time()

        while not self.jobs.empty():
            done, res = self.jobs.get()
            self.pending -= 1
            done(res)
        if self.boards and (not self.board or now > self.board["until"]):
            self.board = b = self.boards.pop(0)
            pages = math.ceil(len(b["lines"]) / BOARD_ROWS)
            b["off"], b["flip"] = 0, now + 7
            b["until"] = now + (15 if pages == 1 else 7 * pages + 3)
        b = self.board
        if b and now < b["until"] and len(b["lines"]) > BOARD_ROWS and now > b["flip"]:
            b["off"] = (b["off"] + BOARD_ROWS) % (math.ceil(len(b["lines"]) / BOARD_ROWS) * BOARD_ROWS)
            b["flip"] = now + 7
            self.reading = self.reading or now

        # stay parked while an answer is on its way or on screen
        if self.reading:
            busy = (now < self.bubble_until or self.boards or self.pending
                    or (self.board and now < self.board["until"]))
            if busy or now - self.reading < 1:
                if self.state in ("walk", "drive"):
                    self.set_idle()
                if self.state == "idle":
                    self.state_until = max(self.state_until, now + 1.5)
            else:
                self.reading = None

        if self.state != "sleep" and random.random() < 0.012 * dt:
            self.blink_until = now + 0.15

        # one beep per start light as it comes on
        L = self.lights
        if L and L["beeps"] < 5 and now >= L["start"] + (L["beeps"] + 1) * 0.9 and now < L["out"]:
            L["beeps"] += 1
            self.sound.play("beep")

        # engine off once we stop driving (arrived, grabbed, slept...)
        if self.state != "drive" and self.sound.current in ("rev", "engine"):
            if self.state == "idle":
                self.sound.play("stop")
            else:
                self.sound.stop()

        if self.lights and now > self.lights["out"] + 5:
            self.lights = None
            self.set_idle()
            self.say("Hello? The lights went out ages ago!")

        if self.state == "idle":
            if now > self.state_until and not self.lights:
                self.pick_next()

        elif self.state == "walk":
            self.x += WALK_SPEED * self.ease(dt, 30) * self.dir * dt
            if (self.dir > 0 and self.x >= self.target_x) or (self.dir < 0 and self.x <= self.target_x):
                self.set_idle()

        elif self.state == "drive":
            v = DRIVE_SPEED * self.ease(dt, 110)
            self.x += v * self.dir * dt
            self.wheel_rot += v * 0.1 * self.dir * dt
            self.puff_acc += dt * (0.4 + 0.6 * self.speed_k)
            if self.puff_acc >= 3:
                self.puff_acc -= 3
                self.puffs.append([CX - self.dir * 78, FOOT - 22 + random.uniform(-3, 3), 0])
            if (self.dir > 0 and self.x >= self.target_x) or (self.dir < 0 and self.x <= self.target_x):
                self.set_idle()
                if random.random() < 0.4:
                    self.say(random.choice(["P1! Get in there!", "Great lap!", "Tyres are gone."]), happy=True)

        elif self.state == "sleep":
            if now > self.state_until:
                self.wake()
                self.say(random.choice(["*yawn* Ready for qualifying.", "I'm back!"]))

        elif self.state == "fall":
            self.vy += GRAVITY * dt
            self.x += self.vx * dt
            self.y += self.vy * dt
            self.squash = max(-0.18, -abs(self.vy) / 60)
            lo, hi = self.left, self.right - W
            if self.x < lo:
                self.x, self.vx = lo, -self.vx * 0.6
            elif self.x > hi:
                self.x, self.vx = hi, -self.vx * 0.6
            if self.y < self.top - CEILING:
                self.y, self.vy = self.top - CEILING, abs(self.vy) * 0.3
            if self.y >= self.ground_y:
                self.y = self.ground_y
                if self.vy > 4:
                    if self.vy > 9:
                        self.sound.play("land")
                    if self.vy > 22:
                        self.say(random.choice(OUCH_LINES))
                    self.squash = min(0.35, self.vy / 40)
                    self.vy = -self.vy * 0.35
                    self.vx *= 0.7
                else:
                    self.vy = 0
                    self.vx *= 0.8
                    self.squash = 0
                    if abs(self.vx) < 0.5:
                        self.set_idle()
                        self.squash = 0.2

        if self.state != "fall":
            self.squash *= 0.8 ** dt

        # exhaust smoke drifts back and fades
        for p in self.puffs:
            p[0] -= self.dir * 2.5 * dt
            p[1] -= 0.6 * dt
            p[2] += dt
        self.puffs = [p for p in self.puffs if p[2] < 22]

        # random team radio
        if self.state in ("idle", "walk") and now > self.next_chat and now > self.bubble_until \
                and not self.lights:
            self.say(random.choice(RADIO + MEME_RADIO))
            self.next_chat = now + random.uniform(45, 150)

        self.root.geometry(f"+{round(self.x)}+{round(self.y)}")

    # ------------------------------------------------------------ drawing
    def eye_mode(self, now):
        if self.state == "sleep":
            return "sleep"
        if now < self.angry_until:
            return "angry"
        if self.state in ("drag", "fall") and abs(self.vy) > 3:
            return "surprised"
        if now < self.happy_until:
            return "happy"
        if now < self.blink_until:
            return "blink"
        return "open"

    def draw(self):
        c = self.canvas
        c.delete("all")
        now = time.time()
        t = self.t
        mode = self.eye_mode(now)
        d = self.dir
        tau = 2 * math.pi
        jx = random.choice((-1, 0, 1)) if mode == "angry" else 0

        if self.state == "drive":
            # speed lines + exhaust smoke behind the car
            for i in range(3):
                y = FOOT - 34 - i * 14
                off = (t * 9 + i * 23) % 50
                c.create_line(CX - d * (100 + off), y, CX - d * (125 + off), y, fill="#b0b8c4", width=2)
            for px, py, age in self.puffs:
                r = 4 + age * 0.5
                shade = ("#d9d9d9", "#c4c4c4", "#afafaf")[min(2, int(age // 8))]
                c.create_oval(px - r, py - r, px + r, py + r, fill=shade, outline="")
            wph = int((abs(self.wheel_rot) % (tau / 5)) / (tau / 5) * 4) % 4
            spec = ("car", d, wph, mode)
            bob = math.sin(t * 0.5)
            top = FOOT - SF + (SF - 76) - 0.72 * 44 + bob
        else:
            px, _ = self.root.winfo_pointerxy()
            look = d if self.state == "walk" else round(max(-1.0, min(1.0, (px - (self.x + CX)) / 300)) * 2) / 2
            airborne = self.state in ("drag", "fall")
            pose = "air" if airborne else "walk" if self.state == "walk" else "stand"
            ph = int((t * 0.3) % tau / tau * 8) if pose == "walk" else 0
            flag = now < self.flag_until
            thumb = now < self.thumb_until or (mode == "happy" and not flag)
            arm = "air" if airborne else "flag" if flag else "thumb" if thumb else "down"
            aph = int((t * 0.35) % tau / tau * 8) if arm == "flag" else (ph if arm == "down" else 0)
            sq = int(round(max(0.0, self.squash) * 10)) * 2
            spec = ("racer", pose, ph, d, mode, look, arm, aph, sq)
            if self.state == "idle":
                bob = math.sin(t * 0.1) * 2
            elif pose == "walk":
                bob = -abs(math.sin(t * 0.3)) * 3
            elif self.state == "sleep":
                bob = math.sin(t * 0.06) * 1.5
            else:
                bob = 0
            top = FOOT - SF + SHY - 44 + bob + sq

        photo = self.renderer.frame(spec)
        self._photo = photo
        c.create_image(SPRITE_X + jx, SPRITE_Y + bob, image=photo, anchor="nw")

        # Zzz
        if self.state == "sleep":
            for i in range(3):
                phase = ((t * 0.02) + i / 3) % 1
                c.create_text(CX + 40 + phase * 25, top + 10 - phase * 45, text="z",
                              font=("Segoe UI", int(9 + phase * 8), "bold"), fill="#ffb066")

        # start lights gantry
        if self.lights:
            L = self.lights
            gy = top - 93
            round_rect(c, CX - 90, gy, CX + 90, gy + 44, 10, fill="#111111", outline="#444444", width=2)
            for i in range(5):
                lit = L["start"] + (i + 1) * 0.9 <= now < L["out"]
                lx = CX - 64 + i * 32
                c.create_oval(lx - 12, gy + 10, lx + 12, gy + 34, fill="#ff2020" if lit else "#3a0a0a",
                              outline="#000000", width=2)
        # live results board
        elif self.board and now < self.board["until"]:
            self.draw_board(c, self.board, top - 14)
        # stopwatch timing board
        elif self.sw and now >= self.bubble_until:
            n = len(self.sw["laps"]) + 1
            round_rect(c, CX - 62, top - 44, CX + 62, top - 16, 8, fill="#111111", outline=ORANGE, width=2)
            c.create_text(CX, top - 30, text=f"L{n}  {fmt_time(now - self.sw['lap_start'])}",
                          fill=ORANGE, font=("Consolas", 12, "bold"))

        # speech bubble
        board_up = self.board and now < self.board["until"]
        if self.bubble_text and now < self.bubble_until and not self.lights and not board_up:
            bottom = top - 14
            tid = c.create_text(CX, bottom - 10, text=self.bubble_text, width=220,
                                font=FONT, fill=MENU_TEXT, anchor="s", justify="center")
            x1, y1, x2, y2 = c.bbox(tid)
            x1, y1, x2, y2 = x1 - 12, max(2, y1 - 9), x2 + 12, y2 + 8
            round_rect(c, x1, y1, x2, y2, 12, fill=MENU_BG, outline=ORANGE, width=2)
            c.create_polygon(CX - 8, y2 - 1, CX + 6, y2 - 1, CX, y2 + 11,
                             fill=MENU_BG, outline=ORANGE, width=2)
            c.create_line(CX - 6, y2 - 1, CX + 4, y2 - 1, fill=MENU_BG, width=3)
            c.tag_raise(tid)

    def draw_board(self, c, b, bottom):
        """Timing-screen style panel: title, rows in monospace, small print below."""
        n, off, lh = len(b["lines"]), b.get("off", 0), 15
        lines = b["lines"][off:off + BOARD_ROWS]
        if n > BOARD_ROWS:
            lines += [""] * (BOARD_ROWS - len(lines))   # keep the height steady between pages
        small = [(b["foot"], 8, 13)] if b.get("foot") else []
        if b.get("source"):
            small.append((b["source"], 7, 11))
        top = bottom - (30 + lh * len(lines) + sum(s[2] for s in small) + 8)
        round_rect(c, 4, top, W - 4, bottom, 10, fill="#111111", outline=ORANGE, width=2)
        c.create_rectangle(6, top + 22, W - 6, top + 25, fill=ORANGE, outline="")
        c.create_text(14, top + 12, anchor="w", text=b["title"][:34 if n <= BOARD_ROWS else 27], fill=ORANGE,
                      font=("Segoe UI", 10, "bold"))
        if n > BOARD_ROWS:
            c.create_text(W - 14, top + 12, anchor="e", text=f"{off + 1}-{min(n, off + BOARD_ROWS)}/{n}",
                          fill="#8a8a94", font=("Segoe UI", 8))
        y = top + 31
        mark = (b.get("mark") or "").lower()
        for ln in lines:
            hot = mark and mark in ln.lower()
            c.create_text(12, y, anchor="nw", text=ln[:36], fill=ORANGE if hot else "#f2f2f2",
                          font=("Consolas", 9, "bold" if hot else "normal"))
            y += lh
        for text, size, h in small:
            c.create_text(12, y + 1, anchor="nw", text=text[:60], fill="#8a8a94", font=("Segoe UI", size))
            y += h

    def on_wheel(self, e):
        """Scroll a long results board."""
        b, now = self.board, time.time()
        if not b or now > b["until"] or len(b["lines"]) <= BOARD_ROWS:
            return
        b["off"] = max(0, min(b["off"] + (-3 if e.delta > 0 else 3), len(b["lines"]) - BOARD_ROWS))
        b["flip"] = now + 10
        b["until"] = max(b["until"], now + 12)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    Pet().run()
