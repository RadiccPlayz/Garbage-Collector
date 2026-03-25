@echo off
:: =============================================
:: Build script — Garbage Collector (Windows)
:: =============================================

set EXE_NAME=GarbageCollector
set ENTRY=main.py
set ICON=trash-logo.ico

echo Cleaning previous builds...
if exist build     rmdir /s /q build
if exist dist      rmdir /s /q dist
if exist "%EXE_NAME%.spec" del /q "%EXE_NAME%.spec"

echo Building executable...
pyinstaller --clean ^
    --onefile ^
    --noconsole ^
    --icon="%ICON%" ^
    --name "%EXE_NAME%" ^
    --add-data "ui_styles.py;." ^
    --add-data "ui_main.py;." ^
    --add-data "workers.py;." ^
    --add-data "cleanup_tasks.py;." ^
    --add-data "platform_detect.py;." ^
    "%ENTRY%"

:: Tidy up
del /q "%EXE_NAME%.spec" 2>nul
rmdir /s /q build 2>nul

echo.
echo Build complete. Executable: dist\%EXE_NAME%.exe
pause
