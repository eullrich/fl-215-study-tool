from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.config import BASE_DIR
from app.database import get_db
from app.models.content import Flashcard
from app.models.scheduling import CardSchedule, StudyCounter

router = APIRouter(prefix="/api/study")
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")

# Leitner box intervals (intervening cards) — occurrence-based spacing
BOX_CARD_INTERVALS = {
    0: 0,      # Unseen: immediate
    1: 3,      # Learning: ~3 cards later
    2: 7,      # Reviewing: ~7 cards later
    3: 18,     # Familiar: ~18 cards later
    4: 45,     # Mastered: ~45 cards later
}


async def get_position(db: AsyncSession) -> int:
    """Get the current global review position."""
    result = await db.execute(select(StudyCounter).where(StudyCounter.id == 1))
    counter = result.scalar_one_or_none()
    if not counter:
        counter = StudyCounter(id=1, position=0)
        db.add(counter)
        await db.flush()
    return counter.position


async def increment_position(db: AsyncSession) -> int:
    """Increment and return the global review position."""
    result = await db.execute(select(StudyCounter).where(StudyCounter.id == 1))
    counter = result.scalar_one_or_none()
    if not counter:
        counter = StudyCounter(id=1, position=0)
        db.add(counter)
    counter.position += 1
    await db.flush()
    return counter.position


def compute_interval(box: int, ease_factor: float) -> int:
    """Compute the card interval for a given box and ease factor."""
    base = BOX_CARD_INTERVALS[box]
    return max(1, round(base * ease_factor / 2.5))


@router.get("/next-card", response_class=HTMLResponse)
async def next_card(request: Request, chapter_id: int | None = None, db: AsyncSession = Depends(get_db)):
    """Get the next due flashcard. Returns an HTML partial."""
    current_pos = await get_position(db)

    # Find due cards (reviewed at least once, position reached)
    query = (
        select(CardSchedule)
        .options(joinedload(CardSchedule.flashcard))
        .where(
            CardSchedule.review_after_position <= current_pos,
            CardSchedule.total_reviews > 0,
        )
        .order_by(CardSchedule.review_after_position)
    )
    if chapter_id:
        query = query.join(Flashcard).where(Flashcard.chapter_id == chapter_id)

    result = await db.execute(query)
    schedule = result.scalars().first()

    if not schedule:
        # No due cards — check if there are unseen cards
        unseen_query = (
            select(CardSchedule)
            .options(joinedload(CardSchedule.flashcard))
            .where(CardSchedule.box == 0, CardSchedule.total_reviews == 0)
            .order_by(CardSchedule.flashcard_id)
            .limit(1)
        )
        if chapter_id:
            unseen_query = unseen_query.join(Flashcard).where(Flashcard.chapter_id == chapter_id)
        result = await db.execute(unseen_query)
        schedule = result.scalars().first()

    if not schedule:
        # Count total cards for this chapter
        total_query = select(CardSchedule).options(joinedload(CardSchedule.flashcard))
        if chapter_id:
            total_query = total_query.join(Flashcard).where(Flashcard.chapter_id == chapter_id)
        total_result = await db.execute(total_query)
        total = len(total_result.scalars().all())

        return HTMLResponse(f"""
        <div class="card text-center" style="padding: 40px 20px;">
            <div style="font-size: 2rem; margin-bottom: 12px;">&#10003;</div>
            <div class="card-title">All Caught Up!</div>
            <p class="text-sm text-muted mt-4">No cards due right now. Keep studying to unlock more reviews.</p>
            <p class="text-xs text-dim mt-4">{total} cards total in this deck</p>
            <a href="/study" class="btn btn-ghost mt-6">Back to Study</a>
        </div>
        """)

    card = schedule.flashcard

    # Count due + unseen for progress
    due_query = select(CardSchedule).where(
        CardSchedule.review_after_position <= current_pos,
        CardSchedule.total_reviews > 0,
    )
    if chapter_id:
        due_query = due_query.join(Flashcard).where(Flashcard.chapter_id == chapter_id)
    due_result = await db.execute(due_query)
    due_count = len(due_result.scalars().all())

    # Compute prospective intervals for button labels
    def label_for(conf: int) -> str:
        box = schedule.box
        ease = schedule.ease_factor
        if conf == 0:
            return f"~{compute_interval(1, max(1.3, ease - 0.3))}"
        elif conf == 1:
            return f"~{max(3, round(schedule.interval_cards * 0.8))}"
        elif conf == 2:
            new_box = min(4, box + 1)
            return f"~{compute_interval(new_box, ease)}"
        else:
            new_box = min(4, box + 2)
            return f"~{max(1, round(BOX_CARD_INTERVALS[new_box] * (ease + 0.15) / 2.5 * 1.3))}"

    return HTMLResponse(f"""
    <div class="fc-container" x-data="{{ flipped: false }}">
        <div class="fc-card-wrap" @click="flipped = !flipped">
            <div class="fc-card" :class="{{ 'flipped': flipped }}">
                <div class="fc-face fc-front">
                    <div class="fc-label">Question</div>
                    {"<div class='fc-section'>" + card.section + "</div>" if card.section else ""}
                    <div class="fc-text">{card.question}</div>
                    <div class="fc-hint">Tap to flip</div>
                </div>
                <div class="fc-face fc-back">
                    <div class="fc-label">Answer</div>
                    <div class="fc-text" style="font-size: 0.95rem; font-weight: 500;">{card.answer}</div>
                </div>
            </div>
        </div>

        <div x-show="flipped" x-transition class="confidence-row">
            <button class="conf-btn conf-btn--again"
                    hx-post="/api/study/rate?card_id={schedule.id}&confidence=0&chapter_id={chapter_id or ''}"
                    hx-target="#study-area" hx-swap="innerHTML">
                Again
                <span class="conf-label">{label_for(0)} cards</span>
            </button>
            <button class="conf-btn conf-btn--hard"
                    hx-post="/api/study/rate?card_id={schedule.id}&confidence=1&chapter_id={chapter_id or ''}"
                    hx-target="#study-area" hx-swap="innerHTML">
                Hard
                <span class="conf-label">{label_for(1)} cards</span>
            </button>
            <button class="conf-btn conf-btn--good"
                    hx-post="/api/study/rate?card_id={schedule.id}&confidence=2&chapter_id={chapter_id or ''}"
                    hx-target="#study-area" hx-swap="innerHTML">
                Good
                <span class="conf-label">{label_for(2)} cards</span>
            </button>
            <button class="conf-btn conf-btn--easy"
                    hx-post="/api/study/rate?card_id={schedule.id}&confidence=3&chapter_id={chapter_id or ''}"
                    hx-target="#study-area" hx-swap="innerHTML">
                Easy
                <span class="conf-label">{label_for(3)} cards</span>
            </button>
        </div>
        <p class="text-xs text-dim">{due_count} cards remaining</p>
    </div>
    <script>document.getElementById('fc-progress').textContent = 'Box {schedule.box} · {due_count} due';</script>
    """)


