@echo off
setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
pushd "%SCRIPT_DIR%"

if not exist inventory.py (
  echo inventory.py not found in %SCRIPT_DIR%
  popd
  exit /b 1
)

if not exist ".venv\Scripts\activate" (
  echo Virtual environment .venv not found. Create it before running inventory.bat.
  popd
  exit /b 1
)

call ".venv\Scripts\activate"

python -m pip show boto3 >nul 2>&1
if %ERRORLEVEL% neq 0 (
  echo Installing inventory dependencies from requirements.txt...
  python -m pip install -r requirements.txt || (
    echo Failed to install dependencies. Ensure pip works and try again.
    popd
    exit /b 1
  )
)

echo Running inventory.py ...
python inventory.py

popd
endlocal
