#!/usr/bin/env python3
"""Generate Markdown documentation with Mermaid diagrams from TypeQL schema files.

Usage:
    python generate_schema_docs.py [--output-dir docs/]

Parses .tql files from the project's TypeDB schema directory and generates
GitHub-renderable Markdown with embedded Mermaid class/ER diagrams, per-type
javadoc tables, and curated query examples.
"""

import argparse
import json
import re
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# =============================================================================
# Data Model
# =============================================================================

@dataclass
class OwnsClause:
    attribute: str
    is_key: bool = False
    defined_in: str = ""  # which file defined this owns


@dataclass
class PlaysClause:
    relation: str
    role: str
    defined_in: str = ""


@dataclass
class RelatesClause:
    role: str
    defined_in: str = ""


@dataclass
class TypeDef:
    name: str
    kind: str  # "entity", "relation", "attribute"
    parent: str = ""
    is_abstract: bool = False
    value_type: str = ""  # for attributes: string, long, double, etc.
    owns: list[OwnsClause] = field(default_factory=list)
    plays: list[PlaysClause] = field(default_factory=list)
    relates: list[RelatesClause] = field(default_factory=list)
    defined_in: str = ""  # file where first defined
    comment: str = ""  # comment block above the declaration
    section: str = ""  # TQL section header (e.g. "Diagnostic Phase")


@dataclass
class SchemaModel:
    types: dict[str, TypeDef] = field(default_factory=dict)

    def get_ancestors(self, name: str) -> list[str]:
        """Walk the parent chain, returning [parent, grandparent, ...]."""
        ancestors = []
        current = name
        seen = set()
        while current in self.types and self.types[current].parent:
            parent = self.types[current].parent
            if parent in seen:
                break
            seen.add(parent)
            ancestors.append(parent)
            current = parent
        return ancestors

    def get_inherited_owns(self, name: str) -> list[tuple[OwnsClause, str]]:
        """Return [(OwnsClause, inherited_from), ...] for all ancestors."""
        result = []
        own_attrs = {o.attribute for o in self.types[name].owns}
        for ancestor in self.get_ancestors(name):
            if ancestor not in self.types:
                continue
            for o in self.types[ancestor].owns:
                if o.attribute not in own_attrs:
                    result.append((o, ancestor))
                    own_attrs.add(o.attribute)
        return result

    def get_inherited_plays(self, name: str) -> list[tuple[PlaysClause, str]]:
        """Return [(PlaysClause, inherited_from), ...] for all ancestors."""
        result = []
        own_plays = {(p.relation, p.role) for p in self.types[name].plays}
        for ancestor in self.get_ancestors(name):
            if ancestor not in self.types:
                continue
            for p in self.types[ancestor].plays:
                if (p.relation, p.role) not in own_plays:
                    result.append((p, ancestor))
                    own_plays.add((p.relation, p.role))
        return result


# =============================================================================
# TQL Parser
# =============================================================================

# Regex patterns for TypeQL declarations
RE_COMMENT = re.compile(r"^#\s*(.*)")
RE_SECTION_HEADER = re.compile(r"^#\s*[-=]{3,}")
RE_SECTION_TITLE = re.compile(r"^#\s+([A-Z][\w\s/()-]+)")
RE_ATTRIBUTE_DEF = re.compile(
    r"^([\w-]+)\s+sub\s+attribute\s*,\s*value\s+(\w+)\s*;"
)
RE_TYPE_START = re.compile(
    r"^([\w-]+)\s+sub\s+([\w-]+)\s*([,;])"
)
RE_OWNS = re.compile(r"^\s*owns\s+([\w-]+)(\s+@key)?\s*([,;])")
RE_PLAYS = re.compile(r"^\s*plays\s+([\w-]+):([\w-]+)\s*([,;])")
RE_RELATES = re.compile(r"^\s*relates\s+([\w-]+)\s*([,;])")
RE_ABSTRACT = re.compile(r"^\s*abstract\s*([,;])")
# Bare extension: `typename plays relation:role;`
RE_BARE_PLAYS = re.compile(
    r"^([\w-]+)\s+plays\s+([\w-]+):([\w-]+)\s*;"
)
# Bare extension: `typename owns attr;`
RE_BARE_OWNS = re.compile(
    r"^([\w-]+)\s+owns\s+([\w-]+)(\s+@key)?\s*;"
)


def classify_type(parent: str) -> str:
    """Determine if a type is entity, relation, or attribute based on parent."""
    if parent == "attribute":
        return "attribute"
    if parent == "relation":
        return "relation"
    if parent == "entity":
        return "entity"
    # Default: inherit from parent (resolved later)
    return ""


