from datetime import datetime

from sqlalchemy import Integer, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class StudyCounter(Base):
    """Single-row table tracking the global review position."""
    __tablename__ = "study_counters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    position: Mapped[int] = mapped_column(Integer, default=0)


class CardSchedule(Base):
    __tablename__ = "card_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    flashcard_id: Mapped[int] = mapped_column(ForeignKey("flashcards.id"), unique=True)
    box: Mapped[int] = mapped_column(Integer, default=0)  # Leitner box 0-4
    ease_factor: Mapped[float] = mapped_column(Float, default=2.5)
    interval_cards: Mapped[int] = mapped_column(Integer, default=0)
    review_after_position: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_correct: Mapped[int] = mapped_column(Integer, default=0)
    total_reviews: Mapped[int] = mapped_column(Integer, default=0)
    total_correct: Mapped[int] = mapped_column(Integer, default=0)
    last_reviewed_at_position: Mapped[int] = mapped_column(Integer, default=0)
    last_confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0=again,1=hard,2=good,3=easy

    flashcard: Mapped["Flashcard"] = relationship(back_populates="schedule")


class QuizQuestionState(Base):
    __tablename__ = "quiz_question_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("quiz_questions.id"), unique=True)
    times_seen: Mapped[int] = mapped_column(Integer, default=0)
    times_correct: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    mastery_level: Mapped[float] = mapped_column(Float, default=0.0)  # 0.0 to 1.0
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    quiz_question: Mapped["QuizQuestion"] = relationship(back_populates="state")


from app.models.content import Flashcard, QuizQuestion  # noqa: E402, F401
