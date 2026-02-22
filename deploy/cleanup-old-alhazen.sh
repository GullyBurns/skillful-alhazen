#!/bin/bash
set -e

# Cleanup script: Remove the old standalone Alhazen stack (separate user)
# Run this BEFORE deploying the merged OpenClaw+Alhazen stack
# Usage: ./cleanup-old-alhazen.sh -t <target-ip> [--ssh-key <path>] [--ssh-user <user>]

TARGET_IP=""
SSH_USER="root"
SSH_KEY=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -t|--target) TARGET_IP="$2"; shift ;;
        --ssh-user) SSH_USER="$2"; shift ;;
        --ssh-key) SSH_KEY="$2"; shift ;;
        -h|--help)
            echo "Usage: ./cleanup-old-alhazen.sh -t <target-ip> [--ssh-key <path>] [--ssh-user <user>]"
            echo ""
            echo "Removes the old standalone Alhazen stack (separate 'alhazen' user)"
            echo "before deploying the merged OpenClaw+Alhazen stack."
            exit 0
            ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

if [ -z "$TARGET_IP" ]; then
    echo "Error: Target IP required (-t)"
    exit 1
fi

SSH_CMD="ssh"
if [ -n "$SSH_KEY" ]; then
    SSH_CMD="ssh -i $SSH_KEY"
fi

echo "=================================================="
echo "  Cleaning up old standalone Alhazen stack"
echo "  Target: $TARGET_IP"
echo "=================================================="

$SSH_CMD "$SSH_USER@$TARGET_IP" bash -s <<'REMOTE_SCRIPT'
set -e

ALHAZEN_USER="alhazen"

# Check if alhazen user exists
if ! id "$ALHAZEN_USER" &>/dev/null; then
    echo "No alhazen user found. Nothing to clean up."
    exit 0
fi

ALHAZEN_UID=$(id -u "$ALHAZEN_USER")

echo "[1/4] Stopping Alhazen Podman stack..."
su - "$ALHAZEN_USER" -c "XDG_RUNTIME_DIR=/run/user/$ALHAZEN_UID podman-compose -f /home/$ALHAZEN_USER/alhazen-docker/docker-compose.yml down" 2>/dev/null || true

echo "[2/4] Removing all Alhazen containers and images..."
su - "$ALHAZEN_USER" -c "XDG_RUNTIME_DIR=/run/user/$ALHAZEN_UID podman rm -af" 2>/dev/null || true
su - "$ALHAZEN_USER" -c "XDG_RUNTIME_DIR=/run/user/$ALHAZEN_UID podman rmi -af" 2>/dev/null || true

echo "[3/4] Disabling linger for alhazen user..."
loginctl disable-linger "$ALHAZEN_USER" 2>/dev/null || true

echo "[4/4] Removing alhazen user and home directory..."
userdel -r "$ALHAZEN_USER" 2>/dev/null || true

echo ""
echo "Verifying ports are free..."
if ss -tlnp | grep -qE ':1729|:3000|:3001'; then
    echo "WARNING: Some ports still in use:"
    ss -tlnp | grep -E ':1729|:3000|:3001'
else
    echo "Ports 1729, 3000, 3001 are free."
fi

echo ""
echo "Cleanup complete."
REMOTE_SCRIPT

echo ""
echo "Done. Ready to deploy merged stack."