def parse_tql_file(filepath: Path, model: SchemaModel) -> None:
    """Parse a single .tql file and merge into the model."""
    source_name = filepath.stem  # e.g. "alhazen_notebook", "scilit"
    if source_name == "alhazen_notebook":
        source_name = "core"

    lines = filepath.read_text().splitlines()
    current_section = ""
    comment_block = []
    i = 0

    def _is_separator(idx: int) -> bool:
        """Check if a line is a section separator (# --- or # ===)."""
        if 0 <= idx < len(lines):
            return bool(RE_SECTION_HEADER.match(lines[idx].rstrip()))
        return False

    while i < len(lines):
        line = lines[i].rstrip()

        # Detect section headers: separator / title / separator pattern
        # Look for: line[i] is separator, line[i+1] is title, line[i+2] is separator
        if _is_separator(i) and i + 2 < len(lines) and _is_separator(i + 2):
            title_line = lines[i + 1].rstrip()
            title_match = RE_SECTION_TITLE.match(title_line)
            if title_match:
                candidate = title_match.group(1).strip()
                if len(candidate) > 3 and "END" not in candidate:
                    current_section = candidate
            i += 3  # skip all 3 lines of the header block
            continue

        # Skip standalone separator lines (e.g. closing === of file header)
        if RE_SECTION_HEADER.match(line):
            i += 1
            continue

        # Collect comment lines
        comment_match = RE_COMMENT.match(line)
        if comment_match:
            text = comment_match.group(1).strip()
            if text:
                comment_block.append(text)
            i += 1
            continue

        # Skip blank/define lines
        if not line.strip() or line.strip() == "define":
            if not line.strip():
                comment_block = []
            i += 1
            continue

        # Attribute definition (single line)
        attr_match = RE_ATTRIBUTE_DEF.match(line)
        if attr_match:
            name, value_type = attr_match.group(1), attr_match.group(2)
            if name not in model.types:
                comment_text = " ".join(comment_block) if comment_block else ""
                model.types[name] = TypeDef(
                    name=name,
                    kind="attribute",
                    parent="attribute",
                    value_type=value_type,
                    defined_in=source_name,
                    comment=comment_text,
                    section=current_section,
                )
            comment_block = []
            i += 1
            continue

        # Bare plays extension: `typename plays relation:role;`
        bare_plays = RE_BARE_PLAYS.match(line)
        if bare_plays:
            type_name = bare_plays.group(1)
            relation = bare_plays.group(2)
            role = bare_plays.group(3)
            if type_name in model.types:
                model.types[type_name].plays.append(
                    PlaysClause(relation=relation, role=role, defined_in=source_name)
                )
            else:
                # Create a placeholder
                model.types[type_name] = TypeDef(
                    name=type_name, kind="entity", defined_in=source_name
                )
                model.types[type_name].plays.append(
                    PlaysClause(relation=relation, role=role, defined_in=source_name)
                )
            comment_block = []
            i += 1
            continue

        # Bare owns extension
        bare_owns = RE_BARE_OWNS.match(line)
        if bare_owns:
            type_name = bare_owns.group(1)
            attr_name = bare_owns.group(2)
            is_key = bare_owns.group(3) is not None
            if type_name in model.types:
                model.types[type_name].owns.append(
                    OwnsClause(attribute=attr_name, is_key=is_key, defined_in=source_name)
                )
            comment_block = []
            i += 1
            continue

        # Type declaration start
        type_match = RE_TYPE_START.match(line)
        if type_match:
            name = type_match.group(1)
            parent = type_match.group(2)
            terminator = type_match.group(3)

            comment_text = " ".join(comment_block) if comment_block else ""
            comment_block = []

            kind = classify_type(parent)

            # Check if type already exists (merging extensions)
            if name in model.types:
                typedef = model.types[name]
            else:
                typedef = TypeDef(
                    name=name,
                    kind=kind,
                    parent=parent,
                    defined_in=source_name,
                    comment=comment_text,
                    section=current_section,
                )
                model.types[name] = typedef

            # Check for abstract on same line
            rest_of_line = line[type_match.end():]
            if "abstract" in rest_of_line:
                typedef.is_abstract = True

            # If terminated with `;`, it's complete
            if terminator == ";":
                i += 1
                continue

            # Multi-line: read owns/plays/relates until `;`
            i += 1
            while i < len(lines):
                subline = lines[i].rstrip()

                abstract_match = RE_ABSTRACT.match(subline)
                if abstract_match:
                    typedef.is_abstract = True
                    if abstract_match.group(1) == ";":
                        i += 1
                        break
                    i += 1
                    continue

                owns_match = RE_OWNS.match(subline)
                if owns_match:
                    attr_name = owns_match.group(1)
                    is_key = owns_match.group(2) is not None
                    # Avoid duplicate owns
                    existing = {o.attribute for o in typedef.owns}
                    if attr_name not in existing:
                        typedef.owns.append(
                            OwnsClause(attribute=attr_name, is_key=is_key, defined_in=source_name)
                        )
                    if owns_match.group(3) == ";":
                        i += 1
                        break
                    i += 1
                    continue

                plays_match = RE_PLAYS.match(subline)
                if plays_match:
                    relation = plays_match.group(1)
                    role = plays_match.group(2)
                    existing = {(p.relation, p.role) for p in typedef.plays}
                    if (relation, role) not in existing:
                        typedef.plays.append(
                            PlaysClause(relation=relation, role=role, defined_in=source_name)
                        )
                    if plays_match.group(3) == ";":
                        i += 1
                        break
                    i += 1
                    continue

                relates_match = RE_RELATES.match(subline)
                if relates_match:
                    role_name = relates_match.group(1)
                    existing = {r.role for r in typedef.relates}
                    if role_name not in existing:
                        typedef.relates.append(
                            RelatesClause(role=role_name, defined_in=source_name)
                        )
                    if relates_match.group(2) == ";":
                        i += 1
                        break
                    i += 1
                    continue

                # Check for owns on same line as relates (multi-attr relations)
                if subline.strip().startswith("owns"):
                    owns_match2 = RE_OWNS.match(subline)
                    if owns_match2:
                        attr_name = owns_match2.group(1)
                        is_key = owns_match2.group(2) is not None
                        existing = {o.attribute for o in typedef.owns}
                        if attr_name not in existing:
                            typedef.owns.append(
                                OwnsClause(attribute=attr_name, is_key=is_key, defined_in=source_name)
                            )
                        if owns_match2.group(3) == ";":
                            i += 1
                            break

                i += 1
            continue

        comment_block = []
        i += 1

    # Resolve kinds for types whose kind couldn't be determined from parent name
    _resolve_kinds(model)


