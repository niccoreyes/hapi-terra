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
        if /i "%%A"=="CLUSTER_NAME" if not defined CLUSTER_NAME set CLUSTER_NAME=%%B
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

set "AWS_ACCESS_KEY_ID_DEFAULT=%AWS_ACCESS_KEY_ID%"
set "AWS_SECRET_ACCESS_KEY_DEFAULT=%AWS_SECRET_ACCESS_KEY%"
set "AWS_DEFAULT_REGION_DEFAULT=%AWS_DEFAULT_REGION%"

echo AWS Access Key ID (find in AWS Console ^> IAM ^> Users ^> your user ^> Security credentials ^> Access keys)
if defined AWS_ACCESS_KEY_ID_DEFAULT (
    set /p AWS_ACCESS_KEY_ID=Enter AWS Access Key ID [%AWS_ACCESS_KEY_ID_DEFAULT%]: 
    if "%AWS_ACCESS_KEY_ID%"=="" set AWS_ACCESS_KEY_ID=%AWS_ACCESS_KEY_ID_DEFAULT%
) else (
    set /p AWS_ACCESS_KEY_ID=Enter AWS Access Key ID: 
)

echo AWS Secret Access Key (shown once at key creation; generate a new key in IAM if needed)
if defined AWS_SECRET_ACCESS_KEY_DEFAULT (
    set /p AWS_SECRET_ACCESS_KEY=Enter AWS Secret Access Key [stored]: 
    if "%AWS_SECRET_ACCESS_KEY%"=="" set AWS_SECRET_ACCESS_KEY=%AWS_SECRET_ACCESS_KEY_DEFAULT%
) else (
    set /p AWS_SECRET_ACCESS_KEY=Enter AWS Secret Access Key: 
)

echo AWS region code (match the region used during deploy; default us-east-1)
if defined AWS_DEFAULT_REGION_DEFAULT (
    set /p AWS_DEFAULT_REGION=Enter AWS region [%AWS_DEFAULT_REGION_DEFAULT%]: 
    if "%AWS_DEFAULT_REGION%"=="" set AWS_DEFAULT_REGION=%AWS_DEFAULT_REGION_DEFAULT%
) else (
    set /p AWS_DEFAULT_REGION=Enter AWS region [us-east-1]: 
    if "%AWS_DEFAULT_REGION%"=="" set AWS_DEFAULT_REGION=us-east-1
)
if "%AWS_DEFAULT_REGION%"=="" set AWS_DEFAULT_REGION=us-east-1

echo EKS cluster name to destroy (defaults to hapi-eks-cluster if not saved)
if defined CLUSTER_NAME (
    set "CURRENT_CLUSTER_NAME=%CLUSTER_NAME%"
    set /p CLUSTER_NAME=Enter cluster name [%CURRENT_CLUSTER_NAME%]: 
    if "%CLUSTER_NAME%"=="" set CLUSTER_NAME=%CURRENT_CLUSTER_NAME%
) else (
    set /p CLUSTER_NAME=Enter cluster name [hapi-eks-cluster]: 
    if "%CLUSTER_NAME%"=="" set CLUSTER_NAME=hapi-eks-cluster
)
set "CURRENT_CLUSTER_NAME="

set AWS_ACCESS_KEY_ID=%AWS_ACCESS_KEY_ID%
set AWS_SECRET_ACCESS_KEY=%AWS_SECRET_ACCESS_KEY%
set AWS_DEFAULT_REGION=%AWS_DEFAULT_REGION%
set AWS_REGION=%AWS_DEFAULT_REGION%

(
    if defined AWS_ACCESS_KEY_ID (echo AWS_ACCESS_KEY_ID=%AWS_ACCESS_KEY_ID%) else (echo AWS_ACCESS_KEY_ID=)
    if defined AWS_SECRET_ACCESS_KEY (echo AWS_SECRET_ACCESS_KEY=%AWS_SECRET_ACCESS_KEY%) else (echo AWS_SECRET_ACCESS_KEY=)
    if defined AWS_DEFAULT_REGION (echo AWS_DEFAULT_REGION=%AWS_DEFAULT_REGION%) else (echo AWS_DEFAULT_REGION=)
    if defined AWS_REGION (echo AWS_REGION=%AWS_REGION%) else (echo AWS_REGION=)
    if defined CLUSTER_NAME (echo CLUSTER_NAME=%CLUSTER_NAME%) else (echo CLUSTER_NAME=)
    if defined SSH_KEY_NAME (echo SSH_KEY_NAME=%SSH_KEY_NAME%) else (echo SSH_KEY_NAME=)
    if defined ENVIRONMENT (echo ENVIRONMENT=%ENVIRONMENT%) else (echo ENVIRONMENT=)
    if defined HAPI_MODE (echo HAPI_MODE=%HAPI_MODE%) else (echo HAPI_MODE=)
) > .env

terraform destroy -auto-approve -var="aws_region=%AWS_REGION%" -var="ssh_key_name=%SSH_KEY_NAME%" -var="environment=%ENVIRONMENT%" -var="hapi_mode=%HAPI_MODE%" -var="cluster_name=%CLUSTER_NAME%"

if %errorlevel% neq 0 (
    
    echo ❌ Destroy failed.
    pause
    exit /b 1
) else (
    
    echo ✅ All resources destroyed successfully!
    
)
pause
