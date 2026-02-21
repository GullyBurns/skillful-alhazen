#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Help Function
show_help() {
    echo "Usage: ./deploy.sh [OPTIONS]"
    echo ""
    echo "Deploy OpenClaw agent + Alhazen knowledge notebook to a target host."
    echo "Creates a hardened stack with: OpenClaw (AI agent + Telegram), TypeDB,"
    echo "Alhazen MCP server, Dashboard, LiteLLM proxy, and Squid egress filter."
    echo ""
    echo "Options:"
    echo "  -t, --target IP          Target IP address (use 'localhost' for local Mac Mini)"
    echo "  --target-type TYPE       Deployment target: 'vps' (default) or 'macmini'"
    echo "  -p, --provider NAME      LLM Provider (anthropic, openai, ollama, openai_compatible)"
    echo "  -m, --model NAME         Model Name (e.g., claude-sonnet-4-6)"
    echo "  -u, --url URL            API Base URL (for ollama/openai_compatible)"
    echo "  -k, --key KEY            API Key"
    echo "  --branch BRANCH          Alhazen repo branch to deploy (default: main)"
    echo "  --project-name NAME      Compose project name (default: openclaw)"
    echo "  --port-offset N          Offset shared ports by N (e.g., 10000 → TypeDB:11729)"
    echo "  --ssh-user USER          Initial SSH User (Default: root)"
    echo "  --ssh-key PATH           Path to private key for SSH connection"
    echo "  --ask-pass               Ask for SSH and Sudo passwords"
    echo "  --non-interactive        Fail if missing arguments instead of prompting"
    echo "  -h, --help               Show this help message"
    echo ""
}

# Defaults
TARGET_IP=""
TARGET_TYPE="vps"
SSH_USER=""
LLM_PROVIDER=""
LLM_MODEL=""
LLM_URL=""
LLM_KEY=""
DEPLOY_BRANCH="main"
PROJECT_NAME=""
PORT_OFFSET=0
INTERACTIVE=true
ASK_PASS=false
SSH_KEY=""

# Parse Arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -t|--target) TARGET_IP="$2"; shift ;;
        --target-type) TARGET_TYPE="$2"; shift ;;
        -p|--provider) LLM_PROVIDER="$2"; shift ;;
        -m|--model) LLM_MODEL="$2"; shift ;;
        -u|--url) LLM_URL="$2"; shift ;;
        -k|--key) LLM_KEY="$2"; shift ;;
        --branch) DEPLOY_BRANCH="$2"; shift ;;
        --project-name) PROJECT_NAME="$2"; shift ;;
        --port-offset) PORT_OFFSET="$2"; shift ;;
        --ssh-user) SSH_USER="$2"; shift ;;
        --ssh-key) SSH_KEY="$2"; shift ;;
        --ask-pass) ASK_PASS=true ;;
        --non-interactive) INTERACTIVE=false ;;
        -h|--help) show_help; exit 0 ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

# --- Interactive Prompts ---

if [ "$INTERACTIVE" = true ]; then
    echo "=================================================="
    echo "   OpenClaw + Alhazen Hardened Deployment"
    echo "=================================================="
    echo ""

    # Target Type
    if [ "$TARGET_TYPE" = "vps" ]; then
        echo "Select deployment target:"
        echo "  1) Linux VPS (Default) — Podman rootless, UFW, Fail2Ban"
        echo "  2) Mac Mini — Docker Desktop, pf firewall"
        read -p "Choice [1-2]: " target_choice
        case $target_choice in
            2) TARGET_TYPE="macmini" ;;
            *) TARGET_TYPE="vps" ;;
        esac
    fi

    # Target IP
    if [ -z "$TARGET_IP" ]; then
        if [ "$TARGET_TYPE" = "macmini" ]; then
            read -p "Enter Target Host IP [localhost]: " TARGET_IP
            TARGET_IP="${TARGET_IP:-localhost}"
        else
            read -p "Enter Target Host IP: " TARGET_IP
        fi
    fi

    # SSH User (Prompt if not set)
    if [ -z "$SSH_USER" ]; then
        echo "Enter Initial SSH User (e.g., 'root' for bare metal, 'ubuntu' for AWS):"
        read -p "User [root]: " input_user
        SSH_USER="${input_user:-root}"
    fi

    # SSH Key (Prompt if not set)
    if [ -z "$SSH_KEY" ] && [ "$ASK_PASS" = false ]; then
        echo ""
        echo "Enter path to SSH Private Key (leave empty to use default/ssh-agent):"
        read -p "Key Path: " input_key
        SSH_KEY="${input_key}"
    fi

    # Provider
    if [ -z "$LLM_PROVIDER" ]; then
        echo ""
        echo "Select LLM Provider:"
        echo "  1) Anthropic (Default)"
        echo "  2) OpenAI"
        echo "  3) Ollama"
        echo "  4) OpenAI Compatible"
        read -p "Choice [1-4]: " provider_choice
        case $provider_choice in
            2) LLM_PROVIDER="openai" ;;
            3) LLM_PROVIDER="ollama" ;;
            4) LLM_PROVIDER="openai_compatible" ;;
            *) LLM_PROVIDER="anthropic" ;;
        esac
    fi

    # Model Name
    if [ -z "$LLM_MODEL" ]; then
        echo ""
        default_model=""
        if [ "$LLM_PROVIDER" == "anthropic" ]; then default_model="claude-sonnet-4-6"; fi
        if [ "$LLM_PROVIDER" == "openai" ]; then default_model="gpt-4o"; fi
        if [ "$LLM_PROVIDER" == "ollama" ]; then default_model="llama3"; fi

        read -p "Enter Model Name [$default_model]: " input_model
        LLM_MODEL="${input_model:-$default_model}"
    fi

    # Base URL (Conditional)
    if [ -z "$LLM_URL" ]; then
        if [ "$LLM_PROVIDER" == "ollama" ]; then
            echo ""
            read -p "Enter Ollama Base URL [http://10.0.110.1:11434]: " input_url
            LLM_URL="${input_url:-http://10.0.110.1:11434}"
        elif [ "$LLM_PROVIDER" == "openai_compatible" ]; then
            echo ""
            read -p "Enter API Base URL: " LLM_URL
        fi
    fi

    # API Key (Conditional)
    if [ -z "$LLM_KEY" ]; then
        if [ "$LLM_PROVIDER" != "ollama" ]; then
            echo ""
            read -s -p "Enter API Key: " LLM_KEY
            echo ""
        else
            LLM_KEY="ollama"
        fi
    fi