def _resolve_kinds(model: SchemaModel) -> None:
    """Resolve type kinds by walking parent chains."""
    for name, typedef in model.types.items():
        if typedef.kind:
            continue
        chain = [name]
        current = typedef.parent
        while current and current in model.types:
            if model.types[current].kind:
                typedef.kind = model.types[current].kind
                break
            chain.append(current)
            current = model.types[current].parent
        if not typedef.kind:
            typedef.kind = "entity"  # fallback


# =============================================================================
# Namespace Classification
# =============================================================================

NAMESPACE_META = {
    "core": {
        "title": "Core Schema",
        "description": "The foundational Alhazen Notebook Model — five ICE subtypes, agents, classification, and provenance.",
        "file": "alhazen_notebook.tql",
    },
    "scilit": {
        "title": "Scientific Literature (scilit)",
        "description": "Domain-specific subtypes for scientific literature analysis: papers, datasets, preprints, and structured extraction.",
        "file": "namespaces/scilit.tql",
    },
    "jobhunt": {
        "title": "Job Hunting (jobhunt)",
        "description": "Job hunting and career management: positions, companies, skill gaps, learning resources, and application tracking.",
        "file": "namespaces/jobhunt.tql",
    },
    "apm": {
        "title": "Algorithm for Precision Medicine (apm)",
        "description": "Rare disease investigation following Matt Might's APM: diagnostic phase (symptoms → molecular diagnosis) and therapeutic phase (mechanism → treatment).",
        "file": "namespaces/apm.tql",
    },
}


def types_in_namespace(model: SchemaModel, ns: str) -> list[TypeDef]:
    """Return all types defined in a namespace, sorted by kind then name."""
    kind_order = {"attribute": 0, "entity": 1, "relation": 2}
    types = [t for t in model.types.values() if t.defined_in == ns]
    return sorted(types, key=lambda t: (kind_order.get(t.kind, 9), t.name))


# =============================================================================
# Mermaid Generators
# =============================================================================

# Mermaid reserved keywords that can't be used as identifiers
_MERMAID_RESERVED = {
    "note", "class", "end", "style", "click", "callback",
    "link", "direction", "subgraph", "section",
}


def _mermaid_safe(name: str) -> str:
    """Make a name safe for Mermaid identifiers (replace hyphens, escape reserved words)."""
    safe = name.replace("-", "_")
    if safe in _MERMAID_RESERVED:
        safe = safe + "_t"
    return safe


