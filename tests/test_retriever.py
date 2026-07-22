from advisor.knowledge_base import KBDoc
from advisor.retriever import retrieve

_DOGS = KBDoc(doc_id="dog_care", species="dog", topics=["walk", "feeding"], text="dog walk feeding text")
_CATS = KBDoc(doc_id="cat_care", species="cat", topics=["litter", "feeding"], text="cat litter feeding text")
_GENERAL = KBDoc(doc_id="general_safety", species="general", topics=["safety"], text="general safety text")
_ALL_DOCS = [_DOGS, _CATS, _GENERAL]


def test_retrieve_returns_species_specific_doc_plus_general():
    results = retrieve(species="dog", context="", docs=_ALL_DOCS)

    doc_ids = [d.doc_id for d in results]
    assert "dog_care" in doc_ids
    assert "general_safety" in doc_ids
    assert "cat_care" not in doc_ids


def test_retrieve_unknown_species_returns_only_general_docs():
    results = retrieve(species="iguana", context="", docs=_ALL_DOCS)

    assert results == [_GENERAL]


def test_retrieve_empty_docs_list_returns_empty():
    assert retrieve(species="dog", context="", docs=[]) == []
