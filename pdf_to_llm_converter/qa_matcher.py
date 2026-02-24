"""QA matcher for semantic matching of questions to answer sections."""

from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

from pdf_to_llm_converter.models import (
    Document,
    DocumentSection,
    MatchResult,
    QAMatch,
)


class QAMatcher:
    """Matches questions to answer sections using semantic similarity."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model = SentenceTransformer(model_name)

    def match(
        self,
        questions: list[str],
        answer_sections: list[DocumentSection],
        top_n: int = 3,
        min_similarity: float = 0.5,
    ) -> list[QAMatch]:
        """Match questions to answer sections by semantic similarity."""
        if not questions:
            return []

        if not answer_sections:
            return [
                QAMatch(question=q, matches=[], is_unmatched=True)
                for q in questions
            ]

        # Encode questions and section texts into embeddings
        section_texts = [s.content for s in answer_sections]
        question_embeddings = self._model.encode(questions, convert_to_numpy=True)
        section_embeddings = self._model.encode(section_texts, convert_to_numpy=True)

        # Normalize for cosine similarity
        q_norms = np.linalg.norm(question_embeddings, axis=1, keepdims=True)
        q_norms = np.where(q_norms == 0, 1, q_norms)
        question_embeddings = question_embeddings / q_norms

        s_norms = np.linalg.norm(section_embeddings, axis=1, keepdims=True)
        s_norms = np.where(s_norms == 0, 1, s_norms)
        section_embeddings = section_embeddings / s_norms

        # Cosine similarity matrix: (num_questions, num_sections)
        similarity_matrix = question_embeddings @ section_embeddings.T
        # Clamp to [0.0, 1.0] — cosine similarity of normalized vectors can
        # produce tiny negative values due to floating-point arithmetic.
        similarity_matrix = np.clip(similarity_matrix, 0.0, 1.0)

        results: list[QAMatch] = []
        for i, question in enumerate(questions):
            scores = similarity_matrix[i]
            # Get indices sorted by descending similarity
            ranked_indices = np.argsort(scores)[::-1]

            matches: list[MatchResult] = []
            for idx in ranked_indices:
                score = float(scores[idx])
                if score < min_similarity:
                    break
                if len(matches) >= top_n:
                    break
                section = answer_sections[idx]
                excerpt = section.content[:500]
                matches.append(
                    MatchResult(
                        section_title=section.title,
                        page_range=(section.page_start, section.page_end),
                        similarity_score=score,
                        text_excerpt=excerpt,
                    )
                )

            results.append(
                QAMatch(
                    question=question,
                    matches=matches,
                    is_unmatched=len(matches) == 0,
                )
            )

        return results

    @staticmethod
    def split_into_sections(document: Document) -> list[DocumentSection]:
        """Flatten the section hierarchy into a flat list of leaf sections."""
        flat: list[DocumentSection] = []

        def _collect(sections: list[DocumentSection]) -> None:
            for section in sections:
                if section.subsections:
                    _collect(section.subsections)
                else:
                    flat.append(section)

        _collect(document.sections)
        return flat
