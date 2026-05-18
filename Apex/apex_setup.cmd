: << 'WINDOWS_BATCH'
@echo off
setlocal EnableDelayedExpansion

REM ============================================================
REM APEX Setup Script - Windows/Linux Polyglot
REM This file runs as .bat on Windows and .sh on Linux
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
REM User Input: APEX HOST Setup
REM ============================================================
echo ============================================================
echo APEX HOST SETUP OPTIONS
echo ============================================================
echo.
echo APEX HOST (Steps 1-3):
echo   - Step 1: Set Registry Values (SMB settings)
echo   - Step 2: Run Prerequisite Installer
echo   - Step 3: Launch APEX Application
echo.
echo ============================================================
echo.
echo [INFO] Auto-selecting YES in 10 seconds if no input...
echo.

set "RUN_HOST=y"
choice /c yn /t 10 /d y /m "Do you want to run APEX HOST setup (Steps 1-3)?"
if %errorLevel% equ 2 set "RUN_HOST=n"

echo.

REM ============================================================
REM APEX HOST SETUP (Steps 1-3)
REM ============================================================
if /i "!RUN_HOST!"=="y" (
    echo.
    echo ############################################################
    echo # APEX HOST SETUP - Starting
    echo ############################################################
    echo.

    REM ============================================================
    REM Step 1: Set Registry Values
    REM ============================================================
    echo ------------------------------------------------------------
    echo Step 1: Setting Registry Values
    echo ------------------------------------------------------------

    reg add "HKLM\SYSTEM\CurrentControlSet\Services\LanmanWorkstation\Parameters" /v AllowInsecureGuestAuth /t REG_DWORD /d 1 /f
    if !errorLevel! equ 0 (
        echo [SUCCESS] Set AllowInsecureGuestAuth = 1
    ) else (
        echo [ERROR] Failed to set AllowInsecureGuestAuth
    )

    reg add "HKLM\SYSTEM\CurrentControlSet\Services\LanmanWorkstation\Parameters" /v RequireSecuritySignature /t REG_DWORD /d 0 /f
    if !errorLevel! equ 0 (
        echo [SUCCESS] Set RequireSecuritySignature = 0
    ) else (
        echo [ERROR] Failed to set RequireSecuritySignature
    )

    echo.

    REM ============================================================
    REM Step 2: Run Prerequisite Installer
    REM ============================================================
    echo ------------------------------------------------------------
    echo Step 2: Running Prerequisite Installer
    echo ------------------------------------------------------------

    set "PREREQ_PATH=\\saturn.amd.com\data\AutomationTools\APEX\apex-prereq-installer.bat"

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
        echo [INFO] Please ensure you have network access to saturn.amd.com
        set /p CONTINUE="Continue anyway? (y/n): "
        if /i not "!CONTINUE!"=="y" (
            echo [INFO] Exiting script.
            goto :EOF
        )
    )

    echo.

    REM ============================================================
    REM Step 3: Run APEX Application
    REM ============================================================
    echo ------------------------------------------------------------
    echo Step 3: Launching APEX Application
    echo ------------------------------------------------------------

    set "APEX_PATH=\\saturn.amd.com\data\automationtools\apex\APEX.application"

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
        echo       1. Add saturn.amd.com to Internet Explorer Trusted Sites:
        echo          - Open Internet Options ^> Security ^> Trusted Sites ^> Sites
        echo          - Add: file://saturn.amd.com
        echo       2. Or run this command as Admin to trust the publisher:
        echo          certutil -addstore TrustedPublisher ^<certificate.cer^>
        echo       3. Check if .NET Framework is properly installed
        echo.
        echo [INFO] Please interact with any prompts that appear
    ) else (
        echo [ERROR] Cannot access: !APEX_PATH!
        echo [INFO] Please ensure you have network access to saturn.amd.com
    )

    echo.
    echo ############################################################
    echo # APEX HOST SETUP - Completed
    echo ############################################################
    echo.
) else (
    echo.
    echo [SKIPPED] APEX HOST setup ^(Steps 1-3^) skipped by user
    echo.
)

