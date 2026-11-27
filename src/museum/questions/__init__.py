"""Business questions: their specs, and how answers are compared (design sections 7 and 8)."""

from museum.questions.compare import Comparison, Result, compare
from museum.questions.spec import QUESTIONS_DIR, Question, discover, load_question

__all__ = [
    "QUESTIONS_DIR",
    "Comparison",
    "Question",
    "Result",
    "compare",
    "discover",
    "load_question",
]
