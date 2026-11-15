# AGENTS.md

Guidance for AI coding agents working in this repository.

## Project

**DartAnaliz** is a Streamlit dashboard that analyzes one player's darts matches and practice sessions from DartCounter. The tracked player is set by `PLAYER = "Efe"` in `app.py`. All filtering uses an exact match on `player_name`.

## Running

```bash
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

There is no test suite. To check a change, run the app and open the affected tab. A quick compile check:

```bash
python -m py_compile *.py
```

## Layout

| File | Role |
|---|---|
| `app.py` | Entry point: auth, sidebar actions, data loading, the 8 main tabs |
| `dartcounter_api.py` | DartCounter API client, Turso HTTP client (`turso_query`, `turso_execute`), schema setup, match import. Also a CLI: `python dartcounter_api.py <match URL or ID>` |
| `practice_tab.py` | Practice tab (Score Training, Around the Clock, Singles) and the "FETCH PRACTICE" sidebar button |
| `singles_tab.py` | Singles Training sub-tab, called from `practice_tab.py` |
| `coaching_page.py` | Coaching & Analytics tab |
| `ui_helpers.py` | Mobile CSS, the shared chart palette (`colors()`, `seq_scale()`), `chart()` styling, `score_bands()`, `pct()`, and the `dartboard_ring()` / `segment_bars()` segment charts |
| `doubles_section.py` | Double ring heatmap in the Double Trouble tab (ATC Doubles mode + estimated match checkouts) |
| `around_tab.py`, `score_training_tab.py` | **Unused.** Nothing imports them; their logic was merged into `practice_tab.py`. Edit `practice_tab.py` instead |

## Data

- **Storage:** Turso (libSQL over HTTP) is used when `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` are set. Otherwise the code falls back to local SQLite `dart.db`. Every read path has to handle both backends.
- **Match tables:** `matches`, `legs`, `throws` (schema is in `setup_database`).
- **Practice tables:** `practice_sessions`, `practice_turns`, `around_sessions`, `around_targets`, `singles_sessions`, `singles_targets`. These were created by import scripts that have since been deleted.
- **Turso results:** `turso_query` returns `(columns, rows)`. Always build tables with `pd.DataFrame(rows, columns=cols)`. Passing only `rows` gives integer column names and silently breaks every column check.
- **Timestamps:** practice tables store `started_at` as Unix seconds and are shown in `Europe/Istanbul` time. Match dates are stored as `"%Y-%m-%d %H:%M"` strings.

## Secrets and config

- Secrets are read from `st.secrets` (`.streamlit/secrets.toml`) first, then from `.env`. Keys: `DARTCOUNTER_TOKEN`, `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`, plus `[credentials]` and `[cookie]` for `streamlit-authenticator`.
- **Never read, print, log or commit secret values.** `secrets.toml`, `.streamlit/` and `.env` must stay out of git.
- `.gitignore` has a missing newline (`screenshots/secrets.toml`), so the root `secrets.toml` and `.streamlit/` are **not** ignored right now. Check `git status` before any commit.

## Auth

- `streamlit-authenticator` handles admin login. The app keeps its own `st.session_state["role"]`, which is `visitor` by default or the `role` field from the credentials.
- Sidebar fetch and import actions are shown only to `admin`.
- Logout must also clear the authenticator's state (`authenticator.logout()`); resetting `role` alone isn't enough.
- `requirements.txt` pins `streamlit-authenticator==0.3.3`, but the local venv has 0.4.2. Their APIs differ, so write code that works on the pinned (deployed) version.

## Domain rules

- **Raw average** = total score / total darts × 3.
- **Adjusted average** leaves out double attempts. Once a leg's remaining score first reaches ≤ 40 (or exactly 50), that turn and every later turn in the leg count as double attempts (`mark_double_attempts` in `app.py`).
- **Practice metrics** (std dev, bounce-back, fatigue/decay, consistency) are calculated from `practice_turns`. Group them by session and sort by turn before using `shift()` or turn-index logic.

## Conventions

- UI text is in English and goes through `t()` in `app.py`. Code comments are often in Turkish; that's fine.
- Every Streamlit tab renders on each rerun, so keep data loading cached (`@st.cache_data`) and handle errors per tab. One missing table shouldn't take down the whole app.
- After any import or fetch action, call `st.cache_data.clear()` before `st.rerun()`.
- Don't make up placeholder data in charts. If data is missing, show an `st.info` message.
- **Charts:** build them with `plotly.graph_objects`, render them with `ui_helpers.chart()`, and take colors from `ui_helpers.colors()` roles (`you` = player/adjusted, `alt` = second series, `neutral` = opponents). Don't force `template="plotly_dark"` or hard-code hex. Plot time on a real datetime axis. Never use dual y-axes; use small multiples instead. Use straight lines, not splines (sessions cluster minutes apart). Put metric explanations in `help=`, not in `delta=`.

## Known broken (as of 2026-11-15)

- The sidebar buttons call `list_all_matches.py` and `practice_import.py`, which are deleted. Restore them or move the fetch logic into `dartcounter_api.py`.
- `pd.DataFrame(rows)` without column names in `singles_tab.py` and `coaching_page.py`.
- `save_match` doesn't write atomically, so a failed import leaves a partial match that's never repaired.