def generate_class_diagram(model: SchemaModel, ns: str) -> str:
    """Generate a Mermaid class diagram showing type hierarchy for a namespace."""
    lines = ["classDiagram", "    direction LR"]
    ns_types = types_in_namespace(model, ns)

    # Only show entities and relations (not attributes)
    entity_types = [t for t in ns_types if t.kind in ("entity", "relation")]

    # Track which external parents we need to show
    external_parents = set()

    for typedef in entity_types:
        safe = _mermaid_safe(typedef.name)
        # Class declaration with key attributes
        own_attrs = [o.attribute for o in typedef.owns[:5]]  # limit to 5
        if own_attrs:
            lines.append(f"    class {safe} {{")
            for attr in own_attrs:
                lines.append(f"        +{attr}")
            lines.append("    }")
        else:
            lines.append(f"    class {safe}")

        if typedef.is_abstract:
            lines.append(f"    <<abstract>> {safe}")

        # Inheritance arrow
        if typedef.parent and typedef.parent not in ("entity", "relation", "attribute"):
            parent_safe = _mermaid_safe(typedef.parent)
            lines.append(f"    {parent_safe} <|-- {safe}")
            # Check if parent is external
            if typedef.parent in model.types and model.types[typedef.parent].defined_in != ns:
                external_parents.add(typedef.parent)

    # Show external parent types with stereotype
    for ext in external_parents:
        safe = _mermaid_safe(ext)
        ext_ns = model.types[ext].defined_in
        lines.append(f"    class {safe}")
        lines.append(f'    <<{ext_ns}>> {safe}')

    return "\n".join(lines)


def generate_er_diagram(
    model: SchemaModel, ns: str, section_filter: Optional[str] = None
) -> str:
    """Generate a Mermaid ER diagram showing relationships for a namespace.

    For core: only shows direct role players (not inherited from subtypes in other
    namespaces) to avoid combinatorial explosion.
    For namespaces: shows direct players + types from same namespace that inherit roles.
    """
    lines = ["erDiagram"]
    ns_types = types_in_namespace(model, ns)

    relations = [t for t in ns_types if t.kind == "relation"]
    if section_filter:
        relations = [r for r in relations if section_filter.lower() in r.section.lower()]

    seen_edges: set[tuple[str, str, str]] = set()

    for rel in relations:
        # Find which entity types play each role
        role_players: dict[str, list[str]] = {}
        for role_clause in rel.relates:
            role_name = role_clause.role
            players = []
            for t in model.types.values():
                if t.kind != "entity":
                    continue
                # Direct plays (declared on the type itself)
                for p in t.plays:
                    if p.relation == rel.name and p.role == role_name:
                        players.append(t.name)
                # For non-core namespaces, also include types from the same
                # namespace that inherit the role from a core parent
                if ns != "core" and t.defined_in == ns:
                    for p_clause, _ in model.get_inherited_plays(t.name):
                        if p_clause.relation == rel.name and p_clause.role == role_name:
                            if t.name not in players:
                                players.append(t.name)
            role_players[role_name] = players

        # Generate ER edges between all role-player pair combinations
        roles = list(role_players.keys())
        if len(roles) >= 2:
            # For each pair of roles, connect their players
            for ri in range(len(roles)):
                for rj in range(ri + 1, len(roles)):
                    left_players = role_players[roles[ri]]
                    right_players = role_players[roles[rj]]
                    for lp in left_players:
                        for rp in right_players:
                            edge_key = (lp, rp, rel.name)
                            rev_key = (rp, lp, rel.name)
                            if edge_key in seen_edges or rev_key in seen_edges:
                                continue
                            seen_edges.add(edge_key)
                            lp_safe = _mermaid_safe(lp)
                            rp_safe = _mermaid_safe(rp)
                            lines.append(
                                f"    {lp_safe} }}|--o{{ {rp_safe} : {_mermaid_safe(rel.name)}"
                            )

    return "\n".join(lines)


# =============================================================================
# Markdown Generators
# =============================================================================

