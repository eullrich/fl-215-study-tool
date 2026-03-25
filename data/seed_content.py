"""Extract flashcard and quiz data from legacy HTML files and seed the SQLite database."""

import asyncio
import json
import re
from pathlib import Path

from app.config import LEGACY_DIR
from app.database import Base, engine, async_session
from app.models.content import Chapter, Flashcard, QuizQuestion
from app.models.scheduling import CardSchedule, QuizQuestionState
from app.models.study import StudySession, CardReview  # noqa: F401 — ensure table created

CHAPTERS = {
    1: "Basic Principles of Life and Health Insurance",
    2: "Risk, Hazards, Perils & Methods of Handling Risk",
    3: "Insurance Contracts — Elements, Features & Legal Principles",
    4: "Life Insurance Products",
    5: "Life Insurance Policy Provisions, Riders & Exclusions",
}


def extract_js_array(html: str, var_name: str) -> list[dict]:
    """Extract a JS array variable from HTML source using regex to parse each object."""
    pattern = rf'const\s+{var_name}\s*=\s*\['
    match = re.search(pattern, html)
    if not match:
        raise ValueError(f"Could not find 'const {var_name} = [' in HTML")

    # Find the closing ];
    start = match.end()
    end_match = re.search(r'\n\s*\];', html[start:])
    if not end_match:
        raise ValueError(f"Could not find closing ]; for {var_name}")
    block = html[start:start + end_match.start()]

    # Parse each { ... } object individually
    results = []
    # Match each object block
    for obj_match in re.finditer(r'\{([^}]+)\}', block):
        obj_str = obj_match.group(1)
        obj = {}

        # Extract key-value pairs. Keys are: s, q, a, section, opts, ans, exp
        # Handle simple string values: key: "value"
        for kv in re.finditer(r'(\w+)\s*:\s*"((?:[^"\\]|\\.|"")*)"', obj_str):
            key = kv.group(1)
            val = kv.group(2)
            # Handle JS escaped quotes — sometimes \u201c/\u201d smart quotes
            # and sometimes literal nested double-quotes via ""
            val = val.replace('\\"', '"')
            obj[key] = val

        # Handle numeric values: ans: 2
        for kv in re.finditer(r'(\w+)\s*:\s*(\d+)\s*(?=[,}]|$)', obj_str):
            key = kv.group(1)
            obj[key] = int(kv.group(2))

        # Handle array values: opts: ["a", "b", "c", "d"]
        opts_match = re.search(r'opts\s*:\s*\[(.*?)\]', obj_str, re.DOTALL)
        if opts_match:
            opts_raw = opts_match.group(1)
            obj["opts"] = re.findall(r'"((?:[^"\\]|\\.)*)"', opts_raw)

        if obj:
            results.append(obj)

    return results


async def seed(reset: bool = False):
    """Seed the database from legacy HTML files."""
    if reset:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        total_cards = 0
        total_questions = 0

        for ch_num, ch_title in CHAPTERS.items():
            html_path = LEGACY_DIR / f"ch{ch_num}_study_tool.html"
            if not html_path.exists():
                print(f"  SKIP: {html_path} not found")
                continue

            html = html_path.read_text(encoding="utf-8")

            # Create chapter
            chapter = Chapter(id=ch_num, title=ch_title)
            session.add(chapter)

            # Extract and insert flashcards
            cards = extract_js_array(html, "cards")
            for idx, card in enumerate(cards):
                fc = Flashcard(
                    chapter_id=ch_num,
                    section=card.get("s"),
                    question=card["q"],
                    answer=card["a"],
                    order_index=idx,
                )
                session.add(fc)
                total_cards += 1

            # Extract and insert quiz questions
            questions = extract_js_array(html, "questions")
            for q in questions:
                qq = QuizQuestion(
                    chapter_id=ch_num,
                    section=q.get("section", ""),
                    question=q["q"],
                    options=q["opts"],
                    correct_index=q["ans"],
                    explanation=q.get("exp", ""),
                )
                session.add(qq)
                total_questions += 1

            print(f"  Ch{ch_num}: {len(cards)} flashcards, {len(questions)} quiz questions")

        await session.flush()

        # Initialize card schedules for all flashcards
        from sqlalchemy import select
        result = await session.execute(select(Flashcard.id))
        for (fc_id,) in result:
            session.add(CardSchedule(flashcard_id=fc_id))

        # Initialize quiz question states
        result = await session.execute(select(QuizQuestion.id))
        for (qq_id,) in result:
            session.add(QuizQuestionState(question_id=qq_id))

        await session.commit()
        print(f"\nSeeded: {total_cards} flashcards, {total_questions} quiz questions")
        print("Card schedules and quiz states initialized.")


if __name__ == "__main__":
    asyncio.run(seed(reset=True))
