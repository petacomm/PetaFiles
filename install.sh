#!/usr/bin/env bash
# ─────────────────────────────────────────────
#  PetaFiles Installer
#  https://kotechsoft.com/petafiles.html
# ─────────────────────────────────────────────

set -e

INSTALL_DIR="/usr/local/bin"
SCRIPT_NAME="petafiles"
SCRIPT_URL="https://repo.kotechsoft.com/petafiles/petafiles.py"
LOCAL_SCRIPT="$(dirname "$0")/petafiles.py"
REPO_LIST="/etc/apt/sources.list.d/kotech.list"
REPO_URL="https://repo.kotechsoft.com"
GPG_URL="https://repo.kotechsoft.com/kotech-petacomm.gpg"
GPG_KEY="/etc/apt/keyrings/kotech.gpg"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
RESET='\033[0m'

echo ""
echo -e "${BOLD}  PetaFiles — Terminal File Manager${RESET}"
echo -e "  ${CYAN}The file manager your terminal deserved.${RESET}"
echo ""

# ── Check Python ──────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}  ✗ Python 3 not found.${RESET}"
    echo ""
    echo "  Install it with:"
    echo "    Debian/Ubuntu : sudo apt install python3"
    echo "    Fedora/RHEL   : sudo dnf install python3"
    echo "    Arch          : sudo pacman -S python"
    echo ""
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "  ${GREEN}✓${RESET} Python ${PY_VERSION} found"

# ── Check / add Kotech repo ───────────────────
echo ""
echo -e "  ${BOLD}Checking Kotech Petacomm repository...${RESET}"

REPO_READY=false

if [ -f "$REPO_LIST" ]; then
    echo -e "  ${GREEN}✓${RESET} Kotech repo already configured"
    REPO_READY=true
else
    echo -e "  ${YELLOW}⬇${RESET}  Kotech repo not found, adding..."
    # GPG key
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL "$GPG_URL" | sudo gpg --dearmor -o "$GPG_KEY" 2>/dev/null || \
        { echo -e "${RED}  ✗ Failed to add GPG key.${RESET}"; exit 1; }
    # Repo entry
    echo "deb [signed-by=${GPG_KEY}] ${REPO_URL} stable main" | sudo tee "$REPO_LIST" > /dev/null
    echo -e "  ${GREEN}✓${RESET} Kotech repo added"
    sudo apt-get update -qq
    REPO_READY=true
fi

# ── Check micro in repo ───────────────────────
echo ""
echo -e "  ${BOLD}Checking micro editor in repository...${RESET}"

MICRO_IN_REPO=false
if apt-cache show micro &>/dev/null 2>&1; then
    echo -e "  ${GREEN}✓${RESET} micro is available in the repository"
    MICRO_IN_REPO=true