def generate_type_table(model: SchemaModel, typedef: TypeDef) -> str:
    """Generate a markdown section documenting a single type."""
    lines = []
    kind_label = typedef.kind.capitalize()
    parent_display = f"`{typedef.parent}`" if typedef.parent and typedef.parent not in ("entity", "relation", "attribute") else typedef.parent

    lines.append(f"### `{typedef.name}`")
    lines.append("")
    if typedef.comment:
        lines.append(f"> {typedef.comment}")
        lines.append("")

    lines.append(f"- **Kind:** {kind_label}")
    lines.append(f"- **Parent:** {parent_display}")
    if typedef.is_abstract:
        lines.append("- **Abstract:** Yes")
    if typedef.value_type:
        lines.append(f"- **Value type:** `{typedef.value_type}`")
    lines.append(f"- **Defined in:** `{typedef.defined_in}`")
    lines.append("")

    # Owns table
    all_owns = [(o, typedef.defined_in) for o in typedef.owns]
    inherited = model.get_inherited_owns(typedef.name)
    if all_owns or inherited:
        lines.append("**Attributes (owns):**")
        lines.append("")
        lines.append("| Attribute | Key? | Defined In |")
        lines.append("|-----------|------|------------|")
        for o, src in all_owns:
            key = "@key" if o.is_key else ""
            lines.append(f"| `{o.attribute}` | {key} | {src} |")
        for o, src in inherited:
            key = "@key" if o.is_key else ""
            lines.append(f"| `{o.attribute}` | {key} | *{src}* (inherited) |")
        lines.append("")

    # Plays table
    all_plays = [(p, typedef.defined_in) for p in typedef.plays]
    inherited_plays = model.get_inherited_plays(typedef.name)
    if all_plays or inherited_plays:
        lines.append("**Roles (plays):**")
        lines.append("")
        lines.append("| Relation | Role | Defined In |")
        lines.append("|----------|------|------------|")
        for p, src in all_plays:
            lines.append(f"| `{p.relation}` | `{p.role}` | {src} |")
        for p, src in inherited_plays:
            lines.append(f"| `{p.relation}` | `{p.role}` | *{src}* (inherited) |")
        lines.append("")

    # Relates table (for relations)
    if typedef.relates:
        lines.append("**Roles (relates):**")
        lines.append("")
        lines.append("| Role |")
        lines.append("|------|")
        for r in typedef.relates:
            lines.append(f"| `{r.role}` |")
        lines.append("")

    return "\n".join(lines)


def generate_namespace_page(model: SchemaModel, ns: str, query_examples: dict) -> str:
    """Generate a full markdown page for a namespace."""
    meta = NAMESPACE_META[ns]
    lines = []
    lines.append(f"# {meta['title']}")
    lines.append("")
    lines.append(f"> **Source:** `{meta['file']}`")
    lines.append("")
    lines.append(meta["description"])
    lines.append("")

    ns_types = types_in_namespace(model, ns)
    entities = [t for t in ns_types if t.kind == "entity"]
    relations = [t for t in ns_types if t.kind == "relation"]
    attributes = [t for t in ns_types if t.kind == "attribute"]

    lines.append(f"**Summary:** {len(entities)} entities, {len(relations)} relations, {len(attributes)} attributes")
    lines.append("")

    # Table of Contents
    lines.append("## Contents")
    lines.append("")
    lines.append("- [Type Hierarchy](#type-hierarchy)")
    lines.append("- [Relationships](#relationships)")
    if attributes:
        lines.append("- [Attributes](#attributes)")
    lines.append("- [Entity Types](#entity-types)")
    if relations:
        lines.append("- [Relation Types](#relation-types)")
    if ns in query_examples:
        lines.append("- [Query Examples](#query-examples)")
    lines.append("")

    # Class diagram
    lines.append("## Type Hierarchy")
    lines.append("")
    class_diagram = generate_class_diagram(model, ns)
    lines.append("```mermaid")
    lines.append(class_diagram)
    lines.append("```")
    lines.append("")

    # ER diagram
    lines.append("## Relationships")
    lines.append("")
    if ns == "apm" and len(relations) > 8:
        # Split APM into diagnostic and therapeutic phases
        lines.append("### Diagnostic Phase")
        lines.append("")
        lines.append("```mermaid")
        lines.append(generate_er_diagram(model, ns, section_filter="Diagnostic"))
        lines.append("```")
        lines.append("")
        lines.append("### Therapeutic Phase")
        lines.append("")
        lines.append("```mermaid")
        lines.append(generate_er_diagram(model, ns, section_filter="Therapeutic"))
        lines.append("```")
    else:
        er_diagram = generate_er_diagram(model, ns)
        lines.append("```mermaid")
        lines.append(er_diagram)
        lines.append("```")
    lines.append("")

    # Attribute types
    if attributes:
        lines.append("## Attributes")
        lines.append("")
        lines.append("| Attribute | Value Type | Description |")
        lines.append("|-----------|-----------|-------------|")
        for t in attributes:
            desc = t.comment[:80] if t.comment else ""
            lines.append(f"| `{t.name}` | `{t.value_type}` | {desc} |")
        lines.append("")

    # Entity types - detailed docs
    lines.append("## Entity Types")
    lines.append("")
    for t in entities:
        lines.append(generate_type_table(model, t))

    # Relation types - detailed docs
    if relations:
        lines.append("## Relation Types")
        lines.append("")
        for t in relations:
            lines.append(generate_type_table(model, t))

    # Query examples
    if ns in query_examples:
        lines.append("## Query Examples")
        lines.append("")
        for section in query_examples[ns]:
            lines.append(f"### {section['title']}")
            lines.append("")
            if section.get("description"):
                lines.append(section["description"])
                lines.append("")
            for ex in section["examples"]:
                lines.append(f"**{ex['title']}**")
                if ex.get("command"):
                    lines.append(f"*Used by:* `{ex['command']}`")
                lines.append("")
                lines.append("```typeql")
                lines.append(ex["query"])
                lines.append("```")
                lines.append("")

    return "\n".join(lines)


