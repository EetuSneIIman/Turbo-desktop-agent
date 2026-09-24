@echo off
cd /d "%~dp0"
python -m pip install --quiet --disable-pip-version-check pillow
start "" pythonw desktop_pet.py
