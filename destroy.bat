@echo off
title HAPI FHIR Terraform Teardown
echo ===============================================
echo   HAPI FHIR - AWS EKS Terraform Destroy
echo ===============================================


if exist ".env" (
    for /f "usebackq tokens=1* delims==" %%A in (".env") do (
        if /i "%%A"=="AWS_ACCESS_KEY_ID" if not defined AWS_ACCESS_KEY_ID set AWS_ACCESS_KEY_ID=%%B
        if /i "%%A"=="AWS_SECRET_ACCESS_KEY" if not defined AWS_SECRET_ACCESS_KEY set AWS_SECRET_ACCESS_KEY=%%B
        if /i "%%A"=="AWS_DEFAULT_REGION" if not defined AWS_DEFAULT_REGION set AWS_DEFAULT_REGION=%%B
        if /i "%%A"=="AWS_REGION" if not defined AWS_DEFAULT_REGION set AWS_DEFAULT_REGION=%%B
        if /i "%%A"=="SSH_KEY_NAME" if not defined SSH_KEY_NAME set SSH_KEY_NAME=%%B
        if /i "%%A"=="ENVIRONMENT" if not defined ENVIRONMENT set ENVIRONMENT=%%B
        if /i "%%A"=="HAPI_MODE" if not defined HAPI_MODE set HAPI_MODE=%%B
    )
)

where terraform >nul 2>&1
if %errorlevel% neq 0 (
    echo Terraform not found. Please install Terraform before running this script.
    pause
    exit /b 1
)

echo WARNING: This will destroy all AWS resources created by Terraform.

set /p CONFIRM=Type "DESTROY" to continue: 
if /i not "%CONFIRM%"=="DESTROY" (
    echo Aborted.
    exit /b 0
)

if "%AWS_ACCESS_KEY_ID%"=="" (
    echo AWS credentials not found in environment.
    set /p AWS_ACCESS_KEY_ID=AWS Access Key ID (find in AWS Console > IAM > Users > your user > Security credentials > Access keys): 
    set /p AWS_SECRET_ACCESS_KEY=AWS Secret Access Key (shown once at key creation; generate a new key in IAM if needed): 
    set /p AWS_DEFAULT_REGION=AWS region code (default us-east-1; match the region used during deploy): 
    if "%AWS_DEFAULT_REGION%"=="" set AWS_DEFAULT_REGION=us-east-1
)
if "%AWS_DEFAULT_REGION%"=="" set AWS_DEFAULT_REGION=us-east-1

set AWS_ACCESS_KEY_ID=%AWS_ACCESS_KEY_ID%
set AWS_SECRET_ACCESS_KEY=%AWS_SECRET_ACCESS_KEY%
set AWS_DEFAULT_REGION=%AWS_DEFAULT_REGION%
set AWS_REGION=%AWS_DEFAULT_REGION%

(
    if defined AWS_ACCESS_KEY_ID (echo AWS_ACCESS_KEY_ID=%AWS_ACCESS_KEY_ID%) else (echo AWS_ACCESS_KEY_ID=)
    if defined AWS_SECRET_ACCESS_KEY (echo AWS_SECRET_ACCESS_KEY=%AWS_SECRET_ACCESS_KEY%) else (echo AWS_SECRET_ACCESS_KEY=)
    if defined AWS_DEFAULT_REGION (echo AWS_DEFAULT_REGION=%AWS_DEFAULT_REGION%) else (echo AWS_DEFAULT_REGION=)
    if defined AWS_REGION (echo AWS_REGION=%AWS_REGION%) else (echo AWS_REGION=)
    if defined SSH_KEY_NAME (echo SSH_KEY_NAME=%SSH_KEY_NAME%) else (echo SSH_KEY_NAME=)
    if defined ENVIRONMENT (echo ENVIRONMENT=%ENVIRONMENT%) else (echo ENVIRONMENT=)
    if defined HAPI_MODE (echo HAPI_MODE=%HAPI_MODE%) else (echo HAPI_MODE=)
) > .env

terraform destroy -auto-approve

if %errorlevel% neq 0 (
    
    echo ❌ Destroy failed.
    pause
    exit /b 1
) else (
    
    echo ✅ All resources destroyed successfully!
    
)
pause