def generate_index_page(model: SchemaModel) -> str:
    """Generate the index.md overview page."""
    lines = []
    lines.append("# TypeDB Schema Documentation")
    lines.append("")
    lines.append("> Auto-generated by `generate_schema_docs.py`. Do not edit manually.")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    lines.append("The Alhazen Notebook Model is a TypeDB knowledge graph schema for agent memory systems.")
    lines.append("It follows a five-level hierarchy: **Collection → Thing → Artifact → Fragment → Note**.")
    lines.append("")

    # Stats
    all_types = model.types.values()
    entities = [t for t in all_types if t.kind == "entity"]
    relations = [t for t in all_types if t.kind == "relation"]
    attributes = [t for t in all_types if t.kind == "attribute"]
    lines.append(f"**Total types:** {len(entities)} entities, {len(relations)} relations, {len(attributes)} attributes")
    lines.append("")

    # Core model diagram
    lines.append("## Core Model")
    lines.append("")
    lines.append("The five primary ICE (Information Content Entity) subtypes form the backbone:")
    lines.append("")
    lines.append("```mermaid")
    lines.append("classDiagram")
    lines.append("    direction LR")
    lines.append("    class information_content_entity {")
    lines.append("        +id @key")
    lines.append("        +name")
    lines.append("        +description")
    lines.append("        +content")
    lines.append("        +created-at")
    lines.append("    }")
    lines.append("    <<abstract>> information_content_entity")
    lines.append("    information_content_entity <|-- collection")
    lines.append("    information_content_entity <|-- research_item")
    lines.append("    information_content_entity <|-- artifact")
    lines.append("    information_content_entity <|-- fragment")
    lines.append("    information_content_entity <|-- note_t")
    lines.append("    information_content_entity <|-- user_question")
    lines.append("    information_content_entity <|-- information_resource")
    lines.append("")
    lines.append("    class collection {")
    lines.append("        +logical-query")
    lines.append("        +is-extensional")
    lines.append("    }")
    lines.append("    class research_item {")
    lines.append("        +abstract-text")
    lines.append("        +publication-date")
    lines.append("    }")
    lines.append("    class artifact")
    lines.append("    class fragment {")
    lines.append("        +offset")
    lines.append("        +length")
    lines.append("    }")
    lines.append("    class note_t {")
    lines.append("        +confidence")
    lines.append("    }")
    lines.append("    class user_question")
    lines.append("    class information_resource")
    lines.append("```")
    lines.append("")

    # Namespace summary table
    lines.append("## Namespaces")
    lines.append("")
    lines.append("| Namespace | Description | Entities | Relations | Attributes | Docs |")
    lines.append("|-----------|-------------|----------|-----------|------------|------|")
    for ns, meta in NAMESPACE_META.items():
        ns_ents = len([t for t in all_types if t.defined_in == ns and t.kind == "entity"])
        ns_rels = len([t for t in all_types if t.defined_in == ns and t.kind == "relation"])
        ns_attrs = len([t for t in all_types if t.defined_in == ns and t.kind == "attribute"])
        lines.append(f"| **{meta['title']}** | {meta['description'][:60]}... | {ns_ents} | {ns_rels} | {ns_attrs} | [{ns}.md]({ns}.md) |")
    lines.append("")

    # Agent and classification subsystem
    lines.append("## Agent & Classification Subsystem")
    lines.append("")
    lines.append("```mermaid")
    lines.append("classDiagram")
    lines.append("    direction LR")
    lines.append("    class agent {")
    lines.append("        +id @key")
    lines.append("        +name")
    lines.append("        +agent-type")
    lines.append("        +model-name")
    lines.append("    }")
    lines.append("    agent <|-- author")
    lines.append("    class author")
    lines.append("    class organization {")
    lines.append("        +id @key")
    lines.append("        +name")
    lines.append("    }")
    lines.append("    class vocabulary {")
    lines.append("        +id @key")
    lines.append("        +name")
    lines.append("    }")
    lines.append("    class vocabulary_type {")
    lines.append("        +schema-org-uri")
    lines.append("        +wikidata-qid")
    lines.append("    }")
    lines.append("    class vocabulary_property {")
    lines.append("        +schema-org-uri")
    lines.append("    }")
    lines.append("    class tag {")
    lines.append("        +id @key")
    lines.append("        +name")
    lines.append("    }")
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


