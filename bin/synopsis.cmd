@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
set "NoDefaultCurrentDirectoryInExePath=1"
set "PYTHONIOENCODING=utf-8"
set "lanzar="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul && set "lanzar=py -3"
if not defined lanzar python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul && set "lanzar=python"
if not defined lanzar echo Synopsis needs Python 3.11 or newer: https://www.python.org/downloads/
if not defined lanzar exit /b 1
%lanzar% -I -S -X utf8 "%~dp0synopsis" %*
exit /b %errorlevel%
