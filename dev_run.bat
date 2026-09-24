@echo off
cd /d "%~dp0"
title Turbo - live reload
python -m pip install --quiet --disable-pip-version-check pillow
python dev_run.py
pause
