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
    echo [SKIPPED] APEX HOST registry edit ^(Steps 1^) skipped by user
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
REM User Input: APEX EXECUTOR Setup
REM ============================================================
echo.
echo ============================================================
echo APEX EXECUTOR SETUP OPTIONS
echo ============================================================
echo.
echo APEX EXECUTOR (Steps 3-4):
echo   - Step 3: Enable Administrator Account
echo   - Step 4: Copy and Run PostInstall.bat
echo.
echo ============================================================
echo.

REM ============================================================
REM APEX EXECUTOR SETUP (Steps 3-4)
REM ============================================================

echo.
echo ############################################################
echo # APEX EXECUTOR SETUP - Starting
echo ############################################################
echo.

REM ============================================================
REM Step 3: Enable Administrator Account with Password
REM ============================================================
echo ------------------------------------------------------------
echo Step 3: Enable Administrator Account
echo ------------------------------------------------------------

echo.
echo [WARNING] This step will enable the built-in Administrator account
echo          and set the password to: amdlabp@ssw0rd, auto-selecting YES in 10 seconds if no input...
echo.
echo          Command: net user administrator amdlabp@ssw0rd /active:yes
echo.

set "ENABLE_ADMIN=y"
choice /c yn /t 10 /d y /m "Do you want to proceed? (y/n): "
if !errorLevel! equ 2 set "ENABLE_ADMIN=n"

if /i "!ENABLE_ADMIN!"=="y" (
    net user administrator amdlabp@ssw0rd /active:yes
    if !errorLevel! equ 0 (
        echo [SUCCESS] Administrator account enabled and password set
    ) else (
        echo [ERROR] Failed to enable administrator account
    )
) else (
    echo [SKIPPED] Administrator account setup skipped by user
)

echo.

REM ============================================================
REM Step 4: Copy and Run PostInstall.bat
REM ============================================================
echo ------------------------------------------------------------
echo Step 4: Running PostInstall Script
echo ------------------------------------------------------------

set "POSTINSTALL_SRC=\\saturn\drivers\drvpack64\Utils\PostInstall\scripts\PostInstall.bat"
set "POSTINSTALL_DST=C:\PostInstall.bat"

echo [INFO] Source: %POSTINSTALL_SRC%
echo [INFO] Destination: %POSTINSTALL_DST%

if exist "!POSTINSTALL_SRC!" (
    echo [INFO] Copying PostInstall.bat to C: drive...
    copy "!POSTINSTALL_SRC!" "!POSTINSTALL_DST!" /Y
    if !errorLevel! equ 0 (
        echo [SUCCESS] Copied PostInstall.bat to C:\
        echo.
        echo [WARNING] PostInstall.bat may prompt for username and password.
        echo [INFO] Running PostInstall.bat...
        echo.
        call "!POSTINSTALL_DST!"
        if !errorLevel! equ 0 (
            echo [SUCCESS] PostInstall.bat completed
        ) else (
            echo [WARNING] PostInstall.bat exited with code: !errorLevel!
        )
    ) else (
        echo [ERROR] Failed to copy PostInstall.bat
    )
) else (
    echo [ERROR] Cannot access: !POSTINSTALL_SRC!
    echo [INFO] Please ensure you have network access to saturn
    set /p CONTINUE="Continue anyway? (y/n): "
    if /i not "!CONTINUE!"=="y" (
        echo [INFO] Exiting script.
        goto :EOF
    )
)

echo.
echo ############################################################
echo # APEX EXECUTOR SETUP - Completed
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