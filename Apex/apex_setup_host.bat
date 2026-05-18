@echo off
setlocal EnableDelayedExpansion

REM ============================================================
REM APEX Setup Script - Windows
REM ============================================================

echo ============================================================
echo APEX Setup Script
echo Platform: Windows
echo ============================================================
echo.

REM Check for Administrator privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [WARNING] This script requires Administrator privileges.
    echo [INFO] Attempting to restart with elevated privileges...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo [INFO] Running with Administrator privileges
echo.

REM ============================================================
REM APEX PREREQUISITES SETUP (Steps 1-2)
REM ============================================================

echo.
echo ############################################################
echo # APEX PREREQUISITES SETUP - Starting
echo ############################################################
echo.

REM ============================================================
REM Step 1: Set Registry Values
REM ============================================================
echo ------------------------------------------------------------
echo Step 1: Setting Registry Values
echo ------------------------------------------------------------
echo.
echo [INFO] Auto-selecting YES in 5 seconds if no input...
echo.

set "RUN_REGISTRY_EDIT=y"
choice /c yn /t 5 /d y /m "Do you want to run APEX REGISTRY edit (Step 1)?"
if %errorLevel% equ 2 set "RUN_REGISTRY_EDIT=n"

if /i "!RUN_REGISTRY_EDIT!"=="y" (
    reg add "HKLM\SYSTEM\CurrentControlSet\Services\LanmanWorkstation\Parameters" /v AllowInsecureGuestAuth /t REG_DWORD /d 1 /f
    if %errorLevel% equ 0 (
        echo [SUCCESS] Set AllowInsecureGuestAuth = 1
    ) else (
        echo [ERROR] Failed to set AllowInsecureGuestAuth
    )

    reg add "HKLM\SYSTEM\CurrentControlSet\Services\LanmanWorkstation\Parameters" /v RequireSecuritySignature /t REG_DWORD /d 0 /f
    if %errorLevel% equ 0 (
        echo [SUCCESS] Set RequireSecuritySignature = 0
    ) else (
        echo [ERROR] Failed to set RequireSecuritySignature
    )
) else (
    echo.
    echo [SKIPPED] APEX HOST registry edit ^(Steps 1-3^) skipped by user
    echo.
)

echo.

REM ============================================================
REM Step 2: Run Prerequisite Installer
REM ============================================================
echo ------------------------------------------------------------
echo Step 2: Running Prerequisite Installer
echo ------------------------------------------------------------

set "PREREQ_PATH=\\saturn\data\AutomationTools\APEX\apex-prereq-installer.bat"

if exist "!PREREQ_PATH!" (
    echo [INFO] Running: !PREREQ_PATH!
    echo [INFO] Auto-sending Enter key presses to proceed through prompts...
    
    REM Create a temp file with multiple Enter key presses to feed into the installer
    set "TEMP_INPUT=%TEMP%\apex_input.txt"
    (
        echo.
        echo.
        echo.
        echo.
        echo.
        echo.
        echo.
        echo.
        echo.
        echo.
    ) > "!TEMP_INPUT!"
    
    REM Run the installer with auto-input
    call "!PREREQ_PATH!" < "!TEMP_INPUT!"
    set "PREREQ_EXIT=!errorLevel!"
    
    REM Cleanup temp file
    del "!TEMP_INPUT!" 2>nul
    
    if !PREREQ_EXIT! equ 0 (
        echo [SUCCESS] Prerequisite installer completed
    ) else (
        echo [WARNING] Prerequisite installer exited with code: !PREREQ_EXIT!
    )
) else (
    echo [ERROR] Cannot access: !PREREQ_PATH!
    echo [INFO] Please ensure you have network access to saturn
    echo [INFO] Auto-selecting YES in 10 seconds if no input...

    set "CONTINUE=y"
    choice /c yn /t 5 /d y /m "Continue anyway? (y/n): "
    if %errorLevel% equ 2 set "CONTINUE=n" (
        echo [INFO] Exiting script.
        goto :EOF
    )
)

echo.

REM ============================================================
REM User Input: APEX HOST Setup
REM ============================================================
echo ============================================================
echo APEX HOST SETUP OPTIONS
echo ============================================================
echo.
echo APEX HOST (Steps 3):
echo   - Step 3: Launch APEX Application
echo.
echo ============================================================
echo.

