@echo off
REM Download missing subtitles for a show folder on the NAS (see subs.py).
REM Usage: subs "Show Name"   |   subs --list   |   subs "Show" -l en -l ar
python "%~dp0subs.py" %*