else
    echo -e "  ${YELLOW}⚠${RESET}  micro not found in repo, fetching and adding..."

    # Download latest micro .deb from upstream
    MICRO_VERSION=$(curl -fsSL https://api.github.com/repos/zyedidia/micro/releases/latest \
        | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'].lstrip('v'))" 2>/dev/null || echo "2.0.13")
    MICRO_DEB_URL="https://github.com/zyedidia/micro/releases/download/v${MICRO_VERSION}/micro-${MICRO_VERSION}-amd64.deb"
    MICRO_DEB="/tmp/micro_${MICRO_VERSION}_amd64.deb"

    echo -e "  ${YELLOW}⬇${RESET}  Downloading micro v${MICRO_VERSION}..."
    curl -fsSL "$MICRO_DEB_URL" -o "$MICRO_DEB" || \
        { echo -e "${RED}  ✗ Failed to download micro.${RESET}"; exit 1; }

    # Copy deb into repo pool and reindex
    POOL_DIR="/var/www/repo/pool/main"
    if [ -d "$POOL_DIR" ]; then
        sudo cp "$MICRO_DEB" "$POOL_DIR/"
        echo -e "  ${GREEN}✓${RESET} micro added to repo pool, reindexing..."
        (
            cd /var/www/repo
            sudo dpkg-scanpackages pool/main /dev/null 2>/dev/null | sudo tee dists/stable/main/binary-amd64/Packages > /dev/null
            sudo dpkg-scanpackages pool/main /dev/null 2>/dev/null | gzip -9c | sudo tee dists/stable/main/binary-amd64/Packages.gz > /dev/null
            sudo apt-ftparchive release dists/stable 2>/dev/null | sudo tee dists/stable/Release > /dev/null
            sudo gpg --batch --yes -abs -o dists/stable/Release.gpg dists/stable/Release 2>/dev/null || true
            sudo gpg --batch --yes --clearsign -o dists/stable/InRelease dists/stable/Release 2>/dev/null || true
        )
        sudo apt-get update -qq
        MICRO_IN_REPO=true
        echo -e "  ${GREEN}✓${RESET} micro is now in the repository"
    else
        # Repo pool not on this machine — just install the deb directly
        echo -e "  ${YELLOW}ℹ${RESET}  Repo pool not found on this machine, installing micro directly..."
        sudo apt-get install -y "$MICRO_DEB" 2>/dev/null || sudo dpkg -i "$MICRO_DEB" || true
        MICRO_IN_REPO=false
    fi
fi

# ── Ask default editor ────────────────────────
echo ""
echo -e "  ${BOLD}Which editor would you like to set as default?${RESET}"
echo ""
echo -e "    ${BOLD}1)${RESET} nano"
echo -e "    ${BOLD}2)${RESET} micro  ${GREEN}(Recommended — easier & modern)${RESET}"
echo ""
printf "  Your choice [1/2, default: 2]: "
read -r EDITOR_CHOICE
echo ""

CHOSEN_EDITOR="micro"
if [ "$EDITOR_CHOICE" = "1" ]; then
    CHOSEN_EDITOR="nano"
fi

# ── Install chosen editor ─────────────────────
if [ "$CHOSEN_EDITOR" = "micro" ]; then
    if command -v micro &>/dev/null; then
        echo -e "  ${GREEN}✓${RESET} micro already installed ($(micro --version 2>/dev/null | head -1))"
    elif [ "$MICRO_IN_REPO" = true ]; then
        echo -e "  ${YELLOW}⬇${RESET}  Installing micro from Kotech repo..."
        sudo apt-get install -y micro -qq
        echo -e "  ${GREEN}✓${RESET} micro installed"
    else
        echo -e "  ${YELLOW}⬇${RESET}  Installing micro..."
        sudo apt-get install -y micro -qq 2>/dev/null || \
        sudo dpkg -i /tmp/micro_*_amd64.deb 2>/dev/null || \
            { echo -e "${RED}  ✗ Could not install micro. Falling back to nano.${RESET}"; CHOSEN_EDITOR="nano"; }
        [ "$CHOSEN_EDITOR" = "micro" ] && echo -e "  ${GREEN}✓${RESET} micro installed"
    fi
else
    if ! command -v nano &>/dev/null; then
        echo -e "  ${YELLOW}⬇${RESET}  Installing nano..."
        sudo apt-get install -y nano -qq
    fi
    echo -e "  ${GREEN}✓${RESET} nano ready"
fi

# ── Set EDITOR in shell rc files ─────────────
EDITOR_LINE="export EDITOR=${CHOSEN_EDITOR}"
VISUAL_LINE="export VISUAL=${CHOSEN_EDITOR}"

for RC in "$HOME/.bashrc" "$HOME/.zshrc"; do
    if [ -f "$RC" ]; then
        # Remove old EDITOR/VISUAL lines set by us, then append
        sed -i '/^export EDITOR=/d' "$RC"
        sed -i '/^export VISUAL=/d' "$RC"
        echo "$EDITOR_LINE" >> "$RC"
        echo "$VISUAL_LINE" >> "$RC"
        echo -e "  ${GREEN}✓${RESET} Set EDITOR=${CHOSEN_EDITOR} in $(basename $RC)"
    fi
done

# Also export for current session
export EDITOR="$CHOSEN_EDITOR"
export VISUAL="$CHOSEN_EDITOR"

# ── Install PetaFiles ─────────────────────────
echo ""
echo -e "  ${BOLD}Installing PetaFiles...${RESET}"

if [ -f "$LOCAL_SCRIPT" ]; then
    SOURCE="$LOCAL_SCRIPT"
    echo -e "  ${GREEN}✓${RESET} Using local petafiles.py"
else
    echo -e "  ${YELLOW}⬇${RESET}  Downloading petafiles..."
    if $REPO_READY && apt-cache show petafiles &>/dev/null 2>&1; then
        sudo apt-get install -y petafiles -qq
        echo -e "  ${GREEN}✓${RESET} petafiles installed via apt"
        SOURCE=""
    else
        TMP=$(mktemp /tmp/petafiles_XXXX.py)
        curl -fsSL "$SCRIPT_URL" -o "$TMP" || wget -qO "$TMP" "$SCRIPT_URL" || \
            { echo -e "${RED}  ✗ Download failed.${RESET}"; exit 1; }
        SOURCE="$TMP"
        echo -e "  ${GREEN}✓${RESET} Downloaded"
    fi
fi

if [ -n "$SOURCE" ]; then
    DEST="${INSTALL_DIR}/${SCRIPT_NAME}"
    if [ ! -w "$INSTALL_DIR" ]; then
        sudo install -m 755 "$SOURCE" "$DEST"
    else
        install -m 755 "$SOURCE" "$DEST"
    fi
    # Ensure shebang
    if ! head -1 "$DEST" | grep -q "python3"; then
        TMP2=$(mktemp)
        echo '#!/usr/bin/env python3' | cat - "$DEST" > "$TMP2"
        sudo mv "$TMP2" "$DEST"
        sudo chmod 755 "$DEST"
    fi
    echo -e "  ${GREEN}✓${RESET} Installed → ${DEST}"
fi

# ── Config dir ────────────────────────────────
if [ -d "$HOME/.config/petafiles" ]; then
    echo -e "  ${GREEN}✓${RESET} Config dir already exists"
else
    mkdir -p "$HOME/.config/petafiles"
    echo -e "  ${GREEN}✓${RESET} Created ~/.config/petafiles"
fi

# ── Done ──────────────────────────────────────
echo ""
echo -e "  ${BOLD}${GREEN}All done!${RESET}"
echo ""
echo -e "  ${BOLD}PetaFiles${RESET}"
echo -e "    ${CYAN}petafiles${RESET}              # start in current dir"
echo -e "    ${CYAN}petafiles ~/projects${RESET}   # start in specific dir"
echo ""
echo -e "  ${BOLD}Default editor:${RESET} ${CHOSEN_EDITOR}"
echo -e "  ${BOLD}Shortcuts:${RESET} h/l navigate  j/k up/down  e edit  ? help  q quit"
echo ""
echo -e "  ${YELLOW}Note:${RESET} Restart your shell or run ${CYAN}source ~/.bashrc${RESET} to apply editor changes."
echo ""
echo -e "  To uninstall: ${YELLOW}sudo apt remove petafiles${RESET}"
echo ""
