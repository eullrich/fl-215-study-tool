# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Mobile-first study tool for the Florida 2-15 (Health & Life) insurance licensing exam. FastAPI backend with Jinja2/HTMX/Alpine.js frontend. 213 flashcards + 229 quiz questions across 5 chapters, with Leitner box + SM-2 spaced repetition tuned for 2-week cramming.

## Commands

```bash
# Run locally (auto-seeds DB if empty)
uvicorn app.main:app --reload

# Reset database from scratch
python -m data.seed_content
```

## Architecture

**Server-driven UI**: Page routes (`app/routers/pages.py`) render full Jinja2 templates. Interactive endpoints (`app/routers/api_study.py`, `api_quiz.py`) return **HTML partials** for HTMX swap — not JSON. Alpine.js handles client-side state (card flip, exam timer).

**Template rendering**: Uses `templates.TemplateResponse(request, name, context)` (new Starlette API). The `_render()` helper in `pages.py` wraps this.

**Spaced repetition** lives in `api_study.py` (`BOX_CARD_INTERVALS` dict + `/rate` endpoint). Uses occurrence-based spacing (intervening cards, not clock time). Leitner boxes 0-4 with card intervals (3→7→18→45 cards). SM-2 ease factor personalizes spacing per card. Global position counter in `StudyCounter` table tracks review progress.

**Quiz state**: In-memory `_quiz_state` dict in `api_quiz.py` — single-user, no persistence between server restarts. Exam simulation (`/exam`) uses Alpine.js client-side with JSON API.

**Auto-seed on startup**: `database.py:init_db()` checks if chapters table is empty, imports `data.seed_content.seed()` if so. The seed script parses JS arrays from `legacy/ch*.html` files via regex.

**Config**: `DATA_DIR` env var controls where SQLite lives. Defaults to `./data/`. On Render, set to persistent disk mount path.

## Key Patterns

- All database access is async (`AsyncSession`, `await db.execute(...)`)
- HTMX attributes on HTML elements drive interactions: `hx-post`, `hx-target="#study-area"`, `hx-swap="innerHTML"`
- CSS uses custom properties defined in `:root` of `app/static/css/style.css` (dark theme: `--bg`, `--surface`, `--primary`, etc.)
- Bottom nav active state set via `active_tab` template variable

## Deployment

Render.com via `render.yaml`. Persistent disk (1GB) at `/opt/render/project/src/db_data` for SQLite. `DATA_DIR` env var points there. Auto-deploys from GitHub push.
