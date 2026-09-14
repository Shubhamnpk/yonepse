@echo off
echo Starting local development server...
echo Open http://localhost:8000 in your browser to view the dashboard.
set "PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if exist "%PY%" (
    "%PY%" -m http.server 8000
) else (
    python -m http.server 8000
)