REM ============================================================
REM User Input: APEX EXECUTOR Setup (after HOST setup)
REM ============================================================
echo.
echo ============================================================
echo APEX EXECUTOR SETUP OPTIONS
echo ============================================================
echo.
echo APEX EXECUTOR (Steps 4-5):
echo   - Step 4: Enable Administrator Account
echo   - Step 5: Copy and Run PostInstall.bat
echo.
echo ============================================================
echo.
echo [INFO] Auto-selecting YES in 10 seconds if no input...
echo.

set "RUN_EXECUTOR=y"
choice /c yn /t 10 /d y /m "Do you want to run APEX EXECUTOR setup (Steps 4-5)?"
if %errorLevel% equ 2 set "RUN_EXECUTOR=n"

echo.

REM ============================================================
REM APEX EXECUTOR SETUP (Steps 4-5)
REM ============================================================
if /i "!RUN_EXECUTOR!"=="y" (
    echo.
    echo ############################################################
    echo # APEX EXECUTOR SETUP - Starting
    echo ############################################################
    echo.

    REM ============================================================
    REM Step 4: Enable Administrator Account with Password
    REM ============================================================
    echo ------------------------------------------------------------
    echo Step 4: Enable Administrator Account
    echo ------------------------------------------------------------

    echo.
    echo [WARNING] This step will enable the built-in Administrator account
    echo          and set the password to: amdlabp@ssw0rd
    echo.
    echo          Command: net user administrator amdlabp@ssw0rd /active:yes
    echo.
    set /p ENABLE_ADMIN="Do you want to proceed? (y/n): "
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
    REM Step 5: Copy and Run PostInstall.bat
    REM ============================================================
    echo ------------------------------------------------------------
    echo Step 5: Running PostInstall Script
    echo ------------------------------------------------------------

    set "POSTINSTALL_SRC=\\saturn\drivers\drvpack64\Utils\PostInstall\scripts\PostInstall.bat"
    set "POSTINSTALL_DST=C:\PostInstall.bat"

    echo [INFO] Source: !POSTINSTALL_SRC!
    echo [INFO] Destination: !POSTINSTALL_DST!

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
) else (
    echo.
    echo [SKIPPED] APEX EXECUTOR setup ^(Steps 4-5^) skipped by user
    echo.
)

echo.
echo ============================================================
echo Setup script completed!
echo ============================================================
echo.
echo Summary:
if /i "!RUN_HOST!"=="y" (
    echo   APEX HOST ^(Steps 1-3^): Completed
) else (
    echo   APEX HOST ^(Steps 1-3^): Skipped
)
if /i "!RUN_EXECUTOR!"=="y" (
    echo   APEX EXECUTOR ^(Steps 4-5^): Completed
) else (
    echo   APEX EXECUTOR ^(Steps 4-5^): Skipped
)
echo.
echo If APEX prompts appeared, please complete them to finish installation.
echo.

pause
exit /b 0

WINDOWS_BATCH

#!/bin/bash
# ============================================================
# APEX Setup Script - Linux Section
# ============================================================

echo "============================================================"
echo "APEX Setup Script"
echo "Platform: Linux"
echo "============================================================"
echo ""

# Check for root privileges
if [ "$EUID" -ne 0 ]; then
    echo "[WARNING] This script requires root privileges."
    echo "[INFO] Please run with: sudo $0"
    exit 1
fi

echo "[INFO] Running with root privileges"
echo ""

# Function to read input with timeout (defaults to 'y' after 10 seconds)
read_with_timeout() {
    local prompt="$1"
    local default="y"
    local timeout=10
    local answer=""
    
    echo "[INFO] Auto-selecting YES in $timeout seconds if no input..."
    echo ""
    
    # Use read with timeout
    if read -t $timeout -p "$prompt" answer; then
        # User provided input
        if [ -z "$answer" ]; then
            echo "$default"
        else
            echo "$answer"
        fi
    else
        # Timeout occurred
        echo ""
        echo "[INFO] No input received, defaulting to YES"
        echo "$default"
    fi
}