# =============================================================================
# Main
# =============================================================================

# =============================================================================
# Wiki Support
# =============================================================================

# Maps namespace key -> wiki page name (without .md)
WIKI_PAGE_NAMES = {
    "core": "Schema: Core",
    "scilit": "Schema: Scientific Literature",
    "jobhunt": "Schema: Job Hunting",
    "apm": "Schema: Precision Medicine",
}
WIKI_INDEX_NAME = "Schema Reference"


def _wiki_filename(page_name: str) -> str:
    """Convert wiki page name to filename: 'Schema: Core' -> 'Schema:-Core.md'."""
    return page_name.replace(": ", ":-").replace(" ", "-") + ".md"


def generate_index_page_wiki(model: SchemaModel) -> str:
    """Generate wiki-compatible index page with [[wiki links]]."""
    lines = []
    lines.append(f"# {WIKI_INDEX_NAME}")
    lines.append("")
    lines.append("> Auto-generated by `generate_schema_docs.py`. Do not edit manually.")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    lines.append("The Alhazen Notebook Model is a TypeDB knowledge graph schema for agent memory systems.")
    lines.append("It follows a five-level hierarchy: **Collection \u2192 Thing \u2192 Artifact \u2192 Fragment \u2192 Note**.")
    lines.append("")

    all_types = model.types.values()
    entities = [t for t in all_types if t.kind == "entity"]
    relations = [t for t in all_types if t.kind == "relation"]
    attributes = [t for t in all_types if t.kind == "attribute"]
    lines.append(f"**Total types:** {len(entities)} entities, {len(relations)} relations, {len(attributes)} attributes")
    lines.append("")

    # Core model diagram (same as regular)
    lines.append("## Core Model")
    lines.append("")
    lines.append("The five primary ICE (Information Content Entity) subtypes form the backbone:")
    lines.append("")
    lines.append("```mermaid")
    lines.append("classDiagram")
    lines.append("    direction LR")
    lines.append("    class information_content_entity {")
    lines.append("        +id @key")
    lines.append("        +name")
    lines.append("        +description")
    lines.append("        +content")
    lines.append("        +created-at")
    lines.append("    }")
    lines.append("    <<abstract>> information_content_entity")
    lines.append("    information_content_entity <|-- collection")
    lines.append("    information_content_entity <|-- research_item")
    lines.append("    information_content_entity <|-- artifact")
    lines.append("    information_content_entity <|-- fragment")
    lines.append("    information_content_entity <|-- note_t")
    lines.append("    information_content_entity <|-- user_question")
    lines.append("    information_content_entity <|-- information_resource")
    lines.append("")
    lines.append("    class collection {")
    lines.append("        +logical-query")
    lines.append("        +is-extensional")
    lines.append("    }")
    lines.append("    class research_item {")
    lines.append("        +abstract-text")
    lines.append("        +publication-date")
    lines.append("    }")
    lines.append("    class artifact")
    lines.append("    class fragment {")
    lines.append("        +offset")
    lines.append("        +length")
    lines.append("    }")
    lines.append("    class note_t {")
    lines.append("        +confidence")
    lines.append("    }")
    lines.append("    class user_question")
    lines.append("    class information_resource")
    lines.append("```")
    lines.append("")

    # Namespace table with wiki links
    lines.append("## Namespaces")
    lines.append("")
    lines.append("| Namespace | Description | Entities | Relations | Attributes |")
    lines.append("|-----------|-------------|----------|-----------|------------|")
    for ns, meta in NAMESPACE_META.items():
        ns_ents = len([t for t in all_types if t.defined_in == ns and t.kind == "entity"])
        ns_rels = len([t for t in all_types if t.defined_in == ns and t.kind == "relation"])
        ns_attrs = len([t for t in all_types if t.defined_in == ns and t.kind == "attribute"])
        wiki_name = WIKI_PAGE_NAMES[ns]
        lines.append(f"| [[{wiki_name}]] | {meta['description'][:70]}... | {ns_ents} | {ns_rels} | {ns_attrs} |")
    lines.append("")

    # Agent subsystem diagram
    lines.append("## Agent & Classification Subsystem")
    lines.append("")
    lines.append("```mermaid")
    lines.append("classDiagram")
    lines.append("    direction LR")
    lines.append("    class agent {")
    lines.append("        +id @key")
    lines.append("        +name")
    lines.append("        +agent-type")
    lines.append("        +model-name")
    lines.append("    }")
    lines.append("    agent <|-- author")
    lines.append("    class author")
    lines.append("    class organization {")
    lines.append("        +id @key")
    lines.append("        +name")
    lines.append("    }")
    lines.append("    class vocabulary {")
    lines.append("        +id @key")
    lines.append("        +name")
    lines.append("    }")
    lines.append("    class vocabulary_type {")
    lines.append("        +schema-org-uri")
    lines.append("        +wikidata-qid")
    lines.append("    }")
    lines.append("    class vocabulary_property {")
    lines.append("        +schema-org-uri")
    lines.append("    }")
    lines.append("    class tag {")
    lines.append("        +id @key")
    lines.append("        +name")
    lines.append("    }")
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


