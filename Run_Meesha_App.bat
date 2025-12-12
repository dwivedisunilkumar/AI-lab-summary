@echo off
TITLE Meesha Diagnostics AI
ECHO Starting Meesha Diagnostics App...
ECHO Please wait while the application loads...

:: Navigate to the script's directory
cd /d "%~dp0"

:: Run the Streamlit app with "App-like" settings (hides developer toolbars)
python -m streamlit run app.py --server.headless true --browser.gatherUsageStats false --theme.base "light" --client.toolbarMode viewer --ui.hideTopBar true

PAUSE