@echo off
setlocal
set "HERE=%~dp0"
if exist "%HERE%流程盒子.exe" (
  start "" "%HERE%流程盒子.exe"
  goto :eof
)
where pythonw >nul 2>nul
if %errorlevel%==0 (
  start "" pythonw "%HERE%canvas_demo.py"
  goto :eof
)
where python >nul 2>nul
if %errorlevel%==0 (
  start "" python "%HERE%canvas_demo.py"
  goto :eof
)
echo 没找到 流程盒子.exe，也没在 PATH 里找到 pythonw.exe / python.exe。
pause
