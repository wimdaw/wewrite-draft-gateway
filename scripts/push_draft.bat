@echo off
rem ============================================================
rem  wewrite-draft-gateway 一键推送（Windows）
rem   用法：把 Markdown 文件拖到本 .bat 上；或命令行执行
rem         push_draft.bat "文章.md" ["封面.png"]
rem   依赖：已 pip install wewrite-draft-gateway（或用 -m wewrite_gateway）
rem   配置：~/.wewrite-gateway.env 或当前目录 .env
rem ============================================================
chcp 65001 >nul
setlocal
set "PY=python"
where python >nul 2>nul || set "PY=py"

if "%~1"=="" (
  echo.
  echo   用法：把 Markdown 文件拖到本 .bat 上；或命令行执行
  echo         %~nx0 "文章.md" ["封面.png"]
  echo.
  pause
  exit /b 1
)

set "ART=%~f1"
set "COVER=%~2"
if "%COVER%"=="" set "COVER=%~dpn1-cover.png"

if not exist "%COVER%" (
  echo [1/2] 未找到封面，自动生成：%COVER%
  "%PY%" "%~dp0..\examples\make_cover.py" "%COVER%" "%~n1"
)

echo [2/2] 正在排版并推送到公众号草稿箱：%ART%
"%PY%" -m wewrite_gateway push "%ART%" --cover "%COVER%"
echo.
pause
