@echo off
setlocal DisableDelayedExpansion
call "%~dp0bin\synopsis.cmd" install %*
exit /b %errorlevel%
