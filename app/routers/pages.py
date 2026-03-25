from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import BASE_DIR
from app.database import get_db
from app.models.content import Chapter, Flashcard, QuizQuestion
from app.models.scheduling import CardSchedule, QuizQuestionState

router = APIRouter()
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")


def _render(name: str, request: Request, **ctx):
    return templates.TemplateResponse(request, name, ctx)


@router.get("/", response_class=RedirectResponse)
async def root():
    return RedirectResponse(url="/dashboard", status_code=302)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    chapters_result = await db.execute(
        select(Chapter).order_by(Chapter.id)
    )
    chapters = chapters_result.scalars().all()

    chapter_stats = []
    total_due = 0
    total_mastered = 0
    total_cards = 0

    for ch in chapters:
        due_count = (await db.execute(
            select(func.count()).select_from(CardSchedule)
            .join(Flashcard).where(
                Flashcard.chapter_id == ch.id,
                CardSchedule.next_review_at <= datetime.utcnow()
            )
        )).scalar() or 0

        ch_total = (await db.execute(
            select(func.count()).select_from(Flashcard).where(Flashcard.chapter_id == ch.id)
        )).scalar() or 0

        ch_mastered = (await db.execute(
            select(func.count()).select_from(CardSchedule)
            .join(Flashcard).where(
                Flashcard.chapter_id == ch.id,
                CardSchedule.box >= 3
            )
        )).scalar() or 0

        quiz_stats = (await db.execute(
            select(
                func.sum(QuizQuestionState.times_seen),
                func.sum(QuizQuestionState.times_correct),
            ).select_from(QuizQuestionState)
            .join(QuizQuestion).where(QuizQuestion.chapter_id == ch.id)
        )).one()
        seen = quiz_stats[0] or 0
        correct = quiz_stats[1] or 0
        quiz_accuracy = round(correct / seen * 100) if seen > 0 else 0

        total_due += due_count
        total_mastered += ch_mastered
        total_cards += ch_total

        chapter_stats.append({
            "id": ch.id,
            "title": ch.title,
            "due": due_count,
            "total": ch_total,
            "mastered": ch_mastered,
            "mastery_pct": round(ch_mastered / ch_total * 100) if ch_total > 0 else 0,
            "quiz_accuracy": quiz_accuracy,
            "quiz_seen": seen,
        })

    mastery_score = total_mastered / total_cards if total_cards > 0 else 0
    readiness = round(mastery_score * 100)

    return _render("pages/dashboard.html", request,
        active_tab="dashboard",
        chapter_stats=chapter_stats,
        total_due=total_due,
        readiness=readiness,
        total_mastered=total_mastered,
        total_cards=total_cards,
    )


@router.get("/study", response_class=HTMLResponse)
async def study_launcher(request: Request, db: AsyncSession = Depends(get_db)):
    chapters_result = await db.execute(select(Chapter).order_by(Chapter.id))
    chapters = chapters_result.scalars().all()

    chapter_info = []
    for ch in chapters:
        due = (await db.execute(
            select(func.count()).select_from(CardSchedule)
            .join(Flashcard).where(
                Flashcard.chapter_id == ch.id,
                CardSchedule.next_review_at <= datetime.utcnow()
            )
        )).scalar() or 0
        total = (await db.execute(
            select(func.count()).select_from(Flashcard).where(Flashcard.chapter_id == ch.id)
        )).scalar() or 0
        chapter_info.append({"id": ch.id, "title": ch.title, "due": due, "total": total})

    total_due = sum(c["due"] for c in chapter_info)

    return _render("pages/study.html", request,
        active_tab="study",
        chapters=chapter_info,
        total_due=total_due,
    )


@router.get("/study/{chapter_id}", response_class=HTMLResponse)
async def study_session(request: Request, chapter_id: int, db: AsyncSession = Depends(get_db)):
    chapter = await db.get(Chapter, chapter_id)
    if not chapter:
        return RedirectResponse(url="/study", status_code=302)

    return _render("pages/study_session.html", request,
        active_tab="study",
        chapter=chapter,
    )


@router.get("/study/due/all", response_class=HTMLResponse)
async def study_due(request: Request):
    return _render("pages/study_session.html", request,
        active_tab="study",
        chapter=None,
    )


@router.get("/quiz", response_class=HTMLResponse)
async def quiz_launcher(request: Request, db: AsyncSession = Depends(get_db)):
    chapters_result = await db.execute(select(Chapter).order_by(Chapter.id))
    chapters = chapters_result.scalars().all()

    chapter_info = []
    for ch in chapters:
        total = (await db.execute(
            select(func.count()).select_from(QuizQuestion).where(QuizQuestion.chapter_id == ch.id)
        )).scalar() or 0
        chapter_info.append({"id": ch.id, "title": ch.title, "total": total})

    return _render("pages/quiz.html", request,
        active_tab="quiz",
        chapters=chapter_info,
    )


@router.get("/quiz/{chapter_id}", response_class=HTMLResponse)
async def quiz_session(request: Request, chapter_id: int, db: AsyncSession = Depends(get_db)):
    chapter = await db.get(Chapter, chapter_id)
    if not chapter:
        return RedirectResponse(url="/quiz", status_code=302)

    return _render("pages/quiz_session.html", request,
        active_tab="quiz",
        chapter=chapter,
    )


@router.get("/exam", response_class=HTMLResponse)
async def exam(request: Request):
    return _render("pages/exam.html", request, active_tab="quiz")


@router.get("/analytics", response_class=HTMLResponse)
async def analytics(request: Request):
    return _render("pages/analytics.html", request, active_tab="stats")
