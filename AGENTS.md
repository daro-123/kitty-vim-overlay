# Repository Guidelines

## Project Overview

A Python Kitty custom-kitten that navigates retained terminal scrollback with Vim-style movement, literal search, and labeled character/line targets. Navigation stays local to the overlay; accepting moves Kitty’s viewport to the selected history row. ANSI styling is retained for display.

## Architecture & Data Flow

`scrollback_navigator.py` delegates to `kitty_scrollback_navigator.kitten.main`, which prevents duplicate sessions with a per-Kitty-instance lock. The Kitty-facing layer captures the source window’s plain and ANSI scrollback, normalizes displayed rows, aligns the current screen with history, and constructs a local model/session and overlay UI. Movement, search, and target selection update local model state only. Accept converts the row delta into a Kitty scroll command; cancel leaves the source viewport unchanged.

Keep responsibilities separated:

- `model.py`: local row/column movement and clamping.
- `search.py`: literal directional search/repeat and visible-row jump targets.
- `snapshot.py`: displayed-row normalization, ANSI-preserving rendering helpers, and viewport alignment.
- `session.py`: terminal side-effect boundary (`ScrollbackAdapter` protocol) and accept/cancel behavior.
- `kitten.py`: Kitty remote-control adapter, UI event handling, orchestration, and rendering.
- `bindings.py` / `instance.py`: binding validation and per-Kitty-instance locking.

Plain rows drive search/model coordinates; corresponding ANSI rows drive rendering. Keep Kitty I/O out of the pure navigation model and preserve visible-character coordinates when transforming ANSI text.

## Key Directories

- `kitty_scrollback_navigator/`: runtime package; keep it alongside the root kitten entrypoint when installing.
- `tests/`: standard-library unit tests and fake-adapter behavior.
- `config/`: Kitty smoke-test configuration and the complete example key-binding map.

## Development Commands

- `mise run test` — run the standard-library suite (`python3 -m unittest discover -s tests -v`).
- `mise run test-plugin` — launch Kitty with `config/kitty.conf` for manual overlay/integration smoke testing; requires Kitty and a graphical session.

No build, lint, or formatter task is configured. Kitty’s integration path is not covered by the automated unit suite; use the plugin smoke task for Kitty-specific behavior.

## Code Conventions & Common Patterns

- Use conventional Python naming (`PascalCase` classes, `snake_case` functions/attributes), type annotations, and small concrete modules.
- Keep snapshot/history data immutable where practical (tuples); keep interactive cursor and UI state explicit and local.
- Isolate external effects behind the adapter protocol. Unit-test model/session behavior with in-memory inputs and a fake adapter rather than requiring Kitty.
- Raise specific `ValueError`/`BindingError` for invalid inputs or configuration. Use boolean results and explicit UI state/status values for expected outcomes such as no match, pending labels, or cancellation.
- Follow Kitty’s event-loop/callback model in the overlay; the project has no `async`/`await` convention or async framework.
- Binding JSON is a complete replacement map, not a partial override: preserve all action names and unique valid key assignments. See `README.md` and `config/bindings.example.json`.

## Important Files

- `scrollback_navigator.py` — installable Kitty custom-kitten entrypoint facade.
- `kitty_scrollback_navigator/kitten.py` — Kitty integration and overlay lifecycle.
- `kitty_scrollback_navigator/model.py`, `search.py`, `snapshot.py`, `session.py` — navigation and scrollback behavior.
- `kitty_scrollback_navigator/bindings.py`, `instance.py` — configuration and single-instance behavior.
- `mise.toml` — project task definitions.
- `config/kitty.conf` — isolated test mapping (`Alt+Esc`) and scrollback limit.
- `README.md` — setup, bindings, runtime caveats, and smoke-test workflow.

## Runtime/Tooling Preferences

Use Python 3 (`python3`) and Mise for the configured tasks. Tests use only `unittest`; no Python dependency/package manifest or lockfile is present. Kitty is needed to run the overlay; the documented compatibility smoke was on Kitty 0.43.1/Linux, and other versions/platforms are unverified. Alternate-screen applications do not expose primary scrollback to the navigator. Keep the launcher script and package directory together when installing (`README.md`).

## Testing & QA

Tests are grouped by behavior in `tests/test_*.py` and use `unittest.TestCase`, local model builders, in-memory inputs, and small fakes. Run the full suite with `mise run test`; run a focused module with, for example, `python3 -m unittest tests.test_search -v`. Cover visible behavior, boundaries, and state transitions; for Kitty-specific changes, also launch `mise run test-plugin` and exercise the overlay. No coverage threshold or static-analysis command is configured.
