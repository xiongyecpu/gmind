#!/usr/bin/env bash
set -euo pipefail

# install-skill.sh -- Install the gmind-cli skill for AI agents
#
# check: detects Hermes & OpenClaw presence
# install: always writes to ~/.config/agents/skills/gmind-cli/
#   (agentskills.io-compatible agents read from here)
#
# Usage: ./install-skill.sh
#        ./install-skill.sh --check
#        ./install-skill.sh --help

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_SRC="$SCRIPT_DIR/skills/gmind-cli/SKILL.md"
SKILL_DST="$HOME/.config/agents/skills/gmind-cli"
SKILL_AGENTS_DST="$HOME/.agents/skills/gmind-cli"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

warn()  { echo -e "${YELLOW}WARN${NC}: $1"; }
err()   { echo -e "${RED}ERR${NC}: $1"; }
ok()    { echo -e "${GREEN}OK${NC}: $1"; }
info()  { echo "INFO: $1"; }

check_source() {
    if [[ ! -f "$SKILL_SRC" ]]; then
        err "Skill source not found: $SKILL_SRC"
        exit 1
    fi
}

check_agents() {
    info "Checking installed agents..."
    local found=0

    if [[ -d "$HOME/.hermes" ]]; then
        echo "  Hermes:     $HOME/.hermes"
        found=$((found+1))
    else
        echo "  Hermes:     (not found)"
    fi

    if [[ -d "$HOME/.agents/skills" ]]; then
        echo "  Agents:     $HOME/.agents/skills"
        found=$((found+1))
    else
        echo "  Agents:     (not found)"
    fi

    if [[ -d "$HOME/.openclaw" ]]; then
        echo "  OpenClaw:   $HOME/.openclaw"
        found=$((found+1))
    else
        echo "  OpenClaw:   (not found)"
    fi

    echo ""
    if [[ $found -eq 0 ]]; then
        warn "No agents detected."
    else
        ok "Found $found agent(s)"
    fi
    echo "  Install target: $SKILL_DST"
}

install_skill() {
    check_source
    mkdir -p "$SKILL_DST"
    cp "$SKILL_SRC" "$SKILL_DST/SKILL.md"
    chmod 600 "$SKILL_DST/SKILL.md"
    ok "Installed: $SKILL_DST/SKILL.md"

    # Also symlink to ~/.agents/skills/ for Hermes & other agents
    if [[ -d "$HOME/.agents/skills" ]]; then
        if [[ -L "$SKILL_AGENTS_DST" ]] || [[ -e "$SKILL_AGENTS_DST" ]]; then
            rm -rf "$SKILL_AGENTS_DST"
        fi
        ln -s "$SKILL_DST" "$SKILL_AGENTS_DST"
        ok "Linked: $SKILL_AGENTS_DST -> $SKILL_DST"
    else
        warn "Skipped agents link: $HOME/.agents/skills not found"
    fi
}

print_help() {
    cat <<'EOF'
Usage: ./install-skill.sh [options]

Install the gmind-cli skill for AI agents.

  check: detects Hermes & OpenClaw presence
  install: writes to ~/.config/agents/skills/gmind-cli/ and links to ~/.agents/skills/

Options:
  --check         Show detected agents without installing
  -h, --help      Show this help

Examples:
  ./install-skill.sh        # Install to ~/.config/agents/skills/ + ~/.agents/skills/
  ./install-skill.sh --check # Check which agents are present
EOF
}

# --- Main ---

case "${1:-}" in
    -h|--help)
        print_help
        exit 0
        ;;
    --check)
        check_agents
        exit 0
        ;;
    "")
        install_skill
        ;;
    *)
        err "Unknown option: $1"
        print_help
        exit 1
        ;;
esac
