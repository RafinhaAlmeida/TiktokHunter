@echo off
REM Envia suas alteracoes para o GitHub (git add + commit + push)
cd /d "%~dp0"
set /p MSG="Descreva o que mudou: "
if "%MSG%"=="" set MSG=Atualizacao
git add -A
git commit -m "%MSG%"
git push
pause
