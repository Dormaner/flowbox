@echo off
setlocal
set "APP=%~dp0editor_qt.py"
rem 把下面这行改成你机器上装了 PySide6 的 pythonw.exe；路径不对会自动退回 PATH 里的 py / pythonw
set "PYW=C:\Users\niu\Desktop\领导来了\.venv\Scripts\pythonw.exe"
if exist "%PYW%" (
  start "" "%PYW%" "%APP%"
  goto :eof
)
where pythonw >nul 2>nul
if %errorlevel%==0 (
  start "" pythonw "%APP%"
  goto :eof
)
where py >nul 2>nul
if %errorlevel%==0 (
  start "" py -3 "%APP%"
  goto :eof
)
echo 没找到能运行 Qt 版的 Python。先装：pip install PySide6
pause
