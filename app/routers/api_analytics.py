from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.content import Chapter, Flashcard, QuizQuestion
from app.models.scheduling import CardSchedule, QuizQuestionState
from app.models.study import StudySession

router = APIRouter(prefix="/api/analytics")


@router.get("/overview", response_class=HTMLResponse)
async def overview(db: AsyncSession = Depends(get_db)):
    """Return analytics overview as HTML partial."""
    # Flashcard stats
    total_cards = (await db.execute(select(func.count()).select_from(Flashcard))).scalar() or 0
    mastered = (await db.execute(
        select(func.count()).select_from(CardSchedule).where(CardSchedule.box >= 3)
    )).scalar() or 0
    learning = (await db.execute(
        select(func.count()).select_from(CardSchedule).where(CardSchedule.box.in_([1, 2]))
    )).scalar() or 0
    unseen = (await db.execute(
        select(func.count()).select_from(CardSchedule).where(CardSchedule.box == 0)
    )).scalar() or 0
    due_now = (await db.execute(
        select(func.count()).select_from(CardSchedule)
        .where(CardSchedule.next_review_at <= datetime.utcnow())
    )).scalar() or 0

    # Quiz stats
    total_questions = (await db.execute(select(func.count()).select_from(QuizQuestion))).scalar() or 0
    quiz_seen = (await db.execute(
        select(func.sum(QuizQuestionState.times_seen)).select_from(QuizQuestionState)
    )).scalar() or 0
    quiz_correct = (await db.execute(
        select(func.sum(QuizQuestionState.times_correct)).select_from(QuizQuestionState)
    )).scalar() or 0
    quiz_accuracy = round(quiz_correct / quiz_seen * 100) if quiz_seen > 0 else 0

    # Exam sim history
    exam_result = await db.execute(
        select(StudySession)
        .where(StudySession.session_type == "exam_sim")
        .order_by(StudySession.started_at.desc())
        .limit(5)
    )
    exams = exam_result.scalars().all()

    # Per-chapter breakdown
    chapters_result = await db.execute(select(Chapter).order_by(Chapter.id))
    chapters = chapters_result.scalars().all()

    chapter_rows = ""
    for ch in chapters:
        ch_total = (await db.execute(
            select(func.count()).select_from(Flashcard).where(Flashcard.chapter_id == ch.id)
        )).scalar() or 0
        ch_mastered = (await db.execute(
            select(func.count()).select_from(CardSchedule)
            .join(Flashcard).where(Flashcard.chapter_id == ch.id, CardSchedule.box >= 3)
        )).scalar() or 0
        ch_pct = round(ch_mastered / ch_total * 100) if ch_total > 0 else 0

        ch_quiz = (await db.execute(
            select(func.sum(QuizQuestionState.times_seen), func.sum(QuizQuestionState.times_correct))
            .select_from(QuizQuestionState)
            .join(QuizQuestion).where(QuizQuestion.chapter_id == ch.id)
        )).one()
        ch_q_acc = round((ch_quiz[1] or 0) / ch_quiz[0] * 100) if (ch_quiz[0] or 0) > 0 else 0

        bar_color = "var(--success)" if ch_pct >= 75 else "var(--warning)" if ch_pct >= 40 else "var(--primary)"
        chapter_rows += f"""
        <div class="card" style="padding: 14px 16px;">
            <div class="flex justify-between items-center" style="margin-bottom: 6px;">
                <span class="text-sm" style="font-weight: 600;">Ch {ch.id}</span>
                <span class="text-xs text-dim">{ch_mastered}/{ch_total} mastered · Quiz {ch_q_acc}%</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {ch_pct}%; background: {bar_color};"></div>
            </div>
        </div>"""

    # Exam history rows
    exam_rows = ""
    for ex in exams:
        pct = round(ex.cards_correct / ex.cards_reviewed * 100) if ex.cards_reviewed > 0 else 0
        color = "var(--success-light)" if pct >= 70 else "var(--danger-light)"
        date = ex.started_at.strftime("%b %d, %H:%M") if ex.started_at else "—"
        exam_rows += f"""
        <div class="plan-item" style="cursor: default;">
            <span class="text-sm" style="font-weight: 600; color: {color}; min-width: 50px;">{pct}%</span>
            <span class="text-sm text-muted">{ex.cards_correct}/{ex.cards_reviewed} correct</span>
            <span class="text-xs text-dim" style="margin-left: auto;">{date}</span>
        </div>"""

    if not exam_rows:
        exam_rows = '<p class="text-sm text-dim" style="padding: 12px 0;">No exam simulations yet</p>'

    # Readiness
    mastery_pct = round(mastered / total_cards * 100) if total_cards > 0 else 0

    return HTMLResponse(f"""
    <!-- Flashcard Overview -->
    <div class="card">
        <div class="card-title" style="margin-bottom: 12px;">Flashcard Progress</div>
        <div class="flex justify-between" style="gap: 8px; text-align: center;">
            <div style="flex:1; background: var(--bg); border-radius: var(--radius-sm); padding: 14px 8px;">
                <div style="font-size: 1.5rem; font-weight: 800; color: var(--success-light);">{mastered}</div>
                <div class="text-xs text-dim">Mastered</div>
            </div>
            <div style="flex:1; background: var(--bg); border-radius: var(--radius-sm); padding: 14px 8px;">
                <div style="font-size: 1.5rem; font-weight: 800; color: var(--warning);">{learning}</div>
                <div class="text-xs text-dim">Learning</div>
            </div>
            <div style="flex:1; background: var(--bg); border-radius: var(--radius-sm); padding: 14px 8px;">
                <div style="font-size: 1.5rem; font-weight: 800; color: var(--text-dim);">{unseen}</div>
                <div class="text-xs text-dim">Unseen</div>
            </div>
            <div style="flex:1; background: var(--bg); border-radius: var(--radius-sm); padding: 14px 8px;">
                <div style="font-size: 1.5rem; font-weight: 800; color: var(--primary-light);">{due_now}</div>
                <div class="text-xs text-dim">Due Now</div>
            </div>
        </div>
    </div>

    <!-- Quiz Stats -->
    <div class="card">
        <div class="card-title" style="margin-bottom: 8px;">Quiz Performance</div>
        <div class="flex justify-between items-center">
            <span class="text-sm text-muted">{quiz_seen} questions attempted</span>
            <span style="font-size: 1.2rem; font-weight: 800; color: {'var(--success-light)' if quiz_accuracy >= 70 else 'var(--danger-light)'};">{quiz_accuracy}%</span>
        </div>
    </div>

    <!-- Per-Chapter -->
    <div style="margin-bottom: 12px;">
        <div class="card-title" style="padding: 8px 0;">Chapter Breakdown</div>
        {chapter_rows}
    </div>

    <!-- Exam History -->
    <div class="card">
        <div class="card-title" style="margin-bottom: 8px;">Exam Simulations</div>
        {exam_rows}
    </div>
    """)
