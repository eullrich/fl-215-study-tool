from datetime import datetime

from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StudySession(Base):
    __tablename__ = "study_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_type: Mapped[str] = mapped_column(String(20))  # "flashcard" | "quiz" | "exam_sim"
    chapter_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cards_reviewed: Mapped[int] = mapped_column(Integer, default=0)
    cards_correct: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)


class CardReview(Base):
    __tablename__ = "card_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("study_sessions.id"))
    flashcard_id: Mapped[int | None] = mapped_column(ForeignKey("flashcards.id"), nullable=True)
    question_id: Mapped[int | None] = mapped_column(ForeignKey("quiz_questions.id"), nullable=True)
    was_correct: Mapped[bool] = mapped_column(Boolean)
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-3 for flashcards
    response_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
