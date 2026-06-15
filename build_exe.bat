@echo off
REM Gera o EXE standalone (tray app) em dist\Extrator Cortes NF.exe
cd /d "%~dp0"
taskkill /IM "Extrator Cortes NF.exe" /F >nul 2>&1
pyinstaller --noconfirm --onefile --windowed ^
  --name "Extrator Cortes NF" ^
  --icon "assets\icon.ico" ^
  --add-data "assets\icon.png;assets" ^
  --add-data "assets\icon.ico;assets" ^
  --collect-all tkinterdnd2 ^
  --collect-all pystray ^
  --collect-all PIL ^
  app.py
echo.
echo Pronto: dist\Extrator Cortes NF.exe
pause
