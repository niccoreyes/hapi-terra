@echo off
setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
pushd "%SCRIPT_DIR%"

if not exist cleanup.py (
  echo cleanup.py not found in %SCRIPT_DIR%
  popd
  exit /b 1
)

if not exist ".venv\Scripts\activate" (
  echo Virtual environment .venv not found. Create it before running cleanup.bat.
  popd
  exit /b 1
)

call ".venv\Scripts\activate"

python -m pip show boto3 >nul 2>&1
if %ERRORLEVEL% neq 0 (
  echo Installing cleanup dependencies from requirements.txt...
  python -m pip install -r requirements.txt || (
    echo Failed to install dependencies. Ensure pip works and try again.
    popd
    exit /b 1
  )
)

echo Running cleanup.py ...
python cleanup.py

popd
endlocal
