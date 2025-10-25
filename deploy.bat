@echo off
title HAPI FHIR Terraform Deployment
echo ===============================================
echo   HAPI FHIR - AWS EKS Terraform Deployment
echo ===============================================


:: --- Check dependencies ---
echo Checking dependencies...
where terraform >nul 2>&1
if %errorlevel% neq 0 (
    echo Terraform not found. Installing via Chocolatey...
    powershell -Command "Set-ExecutionPolicy Bypass -Scope Process -Force; if (!(Get-Command choco -ErrorAction SilentlyContinue)) {iwr https://community.chocolatey.org/install.ps1 -UseBasicParsing | iex}; choco install terraform -y"
)

where aws >nul 2>&1
if %errorlevel% neq 0 (
    echo AWS CLI not found. Installing via Chocolatey...
    powershell -Command "choco install awscli -y"
)

where kubectl >nul 2>&1
if %errorlevel% neq 0 (
    echo kubectl not found. Installing via Chocolatey...
    powershell -Command "choco install kubernetes-cli -y"
)
echo Dependencies verified.


:: --- Ask for user input ---
if exist ".env" (
    for /f "usebackq tokens=1* delims==" %%A in (".env") do (
        if /i "%%A"=="AWS_ACCESS_KEY_ID" set AWS_ACCESS_KEY_ID_DEFAULT=%%B
        if /i "%%A"=="AWS_SECRET_ACCESS_KEY" set AWS_SECRET_ACCESS_KEY_DEFAULT=%%B
        if /i "%%A"=="AWS_DEFAULT_REGION" set AWS_REGION_DEFAULT=%%B
        if /i "%%A"=="AWS_REGION" set AWS_REGION_DEFAULT=%%B
        if /i "%%A"=="SSH_KEY_NAME" set SSH_KEY_NAME_DEFAULT=%%B
        if /i "%%A"=="ENVIRONMENT" set ENVIRONMENT_DEFAULT=%%B
        if /i "%%A"=="HAPI_MODE" set HAPI_MODE_DEFAULT=%%B
    )
)

if defined AWS_ACCESS_KEY_ID_DEFAULT (
    set /p AWS_ACCESS_KEY_ID=AWS Access Key ID (find in AWS Console > IAM > Users > your user > Security credentials > Access keys) [%AWS_ACCESS_KEY_ID_DEFAULT%]: 
    if "%AWS_ACCESS_KEY_ID%"=="" set AWS_ACCESS_KEY_ID=%AWS_ACCESS_KEY_ID_DEFAULT%
) else (
    set /p AWS_ACCESS_KEY_ID=AWS Access Key ID (find in AWS Console > IAM > Users > your user > Security credentials > Access keys): 
)

if defined AWS_SECRET_ACCESS_KEY_DEFAULT (
    set /p AWS_SECRET_ACCESS_KEY=AWS Secret Access Key (shown once when creating the key; create a new key in the same IAM screen if needed) [stored]: 
    if "%AWS_SECRET_ACCESS_KEY%"=="" set AWS_SECRET_ACCESS_KEY=%AWS_SECRET_ACCESS_KEY_DEFAULT%
) else (
    set /p AWS_SECRET_ACCESS_KEY=AWS Secret Access Key (shown once when creating the key; create a new key in the same IAM screen if needed): 
)

if defined AWS_REGION_DEFAULT (
    set /p AWS_REGION=AWS region code (default us-east-1; matches the region selector in the AWS Console toolbar) [%AWS_REGION_DEFAULT%]: 
    if "%AWS_REGION%"=="" set AWS_REGION=%AWS_REGION_DEFAULT%
) else (
    set /p AWS_REGION=AWS region code (default us-east-1; matches the region selector in the AWS Console toolbar): 
    if "%AWS_REGION%"=="" set AWS_REGION=us-east-1
)
if "%AWS_REGION%"=="" set AWS_REGION=us-east-1

if defined SSH_KEY_NAME_DEFAULT (
    set /p SSH_KEY_NAME=Existing EC2 key pair name (optional; AWS Console > EC2 > Key Pairs). Leave blank to skip SSH access [%SSH_KEY_NAME_DEFAULT%]: 
    if "%SSH_KEY_NAME%"=="" set SSH_KEY_NAME=%SSH_KEY_NAME_DEFAULT%
) else (
    set /p SSH_KEY_NAME=Existing EC2 key pair name (optional; AWS Console > EC2 > Key Pairs). Leave blank to skip SSH access: 
)

