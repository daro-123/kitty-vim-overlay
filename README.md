# Kitty Vim scrollback overlay

[Watch the demo (MP4)](demo.mp4)

> **WARNING:** This extension is written with the help of a Coding Agent.

A Kitty custom-kitten overlay for Vim-style navigation, literal search, labeled targeting, and visual selection across Kitty scrollback rows. Scrollback rows retain Kitty's captured ANSI colors and styles; text uses Kitty's configured terminal font.

## Navigation keys

| Key | Action |
| --- | --- |
| `h`, `j`, `k`, `l` | Move left, down, up, right |
| Arrow keys | Move left, down, up, right |
| `w`, `b` | Next / previous word |
| `0`, `$` | First character / last non-whitespace character in the row |
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
| `Enter` | Submit search text; ignored in normal and visual modes |
| `Esc` | Cancel input/visual mode; exit the overlay from normal mode |
| `q` | Exit the overlay from normal or visual mode |

## Key binding configuration

Copy `config/bindings.example.json` to `~/.config/kitty/vim-overlay.json`. The JSON object maps all 23 action names to keys. It replaces the complete default map: include every action. Remove the obsolete `"accept"` entry from existing custom maps. Unknown actions, missing actions, malformed JSON, unsupported key notation, and duplicate key assignments are errors; they do not fall back to a partial map.

A key is either one printable non-space character or a named key in angle brackets: `<Enter>`, `<Esc>`, `<Tab>`, `<Backspace>`, `<Delete>`, `<Up>`, `<Down>`, `<Left>`, `<Right>`, `<Home>`, `<End>`, `<PageUp>`, `<PageDown>`, `<Insert>`, or `<Space>`. Modifier keys use `<C-x>`, `<A-x>`, or `<S-x>` notation (`x` is one letter or digit). Key names are case-sensitive. For example, changing `"move_down": "j"` to `"move_down": "J"` makes `J` the only configured key for that action.

Install the custom kitten by keeping `vim_overlay.py` and the `kitty_vim_overlay/` directory together. For example, from the repository root:

```sh
mkdir -p ~/.config/kitty
cp vim_overlay.py ~/.config/kitty/
cp -r kitty_vim_overlay ~/.config/kitty/
```

Add this entry mapping to `kitty.conf`:

```conf
map alt+escape kitten /home/USER/.config/kitty/vim_overlay.py
```

`mise run test-plugin` launches a separate Kitty terminal with the repository's `config/kitty.conf` loaded and uses `config/` as Kitty's config directory so the relative kitten path resolves to the checkout. `mise run test` covers the pure model and navigation behavior, not Kitty's authentication path; use `test-plugin` as the manual Kitty integration smoke.

## Compatibility

Kitty >= 0.43.1
