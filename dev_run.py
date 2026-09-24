"""
Live-reload runner for Turbo.

Run:  python dev_run.py      (or double-click dev_run.bat)

Starts desktop_pet.py and restarts it automatically every time the file is saved,
so you can keep Turbo running while you (or Claude) edit the code.
Errors are printed in this console. Choosing "Goodbye" in Turbo's menu, or Ctrl+C here, stops everything.
"""

import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "desktop_pet.py")


def mtime():
    try:
        return os.path.getmtime(TARGET)
    except OSError:
        return 0


def start():
    print(time.strftime("[%H:%M:%S]"), "starting Turbo...", flush=True)
    return subprocess.Popen([sys.executable, TARGET], cwd=HERE)


def stop(proc):
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


def main():
    print("Watching desktop_pet.py - save the file to reload. Ctrl+C to quit.\n", flush=True)
    last = mtime()
    proc = start()
    crashed = False
    try:
        while True:
            time.sleep(0.5)
            m = mtime()
            if m != last:
                time.sleep(0.3)          # let the editor finish writing
                last = mtime()
                stop(proc)
                print(time.strftime("[%H:%M:%S]"), "change detected, reloading", flush=True)
                proc = start()
                crashed = False
            elif proc.poll() is not None and not crashed:
                if proc.returncode == 0:
                    print("Turbo said goodbye. Stopping.")
                    return
                crashed = True
                print(time.strftime("[%H:%M:%S]"),
                      f"Turbo crashed (exit code {proc.returncode}). Fix the error above and save to retry.",
                      flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        stop(proc)


if __name__ == "__main__":
    main()
