@echo off
echo =======================================
echo Building StarMind Manager Executable
echo =======================================

echo Installing PyInstaller...
pip install pyinstaller --upgrade

echo Cleaning old builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist "StarMind Manager.spec" del /q "StarMind Manager.spec"

echo Starting PyInstaller Build...
pyinstaller --noconfirm --onedir --windowed --name "StarMind Manager" --add-data "templates;templates" main.py

echo Build complete!
echo Please find your application in the 'dist/StarMind Manager' folder.
echo =======================================
pause
