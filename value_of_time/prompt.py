"""Build the user prompt for one cell: persona, optional memories, ONE survey question.

No numeric answer exemplars appear anywhere (they anchor small models), and the prompt never says the
memories are relevant to the question.
"""
from __future__ import annotations

from .design import Cell
from .stimuli import FACT_BY_ID, PERSONA, QUESTION_BY_ID

INTRO = "Please read this description of yourself and answer as this person."
FACTS_HEADER = "Some things you remember from your recent life:"
SURVEY_HEADER = "Now please answer this survey question as yourself. There are no right or wrong answers."
FORMAT = "Reply with only a single dollar amount, written as a plain number with no dollar sign, words, or range."


def build_prompt(cell: Cell) -> str:
    parts = [INTRO, PERSONA]
    if cell.fact_order:
        parts.append(FACTS_HEADER + "\n" + "\n".join(f"- {FACT_BY_ID[f].text}" for f in cell.fact_order))
    parts += [SURVEY_HEADER, QUESTION_BY_ID[cell.question].text, FORMAT]
    return "\n\n".join(parts)
