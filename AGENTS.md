# AGENTS.md

Guidance for AI coding agents working in this repository.

## Project

**DartAnaliz** is a Streamlit dashboard that analyzes one player's darts matches and practice sessions from DartCounter. One deployment shows one player: whoever connected their DartCounter account (`PLAYER_ID` / `PLAYER` in `app.py`, read from `app_settings`; `DEFAULT_PLAYER = "Efe"` until someone connects). Filter by DartCounter user id when known, falling back to `player_name` (`dartcounter_api.only_player`).

## Running

```bash
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Tests cover the calculations (adjusted average, double zone, darts stats, doubles ranking, period filter, Turso batches). They use only the standard library:

```bash
python -m unittest discover -s tests -t .
```

For UI changes, also run the app and open the affected tab at 375 px (phone), 820 px (tablet), and desktop. Text cut off with "…" and side-by-side cards or charts that are too narrow show up mostly at the in-between width. A quick compile check:

```bash
python -m py_compile *.py
```

## Layout

| File | Role |
|---|---|
| `app.py` | Entry point: data loading, the header (with the "Synced …" badge and Sync button, `run_sync`), period picker, the 5 main tabs (Home, Matches, Doubles, Practice, Coaching). There is no sidebar |
| `match_stats.py` | Pure match calculations, no Streamlit: `mark_double_attempts`, `adjusted_stats`, `per_match_stats`, `darts_stats` (first 9, checkout %, highest checkout, best 501 leg, 180/140+/100+). Tested in `tests/` |
| `playing_time.py` | Time played: `sessions()` (every match and practice session with its real length), `weekly()` (minutes per Monday–Sunday week and activity), and the weekly stacked bar chart on Home |
| `home_tab.py` | Home tab: this week vs last week, best/weakest double, one trend, recent activity, last sync |
| `dartcounter_api.py` | DartCounter API client, Turso HTTP client (`turso_query`, `turso_execute`), schema setup, match import. Also a CLI: `python dartcounter_api.py <match URL or ID>` |
| `sync.py` | Imports the connected player's whole DartCounter history (matches, Score Training, Around the Clock, Singles, Doubles Training), skipping what's stored. `detect_player(token)` finds the token owner. CLI: `python sync.py` (this year and last) or `python sync.py --all`; saves the sync time and exits non-zero on errors |
| `practice_tab.py` | Practice tab (Score Training, Around the Clock, Singles, Doubles Training), `session_table()` and the cached `load_all_practice_data()` |
| `doubles_training_tab.py` | Doubles Training sub-tab, called from `practice_tab.py` |
| `singles_tab.py` | Singles Training sub-tab, called from `practice_tab.py` |
| `coaching.py` | Coaching calculations, no Streamlit: levels and targets, the 8 skills (`assess`), `priorities`, `weekly_plan`, `then_vs_now`, `daily`. Spec: `docs/coaching.md`. Tested in `tests/test_coaching.py` |
| `coaching_page.py` | Coaching tab: loads the period's data into `coaching.Data` and draws level, skill profile, priorities, weekly plan and progress |
| `ui_helpers.py` | Theme CSS (`inject_theme_css()`, `page_header()`, `tokens()`), the shared chart palette (`colors()`, `seq_scale()`), `chart()` styling, `daily_trend()`, `score_bands()`, `pct()`, and the `dartboard_ring()` / `segment_bars()` segment charts |
| `doubles_section.py` | Double ring heatmap in the Double Trouble tab (Doubles Training + ATC Doubles mode + estimated match checkouts) |

## Data

- **Storage:** Turso (libSQL over HTTP) is used when `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` are set. Otherwise the code falls back to local SQLite `dart.db`. Every read path has to handle both backends.
- **Match tables:** `matches`, `legs`, `throws` (schema is in `setup_database`). `matches.duration_sec` (start to finish, from the API's `started_at` / `finished_at`) was added later. `setup_database()` adds the column to older databases, and each sync fills it for matches that don't have it (`sync.backfill_match_durations`).
- **Practice tables:** `practice_sessions`, `practice_turns`, `around_sessions`, `around_targets`, `singles_sessions`, `singles_targets`, `doubles_sessions`, `doubles_targets`. Created and filled by `sync.py`. Versus sessions also store opponents and CPUs, so always filter to the connected player.
- **Turso results:** `turso_query` returns `(columns, rows)`. Always build tables with `pd.DataFrame(rows, columns=cols)`. Passing only `rows` gives integer column names and silently breaks every column check.
- **Timestamps:** practice tables store `started_at` as Unix seconds and are shown in `Europe/Istanbul` time. Match dates are stored as `"%Y-%m-%d %H:%M"` strings.

## Secrets and config

- Secrets are read from `st.secrets` (`.streamlit/secrets.toml`) first, then from `.env`. Keys: `DARTCOUNTER_TOKEN`, `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`, and optionally `TOKEN_ENCRYPTION_KEY` (Fernet key, only to read a token stored encrypted in `app_settings` by the former Connect panel). `load_token()` tries a stored token first, then `st.secrets`, then `.env`. `[credentials]` and `[cookie]` in older secrets files are no longer used.
- **Never read, print, log or commit secret values.** `secrets.toml` (including `.streamlit/secrets.toml`) and `.env` must stay out of git. `.streamlit/config.toml` holds the theme, has no secrets and is committed.
- `.gitignore` ignores `secrets.toml` and `.streamlit/secrets.toml`. Still check `git status` before any commit.

## Updating the data

- There is no login. The only control that changes data is the **Sync** button next to the "Synced …" badge in the header. It's public, so `run_sync` in `app.py` allows one sync per 2 minutes (`SYNC_COOLDOWN`, start time stored as `app_settings.sync_started`); a second press within that time just shows a toast. After a sync it clears the caches and reruns, so new games and the new sync time show right away.
- `python sync.py` does the same from a terminal (it writes to the same Turso database the live site reads). The site then shows new matches within 5 minutes (`load_data` cache) and the new sync time within a minute.
- A DartCounter token can expire. If sync says "Token rejected", copy a fresh token into `DARTCOUNTER_TOKEN`.

## Domain rules

- **Raw average** = total score / total darts × 3.
- **Adjusted average** leaves out double attempts. Once a leg's remaining score first reaches ≤ 40 (or exactly 50), that turn and every later turn in the leg count as double attempts (`mark_double_attempts` in `match_stats.py`).
- **Time played** is the plain sum of every game's real length (`duration_sec`): matches, including unfinished ones, plus all four practice modes. Long games aren't capped or adjusted. Weeks run Monday–Sunday in Istanbul time.
- **Practice metrics** (std dev, bounce-back, fatigue/decay, consistency) are calculated from `practice_turns`. Group them by session and sort by turn before using `shift()` or turn-index logic.

## Conventions

- UI text is in English and goes through `t()` in `app.py` (currently a pass-through; there is no language toggle). Code comments are often in Turkish; that's fine.
- Every Streamlit tab renders on each rerun, so keep data loading cached (`@st.cache_data`) and handle errors per tab. One missing table shouldn't take down the whole app.
- **Period filter:** the picker at the top sets `st.session_state['period']`. Every tab except Home's "This week" row filters with `ui_helpers.in_period()` (practice tables by `started_at`, matches by `date_col='date'`). Show an `st.info` naming the period when it leaves nothing.
- Tables: show dates with `ui_helpers.date_column()` (readable but sortable), plain column names, newest first. Use `width="stretch"`, not the deprecated `use_container_width`.
- Don't make up placeholder data in charts. If data is missing, show an `st.info` message.
- **Charts:** build them with `plotly.graph_objects`, render them with `ui_helpers.chart()`, and take colors from `ui_helpers.colors()` roles (`you` = player/adjusted, `alt` = second series, `neutral` = opponents). Don't force `template="plotly_dark"` or hard-code hex. Plot time on a real datetime axis. Never use dual y-axes; use small multiples instead. Use straight lines, not splines (sessions cluster minutes apart). For trends over time use `ui_helpers.daily_trend()` (one point per day, min–max bar, overall-mean line, latest value labelled) instead of per-session dots with a rolling line, which stack up on busy days. Put metric explanations in `help=`, not in `delta=`.
- **Theme:** base colours and fonts (Inter, Inter Tight) are in `.streamlit/config.toml`, with separate `[theme.light]` and `[theme.dark]` sections; the app follows the viewer's system setting. `ui_helpers.inject_theme_css()` adds the rest: metric/chart cards, underline main tabs, pill sub-tabs, the page header and phone rules. Its surface colours come from `_TOKENS`, so keep them in step with `config.toml`. Target Streamlit's `data-testid` and ARIA `role` attributes in CSS, not `data-baseweb` or `st-emotion-cache` classes, which change between versions. Don't put an element type in front of a `data-testid` selector (`[data-testid="stMetricLabel"]`, not `div[...]`): Streamlit changes element types too. Rows of metric cards, bordered cards and charts wrap by their own minimum width (150 / 220 / 320 px), so they reflow at any screen width, not just on phones. Labels use Material icons (`:material/name:`), not emojis. Streamlit doesn't rerun when the viewer switches light/dark, so `ui_helpers.watch_theme()` (the invisible `theme_watch/` component, called from `inject_theme_css()`) reports the new theme and triggers a rerun; without it, theme-dependent CSS and chart colours would stay on the old theme until the next click.

## Known limits (as of 2026-11-15)

- Writes go through `turso_batch()`: one all-or-nothing HTTP request per match or practice session. Don't write rows one by one with `turso_execute` in loops.
- Sync still does one existence check (one request) per game it looks at, so walking a long history takes a while even when nothing is new.
- `load_data()` in `app.py` always tries Turso first and falls back to `dart.db` on any error.