# # ============================================================
# # User Input: APEX HOST Setup
# # ============================================================
# echo "============================================================"
# echo "APEX HOST SETUP OPTIONS"
# echo "============================================================"
# echo ""
# echo "APEX HOST (Steps 1-3):"
# echo "  - Step 1: Configure SMB Client Settings"
# echo "  - Step 2: Mount Network Share and Run Prerequisite Installer"
# echo "  - Step 3: APEX Application Notice"
# echo ""
# echo "============================================================"
# echo ""

# RUN_HOST=$(read_with_timeout "Do you want to run APEX HOST setup (Steps 1-3)? (y/n): ")
# echo ""

# # ============================================================
# # APEX HOST SETUP (Steps 1-3)
# # ============================================================
# if [ "$RUN_HOST" == "y" ] || [ "$RUN_HOST" == "Y" ]; then
#     echo ""
#     echo "############################################################"
#     echo "# APEX HOST SETUP - Starting"
#     echo "############################################################"
#     echo ""

#     # ============================================================
#     # Step 1: Configure SMB Client Settings
#     # ============================================================
#     echo "------------------------------------------------------------"
#     echo "Step 1: Configuring SMB Client Settings"
#     echo "------------------------------------------------------------"

#     # Install cifs-utils if not present
#     if ! command -v mount.cifs &> /dev/null; then
#         echo "[INFO] Installing cifs-utils..."
#         if command -v apt-get &> /dev/null; then
#             apt-get update && apt-get install -y cifs-utils
#         elif command -v yum &> /dev/null; then
#             yum install -y cifs-utils
#         elif command -v dnf &> /dev/null; then
#             dnf install -y cifs-utils
#         elif command -v pacman &> /dev/null; then
#             pacman -S --noconfirm cifs-utils
#         else
#             echo "[WARNING] Could not install cifs-utils automatically"
#         fi
#     fi

#     # Configure SMB settings
#     SMB_CONF="/etc/samba/smb.conf"
#     mkdir -p /etc/samba

#     if [ -f "$SMB_CONF" ]; then
#         if ! grep -q "client min protocol" "$SMB_CONF"; then
#             cp "$SMB_CONF" "${SMB_CONF}.backup"
#             echo "[INFO] Backed up existing config"
#             cat >> "$SMB_CONF" << 'SMBEOF'

# [global]
#    client min protocol = NT1
#    client lanman auth = yes
#    client ntlmv2 auth = yes
# SMBEOF
#             echo "[SUCCESS] Added SMB client settings"
#         else
#             echo "[INFO] SMB settings already configured"
#         fi
#     else
#         cat > "$SMB_CONF" << 'SMBEOF'
# [global]
#    client min protocol = NT1
#    client lanman auth = yes
#    client ntlmv2 auth = yes
# SMBEOF
#         echo "[SUCCESS] Created SMB configuration"
#     fi

#     echo ""

#     # ============================================================
#     # Step 2: Mount Network Share and Run Prerequisite Installer
#     # ============================================================
#     echo "------------------------------------------------------------"
#     echo "Step 2: Running Prerequisite Installer"
#     echo "------------------------------------------------------------"

#     SERVER="saturn.amd.com"
#     SHARE="data"
#     MOUNT_POINT="/mnt/saturn_data"
#     PREREQ_PATH="${MOUNT_POINT}/AutomationTools/APEX/apex-prereq-installer.bat"

#     # Create mount point
#     mkdir -p "$MOUNT_POINT"

#     # Try to mount the share
#     echo "[INFO] Attempting to mount network share..."

