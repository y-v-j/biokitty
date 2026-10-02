#!/usr/bin/env bash
#
# biokitty installer
#
# Copies the kitty, fastfetch and helper files into place and wires the banner
# into ~/.bashrc. Existing files are backed up with a .bak-<timestamp> suffix
# rather than overwritten.
#
#   ./install.sh              install
#   ./install.sh --dry-run    print what would happen, change nothing
#   ./install.sh --uninstall  restore the most recent backups and unhook bashrc
#
# Layout after installing:
#
#   ~/.config/kitty/          kitty.conf + ui/keys/marks/diff/open-actions,
#                             tab_bar.py, themes/, sessions/, kittens/
#   ~/.config/fastfetch/      banner configs and logo images
#   ~/.local/bin/             biokitty-theme, biokitty-seq, biokitty-accession

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
DRY_RUN=0
UNINSTALL=0

KITTY_DIR="$HOME/.config/kitty"
FF_DIR="$HOME/.config/fastfetch"
BIN_DIR="$HOME/.local/bin"

for arg in "$@"; do
    case "$arg" in
        --dry-run)   DRY_RUN=1 ;;
        --uninstall) UNINSTALL=1 ;;
        -h|--help)   sed -n '2,20p' "$0"; exit 0 ;;
        *) echo "unknown option: $arg" >&2; exit 2 ;;
    esac
done

say() { printf '%s\n' "$*"; }
run() { if [[ $DRY_RUN == 1 ]]; then say "  would: $*"; else "$@"; fi; }

MARKER_START='# >>> biokitty banner >>>'
MARKER_END='# <<< biokitty banner <<<'

# Earlier versions of this project were installed by hand under a different
# marker. Find that block and replace it rather than appending a second copy:
# two banner blocks are not harmful (the KITTY_BANNER_SHOWN guard stops the
# second from drawing) but the aliases and PATH line in the new block would
# never be reached past the old one.
LEGACY_START='# >>> kitty DNA banner >>>'
LEGACY_END='# <<< kitty DNA banner <<<'

backup_bashrc() {
    [[ -e "$HOME/.bashrc" ]] || return 0
    if [[ ! -e "$HOME/.bashrc.bak-$STAMP" ]]; then
        say "  backing up ~/.bashrc -> ~/.bashrc.bak-$STAMP"
        run cp -p "$HOME/.bashrc" "$HOME/.bashrc.bak-$STAMP"
    fi
}

# ---------------------------------------------------------------------------
if [[ $UNINSTALL == 1 ]]; then
    say "Removing the bashrc hook..."
    found=0
    if grep -qF "$MARKER_START" "$HOME/.bashrc" 2>/dev/null; then
        backup_bashrc
        run sed -i "/${MARKER_START//\//\\/}/,/${MARKER_END//\//\\/}/d" "$HOME/.bashrc"
        say "  unhooked"
        found=1
    fi
    if grep -qF "$LEGACY_START" "$HOME/.bashrc" 2>/dev/null; then
        backup_bashrc
        run sed -i "/${LEGACY_START//\//\\/}/,/${LEGACY_END//\//\\/}/d" "$HOME/.bashrc"
        say "  removed the legacy 'kitty DNA banner' block"
        found=1
    fi
    (( found )) || say "  no hook found"

    say
    say "Removing installed helper commands..."
    for b in biokitty-theme biokitty-seq biokitty-accession; do
        [[ -e "$BIN_DIR/$b" ]] && run rm -f "$BIN_DIR/$b" && say "  removed $BIN_DIR/$b"
    done

    say
    say "Config files were left in place. Restore a backup by hand if you want:"
    ls -1 "$KITTY_DIR"/kitty.conf.bak-* "$FF_DIR"/config.jsonc.bak-* 2>/dev/null \
        || say "  (no backups found)"
    exit 0
fi

# ---------------------------------------------------------------------------
say "biokitty — installing from $REPO"
[[ $DRY_RUN == 1 ]] && say "(dry run; nothing will change)"
say

