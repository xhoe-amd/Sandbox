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