if defined ENVIRONMENT_DEFAULT (
    set /p ENVIRONMENT=Environment tag (default dev; choose labels like dev/test/prod to organize resources) [%ENVIRONMENT_DEFAULT%]: 
    if "%ENVIRONMENT%"=="" set ENVIRONMENT=%ENVIRONMENT_DEFAULT%
) else (
    set /p ENVIRONMENT=Environment tag (default dev; choose labels like dev/test/prod to organize resources): 
)
if "%ENVIRONMENT%"=="" set ENVIRONMENT=dev

echo Choose HAPI FHIR deployment mode:
echo   1 - General FHIR Server (default)
echo   2 - Terminology Server only
echo   3 - Deploy both General and Terminology
if defined HAPI_MODE_DEFAULT (
    set MODE_SELECT_DEFAULT=1
    if /i "%HAPI_MODE_DEFAULT%"=="terminology" set MODE_SELECT_DEFAULT=2
    if /i "%HAPI_MODE_DEFAULT%"=="both" set MODE_SELECT_DEFAULT=3
    set /p MODE_SELECT=Enter choice [1/2/3] (default %MODE_SELECT_DEFAULT%): 
    if "%MODE_SELECT%"=="" set MODE_SELECT=%MODE_SELECT_DEFAULT%
) else (
    set /p MODE_SELECT=Enter choice [1/2/3]: 
    if "%MODE_SELECT%"=="" set MODE_SELECT=1
)
if "%MODE_SELECT%"=="2" (
    set HAPI_MODE=terminology
) else (
    if "%MODE_SELECT%"=="3" (
        set HAPI_MODE=both
    ) else (
        set HAPI_MODE=general
    )
)
echo Selected mode: %HAPI_MODE%

:: --- Set environment variables ---
setx AWS_ACCESS_KEY_ID "%AWS_ACCESS_KEY_ID%" >nul
setx AWS_SECRET_ACCESS_KEY "%AWS_SECRET_ACCESS_KEY%" >nul
setx AWS_DEFAULT_REGION "%AWS_REGION%" >nul
set AWS_ACCESS_KEY_ID=%AWS_ACCESS_KEY_ID%
set AWS_SECRET_ACCESS_KEY=%AWS_SECRET_ACCESS_KEY%
set AWS_DEFAULT_REGION=%AWS_REGION%

(
    if defined AWS_ACCESS_KEY_ID (echo AWS_ACCESS_KEY_ID=%AWS_ACCESS_KEY_ID%) else (echo AWS_ACCESS_KEY_ID=)
    if defined AWS_SECRET_ACCESS_KEY (echo AWS_SECRET_ACCESS_KEY=%AWS_SECRET_ACCESS_KEY%) else (echo AWS_SECRET_ACCESS_KEY=)
    if defined AWS_REGION (echo AWS_DEFAULT_REGION=%AWS_REGION%) else (echo AWS_DEFAULT_REGION=)
    if defined AWS_REGION (echo AWS_REGION=%AWS_REGION%) else (echo AWS_REGION=)
    if defined SSH_KEY_NAME (echo SSH_KEY_NAME=%SSH_KEY_NAME%) else (echo SSH_KEY_NAME=)
    if defined ENVIRONMENT (echo ENVIRONMENT=%ENVIRONMENT%) else (echo ENVIRONMENT=)
    if defined HAPI_MODE (echo HAPI_MODE=%HAPI_MODE%) else (echo HAPI_MODE=)
) > .env

:: --- Terraform apply ---
echo Initializing Terraform...
terraform init

echo Applying Terraform for %HAPI_MODE% mode...
terraform apply -auto-approve ^
  -var="aws_region=%AWS_REGION%" ^
  -var="ssh_key_name=%SSH_KEY_NAME%" ^
  -var="environment=%ENVIRONMENT%" ^
  -var="hapi_mode=%HAPI_MODE%"

if %errorlevel% neq 0 (
    
    echo ❌ Deployment failed.
    pause
    exit /b 1
) else (
    
    echo ✅ Deployment completed successfully!
    
    echo To get the LoadBalancer URL:
    echo   kubectl get svc -A
    
)
pause