#     # Try guest mount first
#     if mount -t cifs "//${SERVER}/${SHARE}" "$MOUNT_POINT" -o guest,sec=none,vers=1.0 2>/dev/null; then
#         echo "[SUCCESS] Mounted share with guest access"
#     elif mount -t cifs "//${SERVER}/${SHARE}" "$MOUNT_POINT" -o guest,vers=2.0 2>/dev/null; then
#         echo "[SUCCESS] Mounted share with guest access (SMB2)"
#     else
#         echo "[INFO] Guest mount failed. Please enter credentials:"
#         read -p "Username: " SMB_USER
#         read -s -p "Password: " SMB_PASS
#         echo ""
        
#         if mount -t cifs "//${SERVER}/${SHARE}" "$MOUNT_POINT" -o "username=${SMB_USER},password=${SMB_PASS},vers=2.0" 2>/dev/null; then
#             echo "[SUCCESS] Mounted share with credentials"
#         else
#             echo "[ERROR] Failed to mount network share"
#             echo "[INFO] Please ensure you have network access to ${SERVER}"
#             read -p "Continue anyway? (y/n): " CONTINUE
#             if [ "$CONTINUE" != "y" ]; then
#                 exit 1
#             fi
#         fi
#     fi

#     # Check for prerequisite installer
#     if [ -f "$PREREQ_PATH" ]; then
#         echo "[WARNING] Prerequisite installer is a Windows batch file"
#         echo "[INFO] On Linux, batch files cannot run natively"
#         echo "[INFO] Options:"
#         echo "       1. Run this script on a Windows machine"
#         echo "       2. Use Wine: wine cmd /c '$PREREQ_PATH'"
#         echo "       3. Skip this step if prerequisites are already installed"
        
#         # Check if Wine is available
#         if command -v wine &> /dev/null; then
#             read -p "Attempt to run with Wine? (y/n): " USE_WINE
#             if [ "$USE_WINE" == "y" ]; then
#                 wine cmd /c "$PREREQ_PATH"
#             fi
#         fi
#     else
#         echo "[WARNING] Cannot access prerequisite installer"
#     fi

#     echo ""

#     # ============================================================
#     # Step 3: APEX Application
#     # ============================================================
#     echo "------------------------------------------------------------"
#     echo "Step 3: APEX Application Notice"
#     echo "------------------------------------------------------------"

#     APEX_PATH="${MOUNT_POINT}/automationtools/apex/APEX.application"

#     echo ""
#     echo "[WARNING] APEX.application is a Windows ClickOnce application"
#     echo "[INFO] ClickOnce applications cannot run natively on Linux"
#     echo ""
#     echo "Options to run APEX:"
#     echo "  1. Run this script on a Windows machine"
#     echo "  2. Use a Windows VM or Remote Desktop"
#     echo "  3. Use Wine with winetricks to install .NET"
#     echo ""

#     if [ -f "$APEX_PATH" ]; then
#         echo "[INFO] APEX application file found at: $APEX_PATH"
        
#         if command -v wine &> /dev/null; then
#             read -p "Attempt to run with Wine? (This may not work) (y/n): " USE_WINE
#             if [ "$USE_WINE" == "y" ]; then
#                 wine rundll32.exe dfshim.dll,ShOpenVerbApplication "$APEX_PATH"
#             fi
#         fi
#     fi

#     echo ""
#     echo "############################################################"
#     echo "# APEX HOST SETUP - Completed"
#     echo "############################################################"
#     echo ""
# else
#     echo ""
#     echo "[SKIPPED] APEX HOST setup (Steps 1-3) skipped by user"
#     echo ""
# fi

