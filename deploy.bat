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
        if /i "%%A"=="CLUSTER_NAME" set CLUSTER_NAME_DEFAULT=%%B
    )
)

echo AWS Access Key ID (find in AWS Console ^> IAM ^> Users ^> your user ^> Security credentials ^> Access keys)
if defined AWS_ACCESS_KEY_ID_DEFAULT (
    set /p AWS_ACCESS_KEY_ID=Enter AWS Access Key ID [%AWS_ACCESS_KEY_ID_DEFAULT%]: 
    if "%AWS_ACCESS_KEY_ID%"=="" set AWS_ACCESS_KEY_ID=%AWS_ACCESS_KEY_ID_DEFAULT%
) else (
    set /p AWS_ACCESS_KEY_ID=Enter AWS Access Key ID: 
)

echo AWS Secret Access Key (shown once when creating the key; create a new key in the same IAM screen if needed)
if defined AWS_SECRET_ACCESS_KEY_DEFAULT (
    set /p AWS_SECRET_ACCESS_KEY=Enter AWS Secret Access Key [stored]: 
    if "%AWS_SECRET_ACCESS_KEY%"=="" set AWS_SECRET_ACCESS_KEY=%AWS_SECRET_ACCESS_KEY_DEFAULT%
) else (
    set /p AWS_SECRET_ACCESS_KEY=Enter AWS Secret Access Key: 
)

echo AWS region code (matches the region selector in the AWS Console toolbar; default us-east-1)
if defined AWS_REGION_DEFAULT (
    set /p AWS_REGION=Enter AWS region [%AWS_REGION_DEFAULT%]: 
    if "%AWS_REGION%"=="" set AWS_REGION=%AWS_REGION_DEFAULT%
) else (
    set /p AWS_REGION=Enter AWS region: 
    if "%AWS_REGION%"=="" set AWS_REGION=us-east-1
)
if "%AWS_REGION%"=="" set AWS_REGION=us-east-1

echo EKS cluster name (used for the Terraform-managed EKS control plane; default hapi-eks-cluster)
if defined CLUSTER_NAME_DEFAULT (
    set /p CLUSTER_NAME=Enter cluster name [%CLUSTER_NAME_DEFAULT%]: 
    if "%CLUSTER_NAME%"=="" set CLUSTER_NAME=%CLUSTER_NAME_DEFAULT%
) else (
    set /p CLUSTER_NAME=Enter cluster name [hapi-eks-cluster]: 
    if "%CLUSTER_NAME%"=="" set CLUSTER_NAME=hapi-eks-cluster
)

set "KEYPAIR_TMP=%TEMP%\hapi_keypairs_%RANDOM%.tmp"
set "HAS_KEYPAIRS="
echo Checking for existing EC2 key pairs in %AWS_REGION%...
aws ec2 describe-key-pairs --query "KeyPairs[].KeyName" --output text --region %AWS_REGION% > "%KEYPAIR_TMP%" 2>nul
if %errorlevel% neq 0 (
    echo Unable to list key pairs automatically. Enter a name manually or create one in AWS Console ^> EC2 ^> Key Pairs.
) else (
    for /f "usebackq tokens=* delims=" %%K in ("%KEYPAIR_TMP%") do (
        if not "%%K"=="" set HAS_KEYPAIRS=1
    )
    if defined HAS_KEYPAIRS (
        echo Available key pairs in %AWS_REGION%:
        type "%KEYPAIR_TMP%"
        echo Enter one of the key names above, or press Enter to skip SSH access.
    ) else (
        echo No key pairs detected in %AWS_REGION%. Create one in AWS Console ^> EC2 ^> Key Pairs if you need SSH access.
    )
)
del "%KEYPAIR_TMP%" >nul 2>&1
set "HAS_KEYPAIRS="

echo Existing EC2 key pair name (optional; AWS Console ^> EC2 ^> Key Pairs). Leave blank to skip SSH access.
if defined SSH_KEY_NAME_DEFAULT (
    set /p SSH_KEY_NAME=Enter key pair name [%SSH_KEY_NAME_DEFAULT%]: 
    if "%SSH_KEY_NAME%"=="" set SSH_KEY_NAME=%SSH_KEY_NAME_DEFAULT%
) else (
    set /p SSH_KEY_NAME=Enter key pair name: 
)

echo Environment tag (choose labels like dev/test/prod to organize resources; default dev)
if defined ENVIRONMENT_DEFAULT (
    set /p ENVIRONMENT=Enter environment tag [%ENVIRONMENT_DEFAULT%]: 
    if "%ENVIRONMENT%"=="" set ENVIRONMENT=%ENVIRONMENT_DEFAULT%
) else (
    set /p ENVIRONMENT=Enter environment tag: 
)
if "%ENVIRONMENT%"=="" set ENVIRONMENT=dev

