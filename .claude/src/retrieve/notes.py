"""Note model + lazy loading + wikilink parsing for the retriever.

A ``NoteRef`` is the lightweight metadata the index holds for every note (no
body). A ``Note`` is a ref plus its content, produced only by ``load_note()``
on demand at query time — we never load the whole corpus into memory.

Wikilink grammar follows the Obsidian convention (see the obsidian-markdown
skill, https://github.com/kepano/obsidian-skills): ``[[target]]``,
``[[target|alias]]`` (the target is taken, alias dropped), and
``[[target#heading]]`` / ``[[target#^block]]`` (the anchor is stripped).
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import frontmatter

_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """Normalise a title or link target to a filename-style slug.

    Consolidates the previously-duplicated slug logic in paper_agent.py and
    knowledge_agent.py. e.g. ``"tool use"`` -> ``"tool-use"``.
    """
    return _SLUG_RE.sub("-", str(name).lower()).strip("-")


def parse_wikilinks(content: str) -> list[str]:
    """Return the slugified targets of every ``[[wikilink]]`` in ``content``.

    Handles ``[[target|alias]]`` and ``[[target#heading]]`` / ``[[target#^id]]``
    by keeping only the target portion before ``|`` and ``#``.
    """
    slugs: list[str] = []
    for raw in _WIKILINK_RE.findall(content):
        target = raw.split("|", 1)[0].split("#", 1)[0].strip()
        if target:
            slugs.append(slugify(target))
    return slugs


def _as_list(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value]


def build_links(post: "frontmatter.Post") -> dict[str, list[str]]:
    """Outgoing links from a note, grouped by edge type (slugified targets)."""
    return {
        "wikilink": parse_wikilinks(post.content),
        "related_concepts": [slugify(x) for x in _as_list(post.get("related_concepts"))],
        "related_papers": [slugify(x) for x in _as_list(post.get("related_papers"))],
    }


@dataclass
class NoteRef:
    """Lightweight note metadata held in the index — no body."""

    slug: str
    path: Path
    kind: str  # "paper" | "concept"
    title: str
    links: dict[str, list[str]] = field(default_factory=dict)
    aliases: list[str] = field(default_factory=list)


@dataclass
class Note:
    """A note ref together with its (lazily loaded) content."""

    ref: NoteRef
    content: str


def ref_from_path(path: Path, kind: str) -> NoteRef:
    """Build a NoteRef by reading only the frontmatter + links from a file."""
    post = frontmatter.load(path)
    return NoteRef(
        slug=slugify(path.stem),
        path=path,
        kind=kind,
        title=str(post.get("title", path.stem)),
        links=build_links(post),
        aliases=[slugify(a) for a in _as_list(post.get("aliases"))],
    )


def load_note(ref: NoteRef) -> Note:
    """Lazily load a single note's body on demand (query time only)."""
    post = frontmatter.load(ref.path)
    return Note(ref=ref, content=post.content)