fi

# --- Validation ---

if [ -z "$TARGET_IP" ]; then
    echo "Error: Target IP is required."
    exit 1
fi

if [ -z "$SSH_USER" ]; then SSH_USER="root"; fi
if [ -z "$LLM_PROVIDER" ]; then LLM_PROVIDER="anthropic"; fi
if [ -z "$LLM_MODEL" ] && [ "$LLM_PROVIDER" == "anthropic" ]; then LLM_MODEL="claude-sonnet-4-6"; fi
if [ -z "$LLM_MODEL" ] && [ "$LLM_PROVIDER" == "ollama" ]; then LLM_MODEL="llama3"; fi
if [ -z "$LLM_URL" ] && [ "$LLM_PROVIDER" == "ollama" ]; then LLM_URL="http://10.0.110.1:11434"; fi
if [ -z "$LLM_KEY" ]; then LLM_KEY="sk-placeholder"; fi

if [ "$TARGET_TYPE" != "vps" ] && [ "$TARGET_TYPE" != "macmini" ]; then
    echo "Error: --target-type must be 'vps' or 'macmini'"
    exit 1
fi

# --- Port Offset & Project Name ---

if [ "$PORT_OFFSET" -gt 0 ] 2>/dev/null; then
    TYPEDB_HOST_PORT=$((1729 + PORT_OFFSET))
    MCP_HOST_PORT=$((3000 + PORT_OFFSET))
    DASHBOARD_HOST_PORT=$((3001 + PORT_OFFSET))
else
    TYPEDB_HOST_PORT=1729
    MCP_HOST_PORT=3000
    DASHBOARD_HOST_PORT=3001
fi

if [ -z "$PROJECT_NAME" ]; then
    PROJECT_NAME="openclaw-docker"
fi

# Container prefix: derive from project name
# openclaw-docker → alhazen (default), openclaw-hardened → hardened
CONTAINER_PREFIX="${PROJECT_NAME##*-}"
if [ "$CONTAINER_PREFIX" = "docker" ]; then
    CONTAINER_PREFIX="alhazen"
fi

# --- Execution ---

echo ""
echo "Deploying Configuration:"
echo "----------------------------------------"
echo "Target:      $TARGET_IP"
echo "Target Type: $TARGET_TYPE"
echo "User:        $SSH_USER"
if [ -n "$SSH_KEY" ]; then echo "SSH Key:     $SSH_KEY"; fi
echo "Provider:    $LLM_PROVIDER"
echo "Model:       $LLM_MODEL"
echo "Branch:      $DEPLOY_BRANCH"
echo "Project:     $PROJECT_NAME"
echo "Prefix:      $CONTAINER_PREFIX"
if [ "$PORT_OFFSET" -gt 0 ] 2>/dev/null; then
echo "Port Offset: +$PORT_OFFSET (TypeDB:$TYPEDB_HOST_PORT, MCP:$MCP_HOST_PORT, Dashboard:$DASHBOARD_HOST_PORT)"
fi
echo "----------------------------------------"

# Create temporary inventory
TEMP_INVENTORY=$(mktemp)
echo "[openclaw_hosts]" > "$TEMP_INVENTORY"
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

check_dep openssl
check_dep ssh-keygen
check_dep ansible
check_dep ansible-playbook

# Check Wordlist
if [ ! -f "eff_large_wordlist.txt" ]; then
    echo "Error: eff_large_wordlist.txt not found in deploy/ directory."
    exit 1
fi

# Install Ansible Requirements
echo "Installing Ansible collections..."
ansible-galaxy collection install -r requirements.yml > /dev/null

# Run Ansible
ANSIBLE_ARGS=""
if [ "$ASK_PASS" = true ]; then
    ANSIBLE_ARGS="-k -K"
fi

if [ -n "$SSH_KEY" ]; then
    ANSIBLE_ARGS="$ANSIBLE_ARGS --private-key=$SSH_KEY"
fi

ansible-playbook -i "$TEMP_INVENTORY" playbook.yml $ANSIBLE_ARGS \
    --extra-vars "llm_provider='$LLM_PROVIDER' llm_model='$LLM_MODEL' llm_url='$LLM_URL' llm_key='$LLM_KEY' target_type='$TARGET_TYPE' deploy_branch='$DEPLOY_BRANCH' compose_project_name='$PROJECT_NAME' container_prefix='$CONTAINER_PREFIX' typedb_host_port='$TYPEDB_HOST_PORT' mcp_host_port='$MCP_HOST_PORT' dashboard_host_port='$DASHBOARD_HOST_PORT'"

# Cleanup
rm "$TEMP_INVENTORY"

echo ""
echo "Deployment finished."
