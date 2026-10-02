# biokitty — shell integration.
#
# Sourced from ~/.bashrc by install.sh. Two parts: the random biology banner
# that greets a new kitty window, and a set of aliases for the kitty kittens
# and sequence tools that have no natural keybinding.
#
# install.sh strips whole-line comments when it appends this, so everything
# below has to work without them.

# --------------------------------------------------------------------------
# PATH
#
# biokitty-theme, biokitty-seq and biokitty-accession are installed to
# ~/.local/bin. The kitty keybindings call them by bare name, so they have to
# be reachable — including from the non-login shells kitty spawns.
# --------------------------------------------------------------------------
case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *) PATH="$HOME/.local/bin:$PATH" ;;
esac
export PATH

# --------------------------------------------------------------------------
# BANNER
#
# Three guards matter here:
#
#   $-  == *i*            only interactive shells, so scp/rsync/scripts are
#                         not corrupted by banner output on stdout
#   $KITTY_WINDOW_ID      only kitty, because the image logos use kitty's
#                         graphics protocol. Other terminals would print the
#                         escape sequence as garbage or silently drop it.
#   $KITTY_BANNER_SHOWN   stops the banner repeating when you start a nested
#                         shell inside an existing window. New tabs and windows
#                         are spawned by kitty itself rather than inherited
#                         from the shell, so each still gets its own banner —
#                         and therefore its own random draw.
#
# ROTATION
# Every ~/.config/fastfetch/config*.jsonc is a candidate, except the ASCII
# one (that is the fallback for terminals without kitty graphics). Each is a
# complete fastfetch config, not just an image path, because every logo needs
# its own geometry: the DNA helix is tall and narrow (29x26 cells), the
# protein logos are squatter (about 42x21-24).
#
# To add a logo: run tools/pdb-logo.py or tools/make-logo.py, and save the
# config block it prints as ~/.config/fastfetch/config-<name>.jsonc. It joins
# the rotation on the next window — there is no list to edit. To drop one
# from the rotation, rename it so it no longer ends in .jsonc.
#
# fastfetch is invoked by ABSOLUTE PATH on purpose. Several distributions —
# Bazzite and the wider Universal Blue family among them — ship a `fastfetch`
# shell alias that pins their own config, which would silently override the
# logo. Bypassing the alias is the whole point.
# --------------------------------------------------------------------------
if [[ $- == *i* ]] && [[ -n "$KITTY_WINDOW_ID" ]] && [[ -z "$KITTY_BANNER_SHOWN" ]]; then
    export KITTY_BANNER_SHOWN=1

    _bk_banners=()
    for _bk_cfg in "$HOME/.config/fastfetch"/config*.jsonc; do
        [[ $_bk_cfg == */config-ascii.jsonc ]] && continue
        [[ -r "$_bk_cfg" ]] && _bk_banners+=("$_bk_cfg")
    done

    if (( ${#_bk_banners[@]} )); then
        _bk_pick="${_bk_banners[RANDOM % ${#_bk_banners[@]}]}"

        if [[ -x /usr/bin/fastfetch ]]; then
            /usr/bin/fastfetch --config "$_bk_pick"
        elif command -v fastfetch >/dev/null 2>&1; then
            command fastfetch --config "$_bk_pick"
        fi
    fi

    unset _bk_banners _bk_cfg _bk_pick
fi

# --------------------------------------------------------------------------
# KITTENS
#
# The kittens that are commands rather than interactive pickers. The ones you
# summon with a keystroke live in kitty/keys.conf instead.
#
# Guarded on kitty being present so these do not break a plain-bash session on
# a machine without it.
# --------------------------------------------------------------------------
if command -v kitten >/dev/null 2>&1; then
    alias icat='kitten icat'
    alias kdiff='kitten diff'
    alias kssh='kitten ssh'
    alias kclip='kitten clipboard'
    alias ktransfer='kitten transfer'
    alias kask='kitten ask'
    alias kfonts='kitten choose_fonts'
    alias kthemes='kitten themes'
    alias kpanel='kitten panel'
    alias kquick='kitten quick-access-terminal'
    alias knotify='kitten notify'
    alias kquery='kitten query-terminal'
    alias khints='kitten hints'

    # ripgrep with clickable file:line hyperlinks in the results. The kitten
    # shells out to rg, so only offer the alias when rg is genuinely on PATH.
    # type -P rather than command -v: command -v also matches shell functions,
    # and several tools ship an rg wrapper function that is not the binary.
    if [[ -n "$(type -P rg)" ]]; then
        alias rgh='kitten hyperlinked-grep'
    fi

    # Show an image inline, sized to the window.
    show() { kitten icat --align left "$@"; }
fi

# --------------------------------------------------------------------------
# SEQUENCE TOOLS
#
# Thin wrappers over kittens/biotools.py so the same operations bound to
# ctrl+shift+b are available in a pipeline. All of them read stdin.
#
#   echo ATGGCCTAA | revcomp
#   revcomp < gene.fasta
#   seqstat < reads.fastq
# --------------------------------------------------------------------------
_biokitty_tools="$HOME/.config/kitty/kittens/biotools.py"
if [[ -r "$_biokitty_tools" ]]; then
    revcomp()   { python3 "$HOME/.config/kitty/kittens/biotools.py" revcomp   "$@"; }
    complement(){ python3 "$HOME/.config/kitty/kittens/biotools.py" complement "$@"; }
    translate() { python3 "$HOME/.config/kitty/kittens/biotools.py" translate "$@"; }
    seqstat()   { python3 "$HOME/.config/kitty/kittens/biotools.py" stats     "$@"; }
    seqclean()  { python3 "$HOME/.config/kitty/kittens/biotools.py" clean     "$@"; }
    orf()       { python3 "$HOME/.config/kitty/kittens/biotools.py" orf       "$@"; }
fi
unset _biokitty_tools

# --------------------------------------------------------------------------
# THEME
#
# `bktheme` with no argument lists the palettes and marks the active one.
# --------------------------------------------------------------------------
if command -v biokitty-theme >/dev/null 2>&1; then
    alias bktheme='biokitty-theme'
fi
