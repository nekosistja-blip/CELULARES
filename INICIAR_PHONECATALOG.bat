@echo off
setlocal
cd /d "%~dp0"
title PhoneCatalog V2
cls
echo ========================================
echo        PhoneCatalog V2 - Internet
echo ========================================
echo Carpeta: %CD%
echo.
where python >nul 2>nul
if errorlevel 1 (
 echo ERROR: Python no esta instalado o no esta en PATH.
 pause
 exit /b 1
)
echo Verificando dependencias...
python -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
 echo ERROR instalando dependencias.
 pause
 exit /b 1
)
echo.
echo Iniciando PhoneCatalog V2...
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:5050"
python "%~dp0app.py"
pause
