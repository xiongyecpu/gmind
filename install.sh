#!/usr/bin/env bash
set -euo pipefail

# install.sh — One-shot installer for GMind
#
# Usage:
#   git clone https://github.com/xiongyecpu/gmind.git
#   cd gmind
#   ./install.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}INFO${NC}  $1"; }
ok()    { echo -e "${GREEN}OK${NC}    $1"; }
warn()  { echo -e "${YELLOW}WARN${NC}  $1"; }
err()   { echo -e "${RED}ERR${NC}   $1"; }

# ------------------------------------------------------------------
# 1. Environment checks
# ------------------------------------------------------------------
info "Checking environment..."

if ! command -v python3 &>/dev/null; then
    err "python3 not found. Please install Python 3.12+ first."
    exit 1
fi

PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
info "Python version: $PY_VER"

if ! command -v uv &>/dev/null; then
    warn "uv not found. Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Try to source the new PATH
    export PATH="$HOME/.local/bin:$PATH"
    if ! command -v uv &>/dev/null; then
        err "uv installation failed. Please install manually: https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    fi
fi
ok "uv: $(uv --version)"

# ------------------------------------------------------------------
# 2. Install gmind Python package
# ------------------------------------------------------------------
info "Installing gmind package..."
cd "$SCRIPT_DIR"
uv tool install -e "."
ok "gmind package installed"

# Verify binary is available
if ! command -v gmind &>/dev/null; then
    warn "gmind command not found in PATH"
    info "Please add the following to your shell profile (~/.bashrc / ~/.zshrc):"
    echo '    export PATH="$HOME/.local/bin:$PATH"'
fi

# ------------------------------------------------------------------
# 3. Agent skill (optional)
# ------------------------------------------------------------------
if [[ -d "$HOME/.config/agents/skills" ]] || [[ -d "$HOME/.agents/skills" ]]; then
    info "Installing agent skill..."
    bash "$SCRIPT_DIR/install-skill.sh"
fi

# ------------------------------------------------------------------
# 4. Configuration check
# ------------------------------------------------------------------
CONFIG_PATH="${HOME}/.gmind/config.toml"
if [[ -f "$CONFIG_PATH" ]]; then
    ok "Config found: $CONFIG_PATH"
else
    warn "GMind config not found."
    echo ""
    echo "Run the following to initialize:"
    echo ""
    echo "    gmind init"
    echo ""
    echo "It will ask for:"
    echo "  - PostgreSQL connection URL"
    echo "  - Embedding API key (SiliconFlow)"
    echo "  - Embedding model name"
    echo ""
fi

# ------------------------------------------------------------------
# 5. Done
# ------------------------------------------------------------------
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  GMind installation complete!              ${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "Quick start:"
echo ""
echo "  # 1. Initialize (if first time)"
echo "  gmind init"
echo ""
echo "  # 2. Start the HTTP server for Chrome extension"
echo "  gmind serve --port 8765"
echo ""
echo "  # 3. Load Chrome extension"
echo "     Chrome → Extensions → Developer mode ON"
echo "     → Load unpacked → select: $(basename "$SCRIPT_DIR")/chrome-extension/"
echo ""
echo "  # 4. Try it"
echo "  gmind stats"
echo ""
