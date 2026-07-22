"""Lightweight keyword/tag retrieval over the local knowledge base.

Deliberately not a vector database: the knowledge base is a handful of small,
hand-curated documents, so a species match plus simple keyword overlap is enough
to reliably surface the right doc(s) without the setup cost of embeddings.
"""

import re
from typing import List

from advisor.knowledge_base import KBDoc, load_knowledge_base

_WORD_RE = re.compile(r"[a-z]+")


def _words(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def retrieve(species: str, context: str = "", top_n: int = 2, docs: List[KBDoc] | None = None) -> List[KBDoc]:
    """Return the top_n knowledge-base docs most relevant to the given species/context.

    'general' safety docs are always included alongside the best species-specific
    match so guardrail-relevant safety guidance is never left out of the prompt.
    """
    if docs is None:
        docs = load_knowledge_base()

    species = (species or "").strip().lower()
    context_words = _words(context)

    species_docs = [d for d in docs if d.species == species]
    general_docs = [d for d in docs if d.species == "general"]

    if not species_docs:
        return general_docs[:top_n]

    def score(doc: KBDoc) -> int:
        topic_words = _words(" ".join(doc.topics))
        return len(context_words & topic_words) + len(context_words & _words(doc.text))

    ranked = sorted(species_docs, key=score, reverse=True) if context_words else species_docs
    selected = ranked[:top_n]

    for gdoc in general_docs:
        if gdoc not in selected:
            selected.append(gdoc)

    return selected
