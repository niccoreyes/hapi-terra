@echo off
setlocal
title HAPI FHIR Terraform Deployment
echo ===============================================
echo  HAPI FHIR - AWS EKS Terraform - BATCH SCRIPT
echo ===============================================

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found. Installing via Chocolatey...
    powershell -NoProfile -Command "Set-ExecutionPolicy Bypass -Scope Process -Force; if (!(Get-Command choco -ErrorAction SilentlyContinue)) {iwr https://community.chocolatey.org/install.ps1 -UseBasicParsing | iex}; choco install python -y"
)

set "VENV_DIR=.venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    echo Creating virtual environment...
    python -m venv "%VENV_DIR%"
)

if not exist "%PYTHON_EXE%" (
    echo Failed to create virtual environment. Ensure Python is installed correctly.
    pause
    exit /b 1
)

"%PYTHON_EXE%" deploy.py
set EXITCODE=%ERRORLEVEL%

if %EXITCODE% neq 0 (
    echo.
    echo Deployment script exited with code %EXITCODE%.
) else (
    echo.
    echo Deployment script completed.
)

pause
exit /b %EXITCODE%
