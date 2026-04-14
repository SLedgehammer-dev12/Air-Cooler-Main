@echo off
setlocal

echo Building Air Cooler Main executable...
pyinstaller --clean --noconfirm air_cooler_main.spec

echo.
echo Build complete: dist\AirCooler_Main
pause