set "DUPLICATE_LOG=%TEMP%\hapi_duplicate_%RANDOM%.log"
set "EXISTING_DEPLOYMENT="
echo Checking for an existing EKS cluster named %CLUSTER_NAME% in %AWS_REGION%...
aws eks describe-cluster --name "%CLUSTER_NAME%" --region %AWS_REGION% >nul 2>"%DUPLICATE_LOG%"
if %errorlevel%==0 (
    set EXISTING_DEPLOYMENT=1
    echo Found existing EKS cluster "%CLUSTER_NAME%".
) else (
    findstr /c:"ResourceNotFoundException" "%DUPLICATE_LOG%" >nul
    if not errorlevel 1 (
        echo No existing EKS cluster found; proceeding with a new deployment.
    ) else (
        set "DUPLICATE_WARNED="
        for /f "usebackq tokens=* delims=" %%E in ("%DUPLICATE_LOG%") do (
            if not "%%~E"=="" (
                if not defined DUPLICATE_WARNED (
                    echo Warning: Unable to confirm duplicate deployment automatically.
                    echo   AWS CLI output:
                    set DUPLICATE_WARNED=1
                )
                call echo     %%E
            )
        )
        if not defined DUPLICATE_WARNED (
            echo Warning: Unable to confirm duplicate deployment automatically.
            echo   Review AWS CLI permissions or retry manually with: aws eks describe-cluster --name "%CLUSTER_NAME%"
        )
    )
)
del "%DUPLICATE_LOG%" >nul 2>&1

if defined EXISTING_DEPLOYMENT (
    set /p DUPLICATE_CONFIRM=Cluster already exists. Continue and let Terraform reconcile it? [y/N]: 
    if /i not "%DUPLICATE_CONFIRM%"=="y" if /i not "%DUPLICATE_CONFIRM%"=="yes" (
        echo Deployment cancelled at user request.
        pause
        exit /b 0
    )
)
set "DUPLICATE_WARNED="

echo Choose HAPI FHIR deployment mode:
echo   1 - General FHIR Server (default)
echo   2 - Terminology Server only
echo   3 - Deploy both General and Terminology
set MODE_SELECT_DEFAULT=1
if defined HAPI_MODE_DEFAULT (
    if /i "%HAPI_MODE_DEFAULT%"=="terminology" set MODE_SELECT_DEFAULT=2
    if /i "%HAPI_MODE_DEFAULT%"=="both" set MODE_SELECT_DEFAULT=3
)
echo Enter choice 1/2/3 (default %MODE_SELECT_DEFAULT%)
set /p MODE_SELECT=Selection: 
if "%MODE_SELECT%"=="" set MODE_SELECT=%MODE_SELECT_DEFAULT%
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
setx CLUSTER_NAME "%CLUSTER_NAME%" >nul
set AWS_ACCESS_KEY_ID=%AWS_ACCESS_KEY_ID%
set AWS_SECRET_ACCESS_KEY=%AWS_SECRET_ACCESS_KEY%
set AWS_DEFAULT_REGION=%AWS_REGION%
set CLUSTER_NAME=%CLUSTER_NAME%

(
    if defined AWS_ACCESS_KEY_ID (echo AWS_ACCESS_KEY_ID=%AWS_ACCESS_KEY_ID%) else (echo AWS_ACCESS_KEY_ID=)
    if defined AWS_SECRET_ACCESS_KEY (echo AWS_SECRET_ACCESS_KEY=%AWS_SECRET_ACCESS_KEY%) else (echo AWS_SECRET_ACCESS_KEY=)
    if defined AWS_REGION (echo AWS_DEFAULT_REGION=%AWS_REGION%) else (echo AWS_DEFAULT_REGION=)
    if defined AWS_REGION (echo AWS_REGION=%AWS_REGION%) else (echo AWS_REGION=)
    if defined CLUSTER_NAME (echo CLUSTER_NAME=%CLUSTER_NAME%) else (echo CLUSTER_NAME=)
    if defined SSH_KEY_NAME (echo SSH_KEY_NAME=%SSH_KEY_NAME%) else (echo SSH_KEY_NAME=)
    if defined ENVIRONMENT (echo ENVIRONMENT=%ENVIRONMENT%) else (echo ENVIRONMENT=)
    if defined HAPI_MODE (echo HAPI_MODE=%HAPI_MODE%) else (echo HAPI_MODE=)
) > .env

:: --- Terraform apply ---
echo Initializing Terraform...
terraform init

echo Applying Terraform for %HAPI_MODE% mode...
terraform apply -auto-approve -var="aws_region=%AWS_REGION%" -var="ssh_key_name=%SSH_KEY_NAME%" -var="environment=%ENVIRONMENT%" -var="hapi_mode=%HAPI_MODE%" -var="cluster_name=%CLUSTER_NAME%"

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
