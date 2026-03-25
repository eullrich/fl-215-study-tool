import random
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import BASE_DIR
from app.database import get_db
from app.models.content import QuizQuestion
from app.models.scheduling import QuizQuestionState
from app.models.study import StudySession

router = APIRouter(prefix="/api/quiz")
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")

# In-memory quiz state (single user, no need for DB sessions)
_quiz_state: dict = {}


@router.get("/start", response_class=HTMLResponse)
async def start_quiz(request: Request, chapter_id: int, db: AsyncSession = Depends(get_db)):
    """Start a chapter quiz. Returns the first question as HTML."""
    result = await db.execute(
        select(QuizQuestion).where(QuizQuestion.chapter_id == chapter_id).order_by(func.random())
    )
    questions = result.scalars().all()
    if not questions:
        return HTMLResponse("<p class='text-muted'>No questions found.</p>")

    _quiz_state.clear()
    _quiz_state["questions"] = [q.id for q in questions]
    _quiz_state["current"] = 0
    _quiz_state["correct"] = 0
    _quiz_state["total"] = len(questions)
    _quiz_state["chapter_id"] = chapter_id

    return _render_question(questions[0], 0, len(questions))


@router.post("/answer", response_class=HTMLResponse)
async def answer_question(
    request: Request,
    question_id: int,
    selected: int,
    db: AsyncSession = Depends(get_db),
):
    """Submit an answer and get feedback + next question button."""
    q = await db.get(QuizQuestion, question_id)
    if not q:
        return HTMLResponse("<p class='text-muted'>Question not found</p>")

    is_correct = selected == q.correct_index
    if is_correct:
        _quiz_state["correct"] = _quiz_state.get("correct", 0) + 1

    # Update quiz question state
    state_result = await db.execute(
        select(QuizQuestionState).where(QuizQuestionState.question_id == question_id)
    )
    state = state_result.scalar_one_or_none()
    if state:
        state.times_seen += 1
        if is_correct:
            state.times_correct += 1
            state.streak += 1
        else:
            state.streak = 0
        state.mastery_level = state.times_correct / state.times_seen if state.times_seen > 0 else 0
        state.last_seen_at = datetime.utcnow()
        await db.commit()

    current = _quiz_state.get("current", 0)
    total = _quiz_state.get("total", 0)
    correct_count = _quiz_state.get("correct", 0)

    # Build option HTML with feedback
    letters = ['A', 'B', 'C', 'D']
    opts_html = ""
    for i, opt in enumerate(q.options):
        cls = "q-opt disabled"
        if i == q.correct_index:
            cls += " correct"
        elif i == selected and not is_correct:
            cls += " incorrect"
        opts_html += f"""
        <div class="{cls}">
            <span class="q-opt-letter">{letters[i]}</span>
            <span class="q-opt-text">{opt}</span>
        </div>"""

    # Next button or results
    has_next = current + 1 < total
    if has_next:
        next_qid = _quiz_state["questions"][current + 1]
        nav_html = f"""
        <button class="btn btn-primary btn-block mt-4"
                hx-get="/api/quiz/question?idx={current + 1}"
                hx-target="#quiz-area" hx-swap="innerHTML">
            Next Question
        </button>"""
    else:
        score_pct = round(correct_count / total * 100) if total > 0 else 0
        color = "var(--success-light)" if score_pct >= 70 else "var(--danger-light)"
        status = "PASS" if score_pct >= 70 else "NEEDS WORK"
        nav_html = f"""
        <div class="card results-card mt-4">
            <div class="results-score" style="color: {color};">{score_pct}%</div>
            <div class="results-detail">{correct_count} correct out of {total}</div>
            <div class="results-status" style="background: {color}22; color: {color};">{status}</div>
            <p class="text-sm text-dim mt-4">Pass threshold: 70%</p>
            <a href="/quiz/{_quiz_state.get('chapter_id', '')}" class="btn btn-primary btn-block mt-4">Retake Quiz</a>
            <a href="/quiz" class="btn btn-ghost btn-block" style="margin-top: 8px;">Back to Quiz Menu</a>
        </div>"""

    result_icon = "&#10003;" if is_correct else "&#10007;"
    result_color = "var(--success-light)" if is_correct else "var(--danger-light)"

    html = f"""
    <div class="q-card">
        <div class="q-section">{q.section}</div>
        <div style="font-size: 1.2rem; margin-bottom: 12px; color: {result_color};">{result_icon} {'Correct' if is_correct else 'Incorrect'}</div>
        <div class="q-text">{q.question}</div>
        <div class="q-opts">{opts_html}</div>
        <div class="q-explanation">{q.explanation}</div>
    </div>
    {nav_html}
    <script>document.getElementById('score-badge').textContent = '{correct_count} / {current + 1}';</script>
    """
    return HTMLResponse(html)


