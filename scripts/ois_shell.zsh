# Niceone Obsidian — OIS shell integration
# Source from an interactive zsh session after installing the package.

[[ -o interactive ]] || return 0

# Prefer the installed console entry point, but keep `python -m ois` as a fallback.
ois() {
    if (( $+commands[ois] )); then
        command ois "$@"
    else
        python -m ois "$@"
    fi
}

# Safe, explicit shortcuts for common operator views.
alias ois-status='ois status'
alias ois-doctor='ois doctor'
alias ois-verify='ois verify'
alias ois-health='ois health'
alias ois-capabilities='ois capabilities'
alias ois-agents='ois agents'
alias ois-tools='ois tools'
alias ois-workflows='ois workflows'

# Keep fundamental shell commands unmodified. Use `c` for the enhanced clear UX.
ois-clear() {
    command clear
    if (( $+commands[oh-my-posh] )); then
        oh-my-posh notice
    fi
}
alias c='ois-clear'

# Optional developer aliases; only install when the backing commands exist.
(( $+commands[btm] )) && alias top='btm'
(( $+commands[lazygit] )) && alias gitlog='lazygit'
(( $+commands[bat] )) && alias cat='bat'
(( $+commands[gping] )) && alias ping='gping'
