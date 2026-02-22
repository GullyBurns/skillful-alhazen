#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Help Function
show_help() {
    echo "Usage: ./update-channels.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -t, --target IP            Target IP address (Required)"
    echo "  --channel CHANNEL          Channel: telegram, whatsapp, discord, signal (Required)"
    echo "  --add-user USER_ID         Add user ID to channel allowFrom list"
    echo "  --remove-user USER_ID      Remove user ID from channel allowFrom list"
    echo "  --list                     List current allowFrom users for the channel"
    echo "  --target-type TYPE         Deployment target: 'vps' (default) or 'macmini'"
    echo "  --ssh-user USER            SSH User (Default: root)"
    echo "  --compose-project NAME     Compose project name (Default: openclaw-docker)"
    echo "  --ask-pass                 Ask for SSH/Sudo passwords"
    echo "  -h, --help                 Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./update-channels.sh -t 5.78.187.158 --channel telegram --add-user 7365829064"
    echo "  ./update-channels.sh -t 5.78.187.158 --channel telegram --remove-user 7365829064"
    echo "  ./update-channels.sh -t 5.78.187.158 --channel telegram --list"
    echo "  ./update-channels.sh -t 10.0.110.100 --target-type macmini --channel discord --add-user 123456"
}

TARGET_IP=""
TARGET_TYPE="vps"
SSH_USER="root"
COMPOSE_PROJECT="openclaw-docker"
ASK_PASS=false
CHANNEL=""
ADD_USER=""
REMOVE_USER=""
LIST_ONLY=false

# Parse Arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -t|--target) TARGET_IP="$2"; shift ;;
        --channel) CHANNEL="$2"; shift ;;
        --add-user) ADD_USER="$2"; shift ;;
        --remove-user) REMOVE_USER="$2"; shift ;;
        --list) LIST_ONLY=true ;;
        --target-type) TARGET_TYPE="$2"; shift ;;
        --ssh-user) SSH_USER="$2"; shift ;;
        --compose-project) COMPOSE_PROJECT="$2"; shift ;;
        --ask-pass) ASK_PASS=true ;;
        -h|--help) show_help; exit 0 ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

# Validation
if [ -z "$TARGET_IP" ]; then
    echo "Error: Target IP is required (-t)."
    exit 1
fi

if [ -z "$CHANNEL" ]; then
    echo "Error: Channel is required (--channel)."
    exit 1
fi

VALID_CHANNELS="telegram whatsapp discord signal"
if ! echo "$VALID_CHANNELS" | grep -qw "$CHANNEL"; then
    echo "Error: Invalid channel '$CHANNEL'. Must be one of: $VALID_CHANNELS"
    exit 1
fi

if [ "$LIST_ONLY" = false ] && [ -z "$ADD_USER" ] && [ -z "$REMOVE_USER" ]; then
    echo "Error: Must specify --add-user, --remove-user, or --list."
    exit 1
fi

# Determine action
ACTION="list"
USER_ID=""
if [ -n "$ADD_USER" ]; then
    ACTION="add"
    USER_ID="$ADD_USER"
elif [ -n "$REMOVE_USER" ]; then
    ACTION="remove"
    USER_ID="$REMOVE_USER"
fi

echo "Channel user management: $ACTION on $CHANNEL @ $TARGET_IP..."

# Create temporary inventory
TEMP_INVENTORY=$(mktemp)
echo "[alhazen_hosts]" > "$TEMP_INVENTORY"
if [ "$TARGET_IP" = "localhost" ]; then
    echo "localhost ansible_connection=local" >> "$TEMP_INVENTORY"
else
    echo "$TARGET_IP ansible_user=$SSH_USER" >> "$TEMP_INVENTORY"
fi

# Check Local Dependencies
check_dep() {
    if ! command -v "$1" &> /dev/null; then
        echo "Error: $1 is not installed locally. Please install it first."
        exit 1
    fi
}

check_dep ansible
check_dep ansible-playbook

# Ansible Args
ANSIBLE_ARGS=""
if [ "$ASK_PASS" = true ]; then
    ANSIBLE_ARGS="-k -K"
fi

# Run Playbook
ansible-playbook -i "$TEMP_INVENTORY" update-channels.yml $ANSIBLE_ARGS \
    --extra-vars "target_type='$TARGET_TYPE' compose_project_name='$COMPOSE_PROJECT' channel='$CHANNEL' channel_action='$ACTION' user_id='$USER_ID'"

# Cleanup
rm "$TEMP_INVENTORY"
echo "Done."
