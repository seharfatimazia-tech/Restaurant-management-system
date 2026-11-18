@echo off
title Gusto Restaurant Management Software
color 0F

echo ==============================================================================
echo             GUSTO RESTAURANT MANAGEMENT DESKTOP SOFTWARE
echo               Enterprise POS, Inventory, Delivery ^& DBMS
echo ==============================================================================
echo.

cd /d "%~dp0"

echo [1/3] Checking Python installation...
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    where py >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Python was not found in PATH.
        echo Please install Python 3.10+ from https://www.python.org/ or open in VS Code.
        pause
        exit /b 1
    ) else (
        set PY_CMD=py
    )
) else (
    set PY_CMD=python
)

echo [2/3] Checking dependencies...
%PY_CMD% -c "import flask, flask_sqlalchemy, werkzeug" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Installing required software packages...
    %PY_CMD% -m pip install -r requirements.txt
)

echo [3/3] Launching Desktop Software Application Window...
echo.
%PY_CMD% main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [Notice] Software session ended.
    pause
)