# ============================================================
# User Input: APEX EXECUTOR Setup (after HOST setup)
# ============================================================
echo ""
echo "============================================================"
echo "APEX EXECUTOR SETUP OPTIONS"
echo "============================================================"
echo ""
echo "APEX EXECUTOR (Steps 4-11):"
echo "  - Step 4: Set Root Password"
echo "  - Step 5: Configure Auto-Login for Root"
echo "  - Step 6: Update Timezone and System Time"
echo "  - Step 7: Update Package Lists (apt update)"
echo "  - Step 8: Install Required Packages"
echo "  - Step 9: Download apex_exec.zip"
echo "  - Step 10: Extract apex_exec.zip with Permissions"
echo "  - Step 11: Configure Auto-Start in .bashrc"
echo ""
echo "============================================================"
echo ""

RUN_EXECUTOR=$(read_with_timeout "Do you want to run APEX EXECUTOR setup (Steps 4-11)? (y/n): ")
echo ""

# ============================================================
# APEX EXECUTOR SETUP (Steps 4-10)
# ============================================================
if [ "$RUN_EXECUTOR" == "y" ] || [ "$RUN_EXECUTOR" == "Y" ]; then
    # echo ""
    # echo "############################################################"
    # echo "# APEX EXECUTOR SETUP - Starting"
    # echo "############################################################"
    # echo ""

    # # ============================================================
    # # Step 4: Set Root Password
    # # ============================================================
    # echo "------------------------------------------------------------"
    # echo "Step 4: Setting Root Password"
    # echo "------------------------------------------------------------"

    # echo "[INFO] Setting root password..."
    # usermod --password $(echo password | openssl passwd -1 -stdin) root
    # if [ $? -eq 0 ]; then
    #     echo "[SUCCESS] Root password has been set"
    # else
    #     echo "[ERROR] Failed to set root password"
    # fi

    echo ""

    # ============================================================
    # Step 5: Configure Auto-Login for Root
    # ============================================================
    echo "------------------------------------------------------------"
    echo "Step 5: Configuring Auto-Login for Root"
    echo "------------------------------------------------------------"

    GETTY_SERVICE="/lib/systemd/system/getty@.service"

    if [ -f "$GETTY_SERVICE" ]; then
        # Backup original file
        cp "$GETTY_SERVICE" "${GETTY_SERVICE}.backup"
        echo "[INFO] Backed up original getty@.service"
        
        # Comment out the original ExecStart lines and add autologin
        sed -i 's|^ExecStart=-/sbin/agetty -o.*$|# &|' "$GETTY_SERVICE"
        sed -i 's|^ExecStart=-/sbin/agetty --noclear.*$|# &|' "$GETTY_SERVICE"
        
        # Check if autologin is already configured
        if ! grep -q "autologin root" "$GETTY_SERVICE"; then
            # Add the autologin ExecStart line
            sed -i '/^\[Service\]/a ExecStart=-/sbin/agetty --noissue --autologin root %I $TERM' "$GETTY_SERVICE"
            echo "[SUCCESS] Added auto-login configuration for root"
        else
            echo "[INFO] Auto-login already configured"
        fi
        
        # Reload systemd to apply changes
        systemctl daemon-reload
        echo "[SUCCESS] Systemd configuration reloaded"
    else
        echo "[WARNING] getty@.service not found at $GETTY_SERVICE"
        echo "[INFO] Manual configuration required:"
        echo "       1. Run: sudo nano /lib/systemd/system/getty@.service"
        echo "       2. Comment out: ExecStart=-/sbin/agetty -o '-p -- \\u' --noclear %I \$TERM"
        echo "       3. Add: ExecStart=-/sbin/agetty --noissue --autologin root %I \$TERM"
    fi

    echo ""

    # ============================================================
    # Step 6: Update Timezone and System Time
    # ============================================================
    echo "------------------------------------------------------------"
    echo "Step 6: Updating Timezone and System Time"
    echo "------------------------------------------------------------"

    # Show current time info
    echo "[INFO] Current timezone: $(cat /etc/timezone 2>/dev/null || timedatectl show --property=Timezone --value 2>/dev/null || echo 'Unknown')"
    echo "[INFO] Current time: $(date)"

    # Try to sync time with NTP
    if command -v timedatectl &> /dev/null; then
        timedatectl set-ntp true 2>/dev/null
        echo "[SUCCESS] NTP time synchronization enabled"
    fi

    # Force sync time if possible
    if command -v ntpdate &> /dev/null; then
        ntpdate -u pool.ntp.org 2>/dev/null && echo "[SUCCESS] Time synced with NTP server"
    elif command -v chronyd &> /dev/null; then
        chronyc makestep 2>/dev/null && echo "[SUCCESS] Time synced via chrony"
    elif command -v systemctl &> /dev/null; then
        systemctl restart systemd-timesyncd 2>/dev/null && echo "[INFO] Restarted time sync service"
    fi

    echo "[INFO] Updated system time: $(date)"

    echo ""

    # ============================================================
    # Step 7: Update Package Lists
    # ============================================================
    echo "------------------------------------------------------------"
    echo "Step 7: Updating Package Lists (apt update)"
    echo "------------------------------------------------------------"

    echo "[INFO] Running apt update..."
    apt update
    if [ $? -eq 0 ]; then
        echo "[SUCCESS] Package lists updated"
    else
        echo "[WARNING] apt update had some issues, continuing..."
    fi

    echo ""

    # ============================================================
    # Step 8: Install Required Packages
    # ============================================================
    echo "------------------------------------------------------------"
    echo "Step 8: Installing Required Packages"
    echo "------------------------------------------------------------"

    PACKAGES="ruby lshw cifs-utils net-tools"
    echo "[INFO] Installing: $PACKAGES"

    apt install -y $PACKAGES
    if [ $? -eq 0 ]; then
        echo "[SUCCESS] All packages installed successfully"
    else
        echo "[WARNING] Some packages may have failed to install"
    fi

    # Verify installations
    echo ""
    echo "[INFO] Verifying installations:"
    for pkg in ruby lshw cifs-utils net-tools; do
        if dpkg -l | grep -q "^ii  $pkg"; then
            echo "       [OK] $pkg"
        else
            echo "       [MISSING] $pkg"
        fi
    done

    echo ""

    # ============================================================
    # Step 9: Download apex_exec.zip
    # ============================================================
    echo "------------------------------------------------------------"
    echo "Step 9: Downloading apex_exec.zip"
    echo "------------------------------------------------------------"

    APEX_EXEC_URL="http://ouray/utils/apex_exec/apex_exec.zip"
    APEX_EXEC_DEST="/root/apex_exec.zip"

    echo "[INFO] Downloading from: $APEX_EXEC_URL"
    echo "[INFO] Saving to: $APEX_EXEC_DEST"

    wget -P /root/ "$APEX_EXEC_URL"
    if [ $? -eq 0 ]; then
        echo "[SUCCESS] Downloaded apex_exec.zip"
    else
        echo "[ERROR] Failed to download apex_exec.zip"
        echo "[INFO] Please ensure you have network access to ouray"
    fi

    echo ""

    # ============================================================
    # Step 10: Extract apex_exec.zip with Permissions
    # ============================================================
    echo "------------------------------------------------------------"
    echo "Step 10: Extracting apex_exec.zip"
    echo "------------------------------------------------------------"

    APEX_EXEC_DIR="/usr/local/bin/apex_exec"

    if [ -f "$APEX_EXEC_DEST" ]; then
        # Set permissions on the zip file first
        chmod 777 "$APEX_EXEC_DEST"
        echo "[INFO] Set permissions (chmod 777) on zip file"
        
        # Create destination directory
        mkdir -p "$APEX_EXEC_DIR"
        chmod 777 "$APEX_EXEC_DIR"
        
        # Extract
        echo "[INFO] Extracting to: $APEX_EXEC_DIR"
        unzip -o "$APEX_EXEC_DEST" -d "$APEX_EXEC_DIR"
        
        if [ $? -eq 0 ]; then
            echo "[SUCCESS] Extracted apex_exec.zip"
            
            # Set permissions on all extracted files (chmod 777 for read/write)
            echo "[INFO] Setting permissions (chmod 777) on all extracted files..."
            chmod -R 777 "$APEX_EXEC_DIR"
            echo "[SUCCESS] Permissions set on all files in $APEX_EXEC_DIR"
            
            # List extracted files
            echo ""
            echo "[INFO] Extracted files:"
            ls -la "$APEX_EXEC_DIR"
        else
            echo "[ERROR] Failed to extract apex_exec.zip"
        fi
    else
        echo "[ERROR] apex_exec.zip not found at $APEX_EXEC_DEST"
        echo "[INFO] Please download it manually:"
        echo "       wget -P /root/ $APEX_EXEC_URL"
        echo "       chmod 777 /root/apex_exec.zip"
        echo "       unzip /root/apex_exec.zip -d $APEX_EXEC_DIR"
        echo "       chmod -R 777 $APEX_EXEC_DIR"
    fi

    echo ""

    # ============================================================
    # Step 11: Configure Auto-Start in .bashrc
    # ============================================================
    echo "------------------------------------------------------------"
    echo "Step 11: Configuring Auto-Start in .bashrc"
    echo "------------------------------------------------------------"

    BASHRC_FILE="/root/.bashrc"
    APEX_MARKER="# APEX Auto-Start"

    # Check if the auto-start code already exists
    if grep -q "$APEX_MARKER" "$BASHRC_FILE" 2>/dev/null; then
        echo "[INFO] Auto-start code already exists in $BASHRC_FILE"
        echo "[SKIPPED] No changes made to .bashrc"
    else
        # Create .bashrc if it doesn't exist
        if [ ! -f "$BASHRC_FILE" ]; then
            touch "$BASHRC_FILE"
            echo "[INFO] Created $BASHRC_FILE"
        fi

        # Append the auto-start code
        echo "[INFO] Adding auto-start code to $BASHRC_FILE"
        cat >> "$BASHRC_FILE" << 'BASHRC_EOF'

