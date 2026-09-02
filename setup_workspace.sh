#!/bin/bash

# ==============================================================================
# PIONEER / PRINCIPAL ENGINEER MACOS WORKSPACE AUTOMATION SCRIPT
# ==============================================================================
# Target OS: macOS (Intel or Apple Silicon)
# Core Tools: Homebrew, Ghostty, Raycast, Bruno, JetBrains Mono, Cursor/VSCode Config
# ==============================================================================

set -e # Exit immediately if a command exits with a non-zero status

echo "🚀 Starting your Pioneer Workspace automation setup..."

# ------------------------------------------------------------------------------
# 1. CHECK / INSTALL HOMEBREW
# ------------------------------------------------------------------------------
if ! command -v brew &> /dev/null; then
    echo "📦 Homebrew not found. Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://githubusercontent.com)"
    
    # Configure Homebrew for the current shell session
    if [[ "$(uname -m)" == "arm64" ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    else
        eval "$(/usr/local/bin/brew shellenv)"
    fi
else
    echo "✅ Homebrew is already installed. Updating..."
    brew update
fi

# ------------------------------------------------------------------------------
# 2. INSTALL ULTIMATE MACOS APPS & UTILITIES (Casks)
# ------------------------------------------------------------------------------
echo "🖥️ Installing macOS GUI applications..."

# Tap the fonts repository to allow downloading developer fonts
brew tap homebrew/cask-fonts 2>/dev/null || true

apps=(
    ghostty               # Lightning fast, GPU-accelerated terminal
    raycast               # Lightweight, keyboard-driven Spotlight replacement
    bruno                 # Open-source, git-friendly API Client
    ollama                # Local LLM sandbox for offline AI compilation
    font-jetbrains-mono   # World-class coding font with rich ligature support
)

for app in "${apps[@]}"; do
    if brew list --cask "$app" &> /dev/null; then
        echo "✅ $app is already installed."
    else
        echo "📥 Installing $app..."
        brew install --cask "$app"
    fi
done

# ------------------------------------------------------------------------------
# 3. CONFIGURE VS CODE / CURSOR GLOBAL SETTINGS
# ------------------------------------------------------------------------------
echo "⚙️ Injecting Principal Engineer configurations into your settings..."

# Define possible configuration paths for both VS Code and Cursor
VSCODE_SETTING_DIR="$HOME/Library/Application Support/Code/User"
CURSOR_SETTING_DIR="$HOME/Library/Application Support/Cursor/User"

SETTINGS_JSON=$(cat <<EOF
{
  "editor.fontFamily": "'JetBrains Mono', monospace",
  "editor.fontLigatures": true,
  "editor.fontSize": 14,
  "editor.lineHeight": 1.6,
  "editor.minimap.enabled": false,
  "workbench.sideBar.location": "right",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.fixAll": "explicit"
  },
  "telemetry.telemetryLevel": "off",
  "workbench.activityBar.location": "default",
  "editor.scrollbar.vertical": "hidden",
  "editor.scrollbar.horizontal": "hidden"
}
EOF
)

# Apply settings to VS Code if directory exists
if [ -d "$VSCODE_SETTING_DIR" ]; then
    echo "$SETTINGS_JSON" > "$VSCODE_SETTING_DIR/settings.json"
    echo "✅ VS Code configuration applied."
else
    mkdir -p "$VSCODE_SETTING_DIR"
    echo "$SETTINGS_JSON" > "$VSCODE_SETTING_DIR/settings.json"
    echo "✅ VS Code folder created and configuration applied."
fi

# Apply settings to Cursor if directory exists
if [ -d "$CURSOR_SETTING_DIR" ]; then
    echo "$SETTINGS_JSON" > "$CURSOR_SETTING_DIR/settings.json"
    echo "✅ Cursor configuration applied."
else
    mkdir -p "$CURSOR_SETTING_DIR"
    echo "$SETTINGS_JSON" > "$CURSOR_SETTING_DIR/settings.json"
    echo "✅ Cursor folder created and configuration applied."
fi

# ------------------------------------------------------------------------------
# 4. OPTIMIZE NETWORK BUFFER SIZES FOR LARGE REPOS
# ------------------------------------------------------------------------------
echo "🌐 Optimizing Git buffer size configurations to prevent RPC network failures..."
git config --global http.postBuffer 524288000

# ------------------------------------------------------------------------------
# 5. COMPLETION
# ------------------------------------------------------------------------------
echo "=========================================================================="
echo "🎉 SUCCESS! Your high-performance workspace is officially initialized."
echo "=========================================================================="
echo "👉 Next steps to take manually:"
echo "1. Open 'Raycast' from Applications to set up your hotkey shortcut."
echo "2. Open 'Ghostty' to verify your lightning-fast terminal environment."
echo "3. Run 'ollama run llama3' in Ghostty to launch your local AI sandbox."
echo "=========================================================================="

