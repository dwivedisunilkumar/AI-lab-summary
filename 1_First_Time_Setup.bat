@echo off
TITLE Meesha App Setup
ECHO ==========================================
ECHO      MEESHA DIAGNOSTICS - INITIAL SETUP
ECHO ==========================================
ECHO.
ECHO This script will install all necessary libraries.
ECHO Please ensure you have Python installed first.
ECHO.

cd /d "%~dp0"

ECHO [1/2] Upgrading PIP...
python -m pip install --upgrade pip

ECHO.
ECHO [2/2] Installing Libraries (Streamlit, PDF Tools)...
pip install -r requirements.txt

ECHO.
ECHO ==========================================
ECHO      SETUP COMPLETE!
ECHO ==========================================
ECHO You can now use "Run_Meesha_App.bat" to start the program.
ECHO.
PAUSE