# =============================================================================
# Main
# =============================================================================

def _parse_model(schema_dir: Path) -> SchemaModel:
    """Parse all TQL files and return the merged model."""
    model = SchemaModel()

    core_file = schema_dir / "alhazen_notebook.tql"
    if core_file.exists():
        print(f"Parsing {core_file.name}...")
        parse_tql_file(core_file, model)

    ns_dir = schema_dir / "namespaces"
    if ns_dir.exists():
        for tql_file in sorted(ns_dir.glob("*.tql")):
            print(f"Parsing {tql_file.name}...")
            parse_tql_file(tql_file, model)

    entities = [t for t in model.types.values() if t.kind == "entity"]
    relations = [t for t in model.types.values() if t.kind == "relation"]
    attributes = [t for t in model.types.values() if t.kind == "attribute"]
    print(f"\nParsed: {len(entities)} entities, {len(relations)} relations, {len(attributes)} attributes")

    return model


def main():
    parser = argparse.ArgumentParser(
        description="Generate schema documentation from TypeQL files"
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).parent / "docs"),
        help="Output directory for generated docs (default: ./docs)",
    )
    parser.add_argument(
        "--schema-dir",
        default=str(Path(__file__).parent),
        help="Directory containing .tql files (default: same as script)",
    )
    parser.add_argument(
        "--wiki",
        metavar="WIKI_DIR",
        help="Also generate wiki-compatible pages in the given directory",
    )
    args = parser.parse_args()

    schema_dir = Path(args.schema_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    model = _parse_model(schema_dir)

    # Load query examples
    query_examples = {}
    examples_file = output_dir / "query_examples.json"
    if examples_file.exists():
        print(f"Loading query examples from {examples_file}...")
        query_examples = json.loads(examples_file.read_text())

    # Generate standard docs
    print("Generating index.md...")
    index_content = generate_index_page(model)
    (output_dir / "index.md").write_text(index_content)

    for ns in NAMESPACE_META:
        filename = f"{ns}.md"
        print(f"Generating {filename}...")
        content = generate_namespace_page(model, ns, query_examples)
        (output_dir / filename).write_text(content)

    print(f"\nDone! Generated docs in {output_dir}/")
    print("Files:")
    for f in sorted(output_dir.glob("*.md")):
        print(f"  {f.name}")

    # Generate wiki pages if requested
    if args.wiki:
        wiki_dir = Path(args.wiki)
        if not wiki_dir.exists():
            print(f"\nError: Wiki directory not found: {wiki_dir}")
            return

        print(f"\nGenerating wiki pages in {wiki_dir}/...")

        # Load query examples from the docs dir (canonical location)
        if not query_examples and examples_file.exists():
            query_examples = json.loads(examples_file.read_text())

        # Index page
        index_file = wiki_dir / _wiki_filename(WIKI_INDEX_NAME)
        print(f"  {index_file.name}")
        index_file.write_text(generate_index_page_wiki(model))

        # Namespace pages (same content, wiki-compatible filenames)
        for ns in NAMESPACE_META:
            wiki_name = WIKI_PAGE_NAMES[ns]
            wiki_file = wiki_dir / _wiki_filename(wiki_name)
            print(f"  {wiki_file.name}")
            content = generate_namespace_page(model, ns, query_examples)
            wiki_file.write_text(content)

        print(f"\nWiki pages generated! Push with:")
        print(f"  cd {wiki_dir} && git add . && git commit -m 'Update schema docs' && git push")


if __name__ == "__main__":
    main()
