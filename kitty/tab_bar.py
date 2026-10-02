# =====================================================================
#  biokitty — custom tab bar
#  ~/.config/kitty/tab_bar.py
#
#  Enabled by "tab_bar_style custom" in ui.conf. kitty imports this
#  module and calls draw_tab() once per tab, every redraw.
#
#  Each tab is labelled with a nucleotide cycling A-T-G-C by position,
#  so tabs read as a short sequence along the top of the window. The
#  right-hand status shows the active theme and the clock.
#
#  If anything in here raises, kitty falls back to drawing nothing for
#  that tab and logs the traceback to stderr — run `kitty --debug-rendering`
#  or check the kitty log if the bar goes blank. To disable this file
#  entirely, remove "tab_bar_style custom" from ui.conf; the built-in
#  powerline bar takes over and nothing else changes.
# =====================================================================

import datetime
import os

from kitty.fast_data_types import Screen
from kitty.tab_bar import DrawData, ExtraData, TabBarData, as_rgb, draw_title
from kitty.utils import color_as_int

# Nucleotides cycled per tab index, so three tabs read "A T G".
BASES = ('A', 'T', 'G', 'C')

# Slanted powerline separators (Nerd Font / powerline glyph range).
SEP_RIGHT = ''   # right-leaning slant
SEP_SOFT = ''    # thin slant, used between two inactive tabs

ICON_THEME = '⬣'  # ⬣ hexagon, stands in for a benzene/porphyrin ring
ICON_CLOCK = '◴'  # ◴

_theme_cache = {'mtime': -1.0, 'name': 'helix'}


def _active_theme() -> str:
    """Name of the theme biokitty-theme last activated.

    Read from the marker file rather than the environment because the tab
    bar runs inside the long-lived kitty process: an env var captured at
    launch would go stale the moment the theme is switched.
    """
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'active-theme')
    try:
        mtime = os.path.getmtime(path)
        if mtime != _theme_cache['mtime']:
            with open(path, encoding='utf-8') as f:
                _theme_cache['name'] = f.read().strip() or 'helix'
            _theme_cache['mtime'] = mtime
    except OSError:
        pass
    return _theme_cache['name']


def _rgb(color) -> int:
    return as_rgb(color_as_int(color))


def _draw_right_status(draw_data: DrawData, screen: Screen, is_last: bool) -> None:
    if not is_last:
        return

    theme = _active_theme()
    clock = datetime.datetime.now().strftime('%H:%M')

    accent = _rgb(draw_data.active_bg)
    accent_fg = _rgb(draw_data.active_fg)
    dim = _rgb(draw_data.inactive_fg)
    ground = _rgb(draw_data.default_bg)

    cells = (
        (accent, ground, SEP_RIGHT),
        (accent_fg, accent, f' {ICON_THEME} {theme} '),
        (dim, ground, f' {ICON_CLOCK} {clock} '),
    )

    width = sum(len(text) for _, _, text in cells)
    padding = screen.columns - screen.cursor.x - width
    if padding < 1:
        # Window too narrow for the status; leave the tabs alone.
        return

    screen.cursor.fg = dim
    screen.cursor.bg = ground
    screen.draw(' ' * padding)

    for fg, bg, text in cells:
        screen.cursor.fg = fg
        screen.cursor.bg = bg
        screen.draw(text)


def draw_tab(
    draw_data: DrawData,
    screen: Screen,
    tab: TabBarData,
    before: int,
    max_title_length: int,
    index: int,
    is_last: bool,
    extra_data: ExtraData,
) -> int:
    base = BASES[(index - 1) % len(BASES)]

    if tab.is_active:
        bg, fg = _rgb(draw_data.active_bg), _rgb(draw_data.active_fg)
    else:
        bg, fg = _rgb(draw_data.inactive_bg), _rgb(draw_data.inactive_fg)

    screen.cursor.bg = bg
    screen.cursor.fg = fg
    screen.cursor.bold = tab.is_active
    screen.draw(f' {base} {index} ')

    screen.cursor.bold = False
    draw_title(draw_data, screen, tab, index, max_title_length)

    # Activity dot, and a bell marker if the tab wants attention.
    if tab.needs_attention:
        screen.draw(f' {draw_data.bell_on_tab}')
    elif tab.has_activity_since_last_focus:
        screen.draw(f' {draw_data.tab_activity_symbol or "●"}')
    screen.draw(' ')

    # Separator: slant out of this tab into whatever comes next.
    screen.cursor.fg = bg
    screen.cursor.bg = _rgb(draw_data.default_bg) if is_last else _rgb(draw_data.inactive_bg)
    screen.draw(SEP_RIGHT)

    _draw_right_status(draw_data, screen, is_last)
    return screen.cursor.x