@router.get("/question", response_class=HTMLResponse)
async def get_question(idx: int, db: AsyncSession = Depends(get_db)):
    """Get a specific question by index in current quiz."""
    _quiz_state["current"] = idx
    qid = _quiz_state["questions"][idx]
    q = await db.get(QuizQuestion, qid)
    total = _quiz_state["total"]
    return _render_question(q, idx, total)


def _render_question(q: QuizQuestion, idx: int, total: int) -> HTMLResponse:
    """Render a quiz question as HTML."""
    letters = ['A', 'B', 'C', 'D']
    opts_html = ""
    for i, opt in enumerate(q.options):
        opts_html += f"""
        <div class="q-opt"
             hx-post="/api/quiz/answer?question_id={q.id}&selected={i}"
             hx-target="#quiz-area" hx-swap="innerHTML">
            <span class="q-opt-letter">{letters[i]}</span>
            <span class="q-opt-text">{opt}</span>
        </div>"""

    return HTMLResponse(f"""
    <div class="q-card">
        <div class="q-section">{q.section}</div>
        <div class="q-num">Question {idx + 1} of {total}</div>
        <div class="q-text">{q.question}</div>
        <div class="q-opts">{opts_html}</div>
    </div>
    """)


@router.get("/exam/start")
async def exam_start(db: AsyncSession = Depends(get_db)):
    """Start an exam simulation. Returns all questions as JSON for Alpine.js."""
    result = await db.execute(select(QuizQuestion).order_by(func.random()).limit(165))
    questions = result.scalars().all()

    return JSONResponse([{
        "id": q.id,
        "section": q.section,
        "question": q.question,
        "options": q.options,
        "correct_index": q.correct_index,
        "explanation": q.explanation,
    } for q in questions])


@router.post("/exam/finish")
async def exam_finish(request: Request, db: AsyncSession = Depends(get_db)):
    """Save exam simulation results."""
    data = await request.json()

    session = StudySession(
        session_type="exam_sim",
        cards_reviewed=data.get("total", 0),
        cards_correct=data.get("correct", 0),
    )
    db.add(session)

    # Update question states
    answers = data.get("answers", {})
    question_ids = data.get("question_ids", [])
    for idx_str, selected in answers.items():
        idx = int(idx_str)
        if idx < len(question_ids):
            qid = question_ids[idx]
            q = await db.get(QuizQuestion, qid)
            if q:
                is_correct = selected == q.correct_index
                state_result = await db.execute(
                    select(QuizQuestionState).where(QuizQuestionState.question_id == qid)
                )
                state = state_result.scalar_one_or_none()
                if state:
                    state.times_seen += 1
                    if is_correct:
                        state.times_correct += 1
                        state.streak += 1
                    else:
                        state.streak = 0
                    state.mastery_level = state.times_correct / state.times_seen
                    state.last_seen_at = datetime.utcnow()

    await db.commit()
    return {"status": "ok"}