REM ============================================================
REM Step 3: Run APEX Application
REM ============================================================
echo ------------------------------------------------------------
echo Step 3: Launching APEX Application
echo ------------------------------------------------------------

set "APEX_PATH=\\saturn\data\automationtools\apex\APEX.application"

echo.
echo ============================================================
echo IMPORTANT: Interactive prompts may appear!
echo ============================================================
echo 1. If a SIGN-IN window appears, please enter your credentials
echo 2. If a SECURITY WARNING appears ^(untrusted publisher^),
echo    click 'Install' or 'Run' to proceed
echo ============================================================
echo.

timeout /t 3 /nobreak >nul

set "APEX_LAUNCHED=0"

if exist "!APEX_PATH!" (
    echo [INFO] Launching: !APEX_PATH!
    echo [INFO] Trying multiple launch methods...
    
    REM Method 1: Add the network location to trusted sites and launch via PowerShell
    if "!APEX_LAUNCHED!"=="0" (
        echo [INFO] Method 1: PowerShell Invoke-Item...
        powershell -Command "& { try { Invoke-Item '!APEX_PATH!' } catch { exit 1 } }" 2>nul
        if !errorLevel! equ 0 (
            echo [SUCCESS] APEX application launch initiated via PowerShell
            set "APEX_LAUNCHED=1"
        )
    )
    
    REM Method 2: Use explorer.exe
    if "!APEX_LAUNCHED!"=="0" (
        echo [INFO] Method 2: Explorer...
        start "" explorer.exe "!APEX_PATH!"
        timeout /t 2 /nobreak >nul
    )
    
    REM Method 3: Copy to local temp and run from there
    if "!APEX_LAUNCHED!"=="0" (
        echo [INFO] Method 3: Copying to local and launching...
        set "LOCAL_APEX=%TEMP%\APEX.application"
        copy "!APEX_PATH!" "!LOCAL_APEX!" >nul 2>&1
        if exist "!LOCAL_APEX!" (
            start "" "!LOCAL_APEX!"
            echo [INFO] Launched from local copy
            set "APEX_LAUNCHED=1"
        )
    )
    
    REM Method 4: Use dfsvc.exe directly (ClickOnce deployment service)
    if "!APEX_LAUNCHED!"=="0" (
        echo [INFO] Method 4: Using dfsvc.exe...
        if exist "%SystemRoot%\Microsoft.NET\Framework64\v4.0.30319\dfsvc.exe" (
            start "" "%SystemRoot%\Microsoft.NET\Framework64\v4.0.30319\dfsvc.exe" "!APEX_PATH!"
            set "APEX_LAUNCHED=1"
        ) else if exist "%SystemRoot%\Microsoft.NET\Framework\v4.0.30319\dfsvc.exe" (
            start "" "%SystemRoot%\Microsoft.NET\Framework\v4.0.30319\dfsvc.exe" "!APEX_PATH!"
            set "APEX_LAUNCHED=1"
        )
    )
    
    REM Method 5: Direct file association (fallback)
    if "!APEX_LAUNCHED!"=="0" (
        echo [INFO] Method 5: Direct launch...
        start "" "!APEX_PATH!"
    )
    
    echo.
    echo [INFO] If you see "Application cannot be started" error:
    echo       This is usually due to ClickOnce trust/certificate issues.
    echo.
    echo       Solutions:
    echo       1. Add saturn to Internet Explorer Trusted Sites:
    echo          - Open Internet Options ^> Security ^> Trusted Sites ^> Sites
    echo          - Add: file://saturn
    echo       2. Or run this command as Admin to trust the publisher:
    echo          certutil -addstore TrustedPublisher ^<certificate.cer^>
    echo       3. Check if .NET Framework is properly installed
    echo.
    echo [INFO] Please interact with any prompts that appear
) else (
    echo [ERROR] Cannot access: !APEX_PATH!
    echo [INFO] Please ensure you have network access to saturn
)

echo.
echo ############################################################
echo # APEX HOST SETUP - Completed
echo ############################################################
echo.

echo.
echo ============================================================
echo Setup script completed!
echo ============================================================
echo.
echo If APEX prompts appeared, please complete them to finish installation.
echo.

pause
exit /b 0