@router.post("/rate", response_class=HTMLResponse)
async def rate_card(
    request: Request,
    card_id: int,
    confidence: int,
    chapter_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Rate a flashcard (0=again, 1=hard, 2=good, 3=easy) and schedule next review."""
    schedule = await db.get(CardSchedule, card_id)
    if not schedule:
        return HTMLResponse("<p class='text-muted'>Card not found</p>", status_code=404)

    new_position = await increment_position(db)

    # Apply Leitner + SM-2 hybrid (occurrence-based)
    if confidence == 0:  # Again
        schedule.box = 1
        schedule.ease_factor = max(1.3, schedule.ease_factor - 0.3)
        schedule.interval_cards = compute_interval(1, schedule.ease_factor)
        schedule.consecutive_correct = 0
    elif confidence == 1:  # Hard
        schedule.ease_factor = max(1.3, schedule.ease_factor - 0.15)
        schedule.interval_cards = max(3, round(schedule.interval_cards * 0.8))
    elif confidence == 2:  # Good
        new_box = min(4, schedule.box + 1)
        schedule.box = new_box
        schedule.interval_cards = compute_interval(new_box, schedule.ease_factor)
        schedule.consecutive_correct += 1
    elif confidence == 3:  # Easy
        new_box = min(4, schedule.box + 2)
        schedule.box = new_box
        schedule.ease_factor += 0.15
        schedule.interval_cards = max(1, round(BOX_CARD_INTERVALS[new_box] * schedule.ease_factor / 2.5 * 1.3))
        schedule.consecutive_correct += 1

    schedule.review_after_position = new_position + schedule.interval_cards
    schedule.last_reviewed_at_position = new_position
    schedule.last_confidence = confidence
    schedule.total_reviews += 1
    if confidence >= 2:
        schedule.total_correct += 1

    await db.commit()

    return await next_card(request, chapter_id=chapter_id, db=db)
