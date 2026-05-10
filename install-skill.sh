#!/usr/bin/env bash
set -euo pipefail

# install-skill.sh -- Install the gmind-cli skill for AI agents
#
# Supports: Hermes, OpenClaw, Kimi Code CLI (and any agentskills.io-compatible agent)
# Usage: ./install-skill.sh [agent1,agent2,...]
#        ./install-skill.sh hermes,openclaw,kimi
#        ./install-skill.sh --all
#        ./install-skill.sh --check

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_SRC="$SCRIPT_DIR/skills/gmind-cli/SKILL.md"

# Target directories per agent
HERMES_DIR="$HOME/.hermes/skills/gmind-cli"
OPENCLAW_DIR="$HOME/.openclaw/skills/gmind-cli"
KIMI_DIR="$HOME/.config/agents/skills/gmind-cli"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

warn()  { echo -e "${YELLOW}WARN${NC}: $1"; }
err()   { echo -e "${RED}ERR${NC}: $1"; }
ok()    { echo -e "${GREEN}OK${NC}: $1"; }
info()  { echo "INFO: $1"; }

check_source() {
    if [[ ! -f "$SKILL_SRC" ]]; then
        err "Skill source not found: $SKILL_SRC"
        exit 1
    fi
    ok "Source: $SKILL_SRC"
}

check_agent_dir() {
    local dir="$1"
    local name="$2"
    if [[ -d "$(dirname "$dir")" ]]; then
        echo "  $name: $dir"
        return 0
    fi
    echo "  $name: $dir (not detected)"
    return 1
}

detect_agents() {
    info "Detecting agents..."
    local found=0
    check_agent_dir "$HERMES_DIR" "Hermes" && found=$((found+1))
    check_agent_dir "$OPENCLAW_DIR" "OpenClaw" && found=$((found+1))
    check_agent_dir "$KIMI_DIR" "Kimi Code CLI" && found=$((found+1))
    if [[ $found -eq 0 ]]; then
        warn "No known agents detected."
        info "You can still install manually by specifying agent names."
    else
        ok "Found $found agent(s)"
    fi
    return 0
}

install_to() {
    local dir="$1"
    local name="$2"

    if [[ ! -d "$(dirname "$dir")" ]]; then
        warn "$name not detected, skipping"
        return 1
    fi

    mkdir -p "$dir"
    cp "$SKILL_SRC" "$dir/SKILL.md"
    chmod 600 "$dir/SKILL.md"
    ok "Installed to $name: $dir/SKILL.md"
    return 0
}

print_help() {
    cat <<'EOF'
Usage: ./install-skill.sh [options] [agents]

Install the gmind-cli SKILL.md to AI agent directories.

Options:
  --all           Install to all detected agents
  --check         List detected agents without installing
  -h, --help      Show this help

Agents (comma-separated):
  hermes          ~/.hermes/skills/gmind-cli/
  openclaw        ~/.openclaw/skills/gmind-cli/
  kimi            ~/.config/agents/skills/gmind-cli/

Examples:
  ./install-skill.sh --check          # Detect agents
  ./install-skill.sh --all            # Install everywhere detected
  ./install-skill.sh hermes           # Install to Hermes only
  ./install-skill.sh hermes,openclaw  # Install to Hermes + OpenClaw
EOF
}

# --- Main ---

check_source

# Parse args
TARGETS=""
MODE=""

for arg in "$@"; do
    case "$arg" in
        -h|--help)
            print_help
            exit 0
            ;;
        --all)
            MODE="all"
            ;;
        --check)
            MODE="check"
            ;;
        *)
            if [[ -n "$TARGETS" ]]; then
                TARGETS="$TARGETS,$arg"
            else
                TARGETS="$arg"
            fi
            ;;
    esac
done

if [[ "$MODE" == "check" ]]; then
    detect_agents
    exit 0
fi

if [[ "$MODE" == "all" ]]; then
    install_to "$HERMES_DIR" "Hermes"
    install_to "$OPENCLAW_DIR" "OpenClaw"
    install_to "$KIMI_DIR" "Kimi Code CLI"
    exit 0
fi

if [[ -z "$TARGETS" ]]; then
    # No args: detect and install to all found
    info "No targets specified. Auto-installing to detected agents..."
    installed=0
    install_to "$HERMES_DIR" "Hermes" && installed=$((installed+1)) || true
    install_to "$OPENCLAW_DIR" "OpenClaw" && installed=$((installed+1)) || true
    install_to "$KIMI_DIR" "Kimi Code CLI" && installed=$((installed+1)) || true
    if [[ $installed -eq 0 ]]; then
        err "No agents detected. Run with --help for usage."
        exit 1
    fi
    exit 0
fi

# Parse comma-separated targets
IFS=',' read -ra AGENTS <<< "$TARGETS"
for agent in "${AGENTS[@]}"; do
    case "$(echo "$agent" | tr '[:upper:]' '[:lower:]')" in
        hermes)
            install_to "$HERMES_DIR" "Hermes"
            ;;
        openclaw)
            install_to "$OPENCLAW_DIR" "OpenClaw"
            ;;
        kimi|kimi-code|kimi-code-cli)
            install_to "$KIMI_DIR" "Kimi Code CLI"
            ;;
        *)
            err "Unknown agent: $agent"
            ;;
    esac
done