# 1. Dependencies -----------------------------------------------------------
missing=()
command -v kitty     >/dev/null 2>&1 || [[ -x "$HOME/.local/kitty.app/bin/kitty" ]] || missing+=(kitty)
command -v fastfetch >/dev/null 2>&1 || [[ -x /usr/bin/fastfetch ]]                 || missing+=(fastfetch)
if (( ${#missing[@]} )); then
    say "Missing: ${missing[*]}"
    say "  kitty:     https://sw.kovidgoyal.net/kitty/binary/"
    say "  fastfetch: https://github.com/fastfetch-cli/fastfetch#installation"
    say
fi

# Optional extras. Absent ones only disable the feature that needs them, so
# these are reported rather than treated as failures.
#   type -P, not command -v: command -v also matches shell functions, and a
#   wrapper function named rg is not the ripgrep binary the kitten needs.
optional=()
[[ -n "$(type -P pymol)" ]] || optional+=("pymol — .pdb/.cif files will not open in a viewer")
[[ -n "$(type -P rg)"    ]] || optional+=("ripgrep — the rgh (hyperlinked grep) alias is skipped")
if (( ${#optional[@]} )); then
    say "Optional, not found:"
    printf '  %s\n' "${optional[@]}"
    say
fi

# 2. Config files -----------------------------------------------------------
install_file() {
    local src="$1" dst="$2" mode="${3:-644}"
    if [[ -e "$dst" ]] && ! cmp -s "$src" "$dst"; then
        say "  backing up $dst -> $dst.bak-$STAMP"
        run cp -p "$dst" "$dst.bak-$STAMP"
    fi
    run install -Dm"$mode" "$src" "$dst"
    [[ $DRY_RUN == 1 ]] || say "  installed $dst"
}

say "Installing kitty config..."
for f in kitty.conf ui.conf keys.conf marks.conf diff.conf open-actions.conf; do
    install_file "$REPO/kitty/$f" "$KITTY_DIR/$f"
done
install_file "$REPO/kitty/tab_bar.py" "$KITTY_DIR/tab_bar.py"

say
say "Installing themes..."
for f in "$REPO"/kitty/themes/*.conf; do
    install_file "$f" "$KITTY_DIR/themes/$(basename "$f")"
done

say
say "Installing sessions and kittens..."
for f in "$REPO"/kitty/sessions/*.conf; do
    install_file "$f" "$KITTY_DIR/sessions/$(basename "$f")"
done
install_file "$REPO/kittens/biotools.py" "$KITTY_DIR/kittens/biotools.py" 755

# The window logo is resolved relative to the kitty config directory, so it
# needs its own copy here even though fastfetch also ships one.
install_file "$REPO/fastfetch/dna-helix.png" "$KITTY_DIR/dna-helix.png"

say
say "Installing helper commands into $BIN_DIR..."
for b in biokitty-theme biokitty-seq biokitty-accession; do
    install_file "$REPO/bin/$b" "$BIN_DIR/$b" 755
done

say
say "Installing fastfetch banners..."
# Every config*.jsonc and every logo PNG: the bashrc hook rotates through
# whichever configs are installed, so a new logo needs no installer change.
for f in "$REPO"/fastfetch/*.jsonc "$REPO"/fastfetch/*.png "$REPO/fastfetch/dna.txt"; do
    install_file "$f" "$FF_DIR/$(basename "$f")"
done

# 3. Seed the active theme --------------------------------------------------
say
say "Selecting the default theme..."
if [[ -e "$KITTY_DIR/active-theme.conf" ]]; then
    say "  keeping the theme already selected ($(cat "$KITTY_DIR/active-theme" 2>/dev/null || echo unknown))"
else
    install_file "$REPO/kitty/themes/digital-helix.conf" "$KITTY_DIR/active-theme.conf"
    if [[ $DRY_RUN == 1 ]]; then
        say "  would record digital-helix as the active theme"
    else
        printf 'digital-helix\n' > "$KITTY_DIR/active-theme"
        say "  active theme: digital-helix"
    fi
fi

# 4. Shell hook -------------------------------------------------------------
say
say "Wiring the banner and aliases into ~/.bashrc..."
if grep -qF "$LEGACY_START" "$HOME/.bashrc" 2>/dev/null; then
    say "  found the older hand-installed 'kitty DNA banner' block; replacing it"
    backup_bashrc
    run sed -i "/${LEGACY_START//\//\\/}/,/${LEGACY_END//\//\\/}/d" "$HOME/.bashrc"
fi

if grep -qF "$MARKER_START" "$HOME/.bashrc" 2>/dev/null; then
    say "  already hooked, skipping (remove the block and re-run to refresh it)"
else
    backup_bashrc
    if [[ $DRY_RUN == 1 ]]; then
        say "  would append the biokitty block to ~/.bashrc"
    else
        {
            printf '\n%s\n' "$MARKER_START"
            sed '/^#/d;/^$/d' "$REPO/shell/biokitty.bashrc"
            printf '%s\n' "$MARKER_END"
        } >> "$HOME/.bashrc"
        say "  appended"
    fi
fi

say
say "Done. Open a new kitty window to see it."
say
say "  ctrl+shift+b   sequence ops on the selection"
say "  ctrl+shift+k   kittens"
say "  ctrl+shift+m   sequence marks"
say "  ctrl+shift+a>n next theme        (or: biokitty-theme --list)"
say
say "Font: the config expects 'FantasqueSansM Nerd Font' — install it from"
say "https://www.nerdfonts.com/font-downloads or edit kitty/kitty.conf."
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) say; say "Note: $BIN_DIR is not on your PATH. The keybindings call"
       say "biokitty-seq and biokitty-accession by name — open a new shell so the"
       say "PATH line added to ~/.bashrc takes effect." ;;
esac
