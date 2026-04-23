@echo off
echo Starting Steam AO Dashboard...
echo Waiting for browser to open at http://localhost:8501
echo Press Ctrl+C to stop.
echo.
cd /d "%~dp0"
python -m streamlit run app.py
pause
