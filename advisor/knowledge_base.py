"""Loads the local pet-care knowledge base (markdown docs with a small frontmatter block)."""

from dataclasses import dataclass
from pathlib import Path
from typing import List

KB_DIR = Path(__file__).resolve().parent.parent / "knowledge_base"


@dataclass
class KBDoc:
    """One knowledge-base document: its id, tagged species/topics, and body text."""

    doc_id: str
    species: str
    topics: List[str]
    text: str


def _parse_frontmatter(raw: str) -> tuple[dict, str]:
    """Split a '---\\nkey: value\\n---\\nbody' file into a dict of fields and the body text."""
    lines = raw.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, raw

    fields: dict = {}
    body_start = len(lines)
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            body_start = i + 1
            break
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()

    body = "\n".join(lines[body_start:]).strip()
    return fields, body


def load_knowledge_base(kb_dir: Path = KB_DIR) -> List[KBDoc]:
    """Read every .md file in kb_dir and return them as parsed KBDoc records."""
    docs: List[KBDoc] = []
    for path in sorted(kb_dir.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        fields, body = _parse_frontmatter(raw)
        species = fields.get("species", "general").lower()
        topics = [t.strip().lower() for t in fields.get("topics", "").split(",") if t.strip()]
        docs.append(KBDoc(doc_id=path.stem, species=species, topics=topics, text=body))
    return docs
