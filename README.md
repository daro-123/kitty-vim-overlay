# Kitty scrollback navigator

A pure Python model for Vim-style navigation, literal search, labeled targeting, and key-binding validation over Kitty scrollback rows, plus a Kitty custom-kitten overlay. Scrollback rows retain Kitty's captured ANSI colors and styles; text uses Kitty's configured terminal font. Only one navigator runs per Kitty instance; repeated entry is ignored until the active session closes.

## Navigation keys

The cursor starts on the last non-empty row in the current Kitty viewport, rather than at the screen's bottom when that area is blank. Movement is over displayed rows; blank rows between content remain navigable, but the cursor cannot move past the last non-empty history row into trailing blank viewport padding. Horizontal movement stays within the current row; vertical and page movement clamp at the history edges. `w` and `b` cross displayed-row boundaries and skip whitespace-separated words.

Search, labeled-target, page, and `gg`/`GG` jumps, plus cursor moves that scroll the viewport, briefly flash a fading trail behind the destination cursor.

| Key | Action |
| --- | --- |
| `h`, `j`, `k`, `l` | Move left, down, up, right |
| Arrow keys | Move left, down, up, right |
| `w`, `b` | Next / previous word |
| `0`, `$` | First / last character in the row |
| `gg`, `GG` | Jump to the first / last displayed scrollback row |
| `Ctrl+f`, `PageDown` | One visible page down |
| `Ctrl+b`, `PageUp` | One visible page up |
| `Ctrl+d`, `Ctrl+u` | Half a visible page down / up |
| `/`, `?` | Search forward / backward |
| `n`, `N` | Move to next match forward / backward |
| `s`, `S` | Start character / line targeting |
| `v` | Start characterwise visual selection |
| `V` | Start linewise visual selection |
| `Ctrl+v` | Start blockwise visual selection |
| `y` | Copy the visual selection to Kitty's clipboard |
| `Enter` | Accept the located position |
| `Esc` | Cancel input/visual mode; exit the navigator from normal mode |
| `q` | Exit the navigator from normal or visual mode |

Page size is the smaller of the visible navigation height and the number of captured rows; half-page movement uses at least one row. Search is literal; both `/` and `?` ignore case. Every matching occurrence in retained displayed rows has a blue background; the current match has a distinct gold background. Initial search selects the nearest following or preceding occurrence and wraps when needed. `n` always moves forward; `N` always moves backward, regardless of whether the search began with `/` or `?`. If no match exists, the position does not change. Press `s` to dim the current display, then type a character: matching characters are found without regard to case and shown with their jump labels overlaid immediately to the right of each target character, leaving the target visible. Labels move farther right only to avoid covering another target character or label; text beneath a label is temporarily obscured rather than shifted. Type a displayed label in either case to jump immediately. `S` labels rows in the current display at the row start, without the one-character offset used for character targets, and accepts labels in either case. `v` selects characters inclusively from the current character; `V` selects complete displayed rows; `Ctrl+v` selects an inclusive rectangular block, padding short rows when copied. Move with `h/j/k/l`, arrow keys, `w`, or `b`. `y` copies the selected text to Kitty's clipboard; displayed rows are joined with newlines. Press the active visual-mode key again to cancel selection, or `Esc` to cancel it. `Enter` applies the selected location to Kitty's viewport.

## Key binding configuration

Copy `config/bindings.example.json` to `~/.config/kitty/scrollback-navigator.json`. The JSON object maps all 24 action names to keys. It replaces the complete default map: include every action. Unknown actions, missing actions, malformed JSON, unsupported key notation, and duplicate key assignments are errors; they do not fall back to a partial map.

A key is either one printable non-space character or a named key in angle brackets: `<Enter>`, `<Esc>`, `<Tab>`, `<Backspace>`, `<Delete>`, `<Up>`, `<Down>`, `<Left>`, `<Right>`, `<Home>`, `<End>`, `<PageUp>`, `<PageDown>`, `<Insert>`, or `<Space>`. Modifier keys use `<C-x>`, `<A-x>`, or `<S-x>` notation (`x` is one letter or digit). Key names are case-sensitive. For example, changing `"move_down": "j"` to `"move_down": "J"` makes `J` the only configured key for that action.

Install the custom kitten by keeping `scrollback_navigator.py` and the `kitty_scrollback_navigator/` directory together. For example, from the repository root:

```sh
mkdir -p ~/.config/kitty
cp scrollback_navigator.py ~/.config/kitty/
cp -r kitty_scrollback_navigator ~/.config/kitty/
```

Add this entry mapping to `kitty.conf`:

```conf
map alt+escape kitten /home/USER/.config/kitty/scrollback_navigator.py
```

Replace `/home/USER` with the absolute home-directory path. To remap entry, replace that line with the desired Kitty key mapping; the JSON configuration only controls keys after the overlay opens. Kitty grants full remote-control capability to this kitten process through an isolated per-invocation channel; global `allow_remote_control` is not required. The implementation uses only fixed `ls`, `get-text`, and `scroll-window` remote-control commands; `y` writes copied text through Kitty's OSC 52 clipboard protocol, which requires `clipboard_control` to permit clipboard writes. The tested `launch --type=overlay kitten ...` child-process form did not provide the required `kitten_ui` remote-control context. Kitty's key-map syntax is documented in the [Kitty configuration reference](https://sw.kovidgoyal.net/kitty/conf/#keyboard-shortcuts).

`mise run test-plugin` launches a separate Kitty terminal with the repository's `config/kitty.conf` loaded and uses `config/` as Kitty's config directory so the relative kitten path resolves to the checkout. In that window, Alt+Esc opens the navigator; the test config sets a 10,000-line scrollback limit without modifying the user's Kitty config. `mise run test` covers the pure model and fake-adapter behavior, not Kitty's authentication path; use `test-plugin` as the manual Kitty integration smoke.

## Kitty compatibility status

Kitty 0.43.1 on Linux was smoke-tested in an isolated instance with a loopback-only listener. The custom kitten fetched retained history with display-wrap markers, moved locally, searched for a literal row, and on Enter moved the source viewport so the selected row was at its bottom; Esc closed the overlay without changing the source viewport. A separate wrapped 430-cell line test selected its middle display row and restored byte-identical screen text after reversing the offset.

In alternate-screen mode (DECSET 1049), Kitty returned only the alternate buffer; the overlay reports that primary scrollback is unavailable and does not apply a selection. Kitty only returns retained scrollback, so text discarded by the configured history limit is not recoverable. Earlier protocol probes used global remote control; the repository test config leaves it disabled and relies on the custom-kitten channel. Kitty 0.43.1 is verified on Linux; other versions and platforms are untested.