# APEX Auto-Start
running=`ps -ef | grep "[a]pex_exec.rb" | wc -l`
if [ $running -lt 1 ] && [ $(tty) == /dev/tty1 ];then
    cd /usr/local/bin/apex_exec
    ruby /usr/local/bin/apex_exec/apex_exec.rb
fi
BASHRC_EOF

        if [ $? -eq 0 ]; then
            echo "[SUCCESS] Auto-start code added to $BASHRC_FILE"
        else
            echo "[ERROR] Failed to update $BASHRC_FILE"
        fi
    fi

    echo ""
    echo "############################################################"
    echo "# APEX EXECUTOR SETUP - Completed"
    echo "############################################################"
    echo ""
else
    echo ""
    echo "[SKIPPED] APEX EXECUTOR setup (Steps 4-10) skipped by user"
    echo ""
fi

# # Cleanup - unmount share if it was mounted
# if mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
#     read -p "Unmount network share? (y/n): " UNMOUNT
#     if [ "$UNMOUNT" == "y" ]; then
#         umount "$MOUNT_POINT" 2>/dev/null && echo "[INFO] Share unmounted"
#     fi
# fi

echo ""
echo "============================================================"
echo "Linux Setup Script Completed!"
echo "============================================================"
# echo ""
# echo "Summary:"
# if [ "$RUN_HOST" == "y" ] || [ "$RUN_HOST" == "Y" ]; then
#     echo "  APEX HOST (Steps 1-3): Completed"
# else
#     echo "  APEX HOST (Steps 1-3): Skipped"
# fi
# if [ "$RUN_EXECUTOR" == "y" ] || [ "$RUN_EXECUTOR" == "Y" ]; then
#     echo "  APEX EXECUTOR (Steps 4-10): Completed"
# else
#     echo "  APEX EXECUTOR (Steps 4-10): Skipped"
# fi
echo ""
echo "Note: A reboot may be required for auto-login to take effect."
