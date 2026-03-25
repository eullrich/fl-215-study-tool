from sqlalchemy import Integer, String, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")

    flashcards: Mapped[list["Flashcard"]] = relationship(back_populates="chapter", cascade="all, delete-orphan")
    quiz_questions: Mapped[list["QuizQuestion"]] = relationship(back_populates="chapter", cascade="all, delete-orphan")


class Flashcard(Base):
    __tablename__ = "flashcards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id"))
    section: Mapped[str | None] = mapped_column(String(200), nullable=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    chapter: Mapped["Chapter"] = relationship(back_populates="flashcards")
    schedule: Mapped["CardSchedule | None"] = relationship(back_populates="flashcard", uselist=False)


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id"))
    section: Mapped[str] = mapped_column(String(200), default="")
    question: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSON)
    correct_index: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[str] = mapped_column(Text, default="")

    chapter: Mapped["Chapter"] = relationship(back_populates="quiz_questions")
    state: Mapped["QuizQuestionState | None"] = relationship(back_populates="quiz_question", uselist=False)


# Avoid circular import — these are imported at module level for type hints
from app.models.scheduling import CardSchedule, QuizQuestionState  # noqa: E402, F401
