"""
TypeQL schema diff and migration rule generator for TypeDB 3.x.

Compares two .tql schema files and reports what changed. Optionally generates
production-ready YAML migration rules compatible with schema_mapper.py.

Usage:
    uv run python src/skillful_alhazen/utils/schema_diff.py diff \
        --old old_schema.tql --new new_schema.tql

    uv run python src/skillful_alhazen/utils/schema_diff.py diff \
        --old old_schema.tql --new new_schema.tql \
        --generate-rules --rules-dir ./rules --intent intent.yaml
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Schema representation
# ---------------------------------------------------------------------------


@dataclass
class SchemaType:
    """Parsed representation of a single TypeQL type definition."""

    kind: str  # "entity", "relation", "attribute"
    name: str
    parent: str | None = None  # sub X
    abstract: bool = False
    owns: list[str] = field(default_factory=list)  # attribute names
    plays: list[str] = field(default_factory=list)  # "relation:role" strings
    relates: list[str] = field(default_factory=list)  # role names (for relations)
    value_type: str | None = None  # for attributes: string, integer, datetime, etc.
    annotations: dict[str, list[str]] = field(
        default_factory=dict
    )  # attr_name -> [@key, etc.]


@dataclass
class SchemaDiff:
    """Result of comparing two parsed schemas."""

    added_types: list[str] = field(default_factory=list)
    removed_types: list[str] = field(default_factory=list)
    hierarchy_changes: list[dict] = field(default_factory=list)
    added_owns: dict[str, list[str]] = field(default_factory=dict)
    removed_owns: dict[str, list[str]] = field(default_factory=dict)
    added_plays: dict[str, list[str]] = field(default_factory=dict)
    removed_plays: dict[str, list[str]] = field(default_factory=dict)
    added_relates: dict[str, list[str]] = field(default_factory=dict)
    removed_relates: dict[str, list[str]] = field(default_factory=dict)
    value_type_changes: list[dict] = field(default_factory=list)
    abstract_changes: list[dict] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(
            self.added_types
            or self.removed_types
            or self.hierarchy_changes
            or self.added_owns
            or self.removed_owns
            or self.added_plays
            or self.removed_plays
            or self.added_relates
            or self.removed_relates
            or self.value_type_changes
            or self.abstract_changes
        )

    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dict, omitting empty fields."""
        result: dict[str, Any] = {}
        for fld in [
            "added_types",
            "removed_types",
            "hierarchy_changes",
            "added_owns",
            "removed_owns",
            "added_plays",
            "removed_plays",
            "added_relates",
            "removed_relates",
            "value_type_changes",
            "abstract_changes",
        ]:
            val = getattr(self, fld)
            if val:
                result[fld] = val
        return result


# ---------------------------------------------------------------------------
# TypeQL parser
# ---------------------------------------------------------------------------

# Matches the start of a type definition block
_BLOCK_START_RE = re.compile(r"^(entity|relation|attribute)\s+")


def _strip_comments(line: str) -> str:
    """Remove inline comments from a line, respecting quoted strings."""
    in_quote = False
    for i, ch in enumerate(line):
        if ch == '"':
            in_quote = not in_quote
        elif ch == "#" and not in_quote:
            return line[:i].rstrip()
    return line


def _normalize_block(block: str) -> str:
    """Normalize whitespace in a definition block to a single line."""
    # Join lines, collapse whitespace
    return re.sub(r"\s+", " ", block).strip()


def _parse_owns_clause(clause: str) -> tuple[str, list[str]]:
    """Parse 'owns attr-name @key' into (attr_name, [annotations])."""
    parts = clause.split()
    attr_name = parts[0]
    annotations = [p for p in parts[1:] if p.startswith("@")]
    return attr_name, annotations


def _parse_block(block: str) -> SchemaType | None:
    """Parse a single normalized definition block into a SchemaType."""
    block = block.rstrip(";").strip()
    if not block:
        return None

    # Determine kind
    match = _BLOCK_START_RE.match(block)
    if not match:
        return None

    kind = match.group(1)
    rest = block[match.end() :].strip()

    # Split the rest by commas at the top level (not inside parens)
    clauses = _split_clauses(rest)
    if not clauses:
        return None

    # First clause is the name, possibly with @abstract and/or sub
    name_clause = clauses[0].strip()
    remaining_clauses = clauses[1:]

    # Parse the name clause
    name, abstract, parent, value_type = _parse_name_clause(name_clause, kind)

    schema_type = SchemaType(
        kind=kind,
        name=name,
        parent=parent,
        abstract=abstract,
        value_type=value_type,
    )

    # Parse remaining clauses
    for clause in remaining_clauses:
        clause = clause.strip()
        if not clause:
            continue

        if clause.startswith("sub "):
            # sub parent (sometimes appears as a separate clause)
            schema_type.parent = clause[4:].strip()
        elif clause.startswith("owns "):
            attr_name, annotations = _parse_owns_clause(clause[5:].strip())
            schema_type.owns.append(attr_name)
            if annotations:
                schema_type.annotations[attr_name] = annotations
        elif clause.startswith("plays "):
            schema_type.plays.append(clause[6:].strip())
        elif clause.startswith("relates "):
            schema_type.relates.append(clause[8:].strip())
        elif clause.startswith("value "):
            schema_type.value_type = clause[6:].strip()
        elif clause.startswith("@abstract"):
            schema_type.abstract = True

    return schema_type


def _split_clauses(text: str) -> list[str]:
    """Split comma-separated clauses, not splitting inside parentheses."""
    clauses: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in text:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            clauses.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    final = "".join(current).strip()
    if final:
        clauses.append(final)
    return clauses


def _parse_name_clause(
    clause: str, kind: str
) -> tuple[str, bool, str | None, str | None]:
    """Parse the first clause of a definition.

    Returns (name, abstract, parent, value_type).

    Examples:
        "person sub agent" -> ("person", False, "agent", None)
        "identifiable-entity @abstract" -> ("identifiable-entity", True, None, None)
        "id" -> ("id", False, None, None)  (attribute, value type in later clause)
    """
    parts = clause.split()
    name = parts[0]
    abstract = False
    parent = None
    value_type = None

    i = 1
    while i < len(parts):
        token = parts[i]
        if token == "@abstract":
            abstract = True
        elif token == "sub":
            if i + 1 < len(parts):
                parent = parts[i + 1]
                i += 1
        elif token == "value":
            if i + 1 < len(parts):
                value_type = parts[i + 1]
                i += 1
        i += 1

    return name, abstract, parent, value_type


def parse_tql(path: str) -> dict[str, SchemaType]:
    """Parse a .tql file into a dict of name -> SchemaType.

    Handles multi-line definitions (comma-separated clauses, semicolon
    terminator), comments, and the define keyword.
    """
    filepath = Path(path)
    if not filepath.exists():
        raise FileNotFoundError(f"Schema file not found: {filepath}")

    text = filepath.read_text(encoding="utf-8")
    lines = text.split("\n")

    # Strip comments and blank lines, skip 'define' keyword
    cleaned_lines: list[str] = []
    for line in lines:
        stripped = _strip_comments(line).strip()
        if not stripped or stripped.lower() == "define":
            continue
        cleaned_lines.append(stripped)

    # Rejoin and split on semicolons to get definition blocks
    full_text = " ".join(cleaned_lines)
    blocks = full_text.split(";")

    schema: dict[str, SchemaType] = {}
    for block in blocks:
        normalized = _normalize_block(block)
        if not normalized:
            continue
        parsed = _parse_block(normalized)
        if parsed:
            schema[parsed.name] = parsed

    return schema


# ---------------------------------------------------------------------------
# Schema diff
# ---------------------------------------------------------------------------


def diff_schemas(
    old: dict[str, SchemaType], new: dict[str, SchemaType]
) -> SchemaDiff:
    """Compare two parsed schemas and return the differences."""
    diff = SchemaDiff()

    old_names = set(old.keys())
    new_names = set(new.keys())

    # Added / removed types
    diff.added_types = sorted(new_names - old_names)
    diff.removed_types = sorted(old_names - new_names)

    # Compare types that exist in both
    common = old_names & new_names
    for name in sorted(common):
        old_t = old[name]
        new_t = new[name]

        # Hierarchy changes
        if old_t.parent != new_t.parent:
            diff.hierarchy_changes.append(
                {
                    "type": name,
                    "old_parent": old_t.parent,
                    "new_parent": new_t.parent,
                }
            )

        # Abstract changes
        if old_t.abstract != new_t.abstract:
            diff.abstract_changes.append(
                {
                    "type": name,
                    "old_abstract": old_t.abstract,
                    "new_abstract": new_t.abstract,
                }
            )

        # Value type changes (attributes only)
        if old_t.value_type != new_t.value_type and (
            old_t.kind == "attribute" or new_t.kind == "attribute"
        ):
            diff.value_type_changes.append(
                {
                    "type": name,
                    "old_value_type": old_t.value_type,
                    "new_value_type": new_t.value_type,
                }
            )

        # Owns diff
        old_owns = set(old_t.owns)
        new_owns = set(new_t.owns)
        added = sorted(new_owns - old_owns)
        removed = sorted(old_owns - new_owns)
        if added:
            diff.added_owns[name] = added
        if removed:
            diff.removed_owns[name] = removed

        # Plays diff
        old_plays = set(old_t.plays)
        new_plays = set(new_t.plays)
        added_p = sorted(new_plays - old_plays)
        removed_p = sorted(old_plays - new_plays)
        if added_p:
            diff.added_plays[name] = added_p
        if removed_p:
            diff.removed_plays[name] = removed_p

        # Relates diff
        old_relates = set(old_t.relates)
        new_relates = set(new_t.relates)
        added_r = sorted(new_relates - old_relates)
        removed_r = sorted(old_relates - new_relates)
        if added_r:
            diff.added_relates[name] = added_r
        if removed_r:
            diff.removed_relates[name] = removed_r

    return diff


# ---------------------------------------------------------------------------
# Migration rule generator
# ---------------------------------------------------------------------------


def _load_intent(path: str | None) -> dict:
    """Load an optional migration intent YAML file."""
    if not path:
        return {}
    filepath = Path(path)
    if not filepath.exists():
        return {}
    with open(filepath) as fh:
        data = yaml.safe_load(fh) or {}
    return data


def _build_rename_map(intent: dict) -> dict[str, str]:
    """Build old->new attribute name mapping from intent renames."""
    renames: dict[str, str] = {}
    for entry in intent.get("renames", []):
        renames[entry["old"]] = entry["new"]
    return renames


def _get_all_owned_attrs(
    schema: dict[str, SchemaType], type_name: str
) -> list[str]:
    """Get all attributes owned by a type, including inherited ones.

    Walks up the inheritance chain collecting owns clauses.
    """
    attrs: list[str] = []
    visited: set[str] = set()
    current = type_name

    while current and current not in visited:
        visited.add(current)
        if current in schema:
            t = schema[current]
            attrs.extend(t.owns)
            current = t.parent
        else:
            break

    return attrs


def _build_fetch_clause(attrs: list[str], var: str = "$x") -> str:
    """Build a TypeQL fetch clause for a list of attributes.

    Example: fetch { "id": $x.id, "name": $x.name };
    """
    if not attrs:
        return 'fetch { "id": ' + var + ".id };"
    parts = [f'"{a}": {var}.{a}' for a in attrs]
    return "fetch { " + ", ".join(parts) + " };"


def _build_insert_clause(
    type_name: str,
    attrs: list[str],
    rename_map: dict[str, str] | None = None,
    var: str = "$x",
) -> str:
    """Build a TypeQL insert clause for a type with attributes.

    Uses $variable placeholders that schema_mapper.py will substitute.
    Applies rename_map: source attr name -> target attr name.
    """
    rename_map = rename_map or {}
    parts = [f"{var} isa {type_name}"]
    for attr in attrs:
        target_attr = rename_map.get(attr, attr)
        parts.append(f"has {target_attr} ${attr}")
    return "insert " + ", ".join(parts) + ";"


def _generate_entity_rule(
    type_name: str,
    old_schema: dict[str, SchemaType],
    new_schema: dict[str, SchemaType],
    rename_map: dict[str, str],
    diff: SchemaDiff,
    rule_index: int,
) -> dict:
    """Generate a migration rule for a single entity type."""
    old_type = old_schema.get(type_name)
    new_type = new_schema.get(type_name)

    # Determine source attributes (what we read from old)
    if old_type:
        source_attrs = _get_all_owned_attrs(old_schema, type_name)
        source_type_name = type_name
    else:
        return {}

    # Determine target type name (same unless renamed -- not supported yet)
    target_type_name = type_name

    # Determine target attributes
    if new_type:
        target_attrs = _get_all_owned_attrs(new_schema, type_name)
    else:
        # Type removed -- no rule needed
        return {}

    # Always include id in the fetch
    if "id" not in source_attrs:
        source_attrs = ["id"] + source_attrs
    # Deduplicate while preserving order
    source_attrs = list(dict.fromkeys(source_attrs))

    # Build source match
    source_match = (
        f"match $x isa {source_type_name};\n"
        + _build_fetch_clause(source_attrs)
    )

    # Build target insert with renames applied
    # Use source attrs as the variable names, but map to target attr names
    insert_attrs = []
    for attr in source_attrs:
        target_attr = rename_map.get(attr, attr)
        # Only include if the target type actually owns it (or inherits it)
        if target_attr in target_attrs or target_attr == "id":
            insert_attrs.append(attr)

    target_insert = _build_insert_clause(
        target_type_name, insert_attrs, rename_map
    )

    # Determine description
    changes: list[str] = []
    for hc in diff.hierarchy_changes:
        if hc["type"] == type_name:
            changes.append(
                f"hierarchy: {hc['old_parent']} -> {hc['new_parent']}"
            )
    if type_name in diff.added_owns:
        changes.append(f"added owns: {diff.added_owns[type_name]}")
    if type_name in diff.removed_owns:
        changes.append(f"removed owns: {diff.removed_owns[type_name]}")
    if not changes:
        changes.append("identity migration (unchanged)")

    description = f"Migrate {type_name}: {'; '.join(changes)}"

    return {
        "name": f"migrate_{type_name.replace('-', '_')}",
        "description": description,
        "depends_on": [],
        "idempotent": True,
        "source_match": source_match,
        "target_insert": target_insert,
        "skolem_keys": ["$id"],
    }


def _generate_relation_rule(
    rel_name: str,
    old_schema: dict[str, SchemaType],
    new_schema: dict[str, SchemaType],
    diff: SchemaDiff,
) -> dict:
    """Generate a migration rule for a relation type.

    Relations are matched by their role players and re-inserted.
    """
    old_rel = old_schema.get(rel_name)
    new_rel = new_schema.get(rel_name)

    if not old_rel or not new_rel:
        return {}

    # Build role player match
    role_vars: list[str] = []
    match_parts: list[str] = []
    for role in old_rel.relates:
        var = f"${role.replace('-', '_')}"
        role_vars.append(f"{role}: {var}")
        # Match role player by id so we can reconnect after migration
        match_parts.append(f"{var} has id ${role.replace('-', '_')}_id")

    # Owned attributes on the relation
    rel_attrs = old_rel.owns
    attr_fetch_parts = []
    for attr in rel_attrs:
        attr_fetch_parts.append(f'"{attr}": $rel.{attr}')
    for role in old_rel.relates:
        var_id = f"{role.replace('-', '_')}_id"
        attr_fetch_parts.append(
            f'"{var_id}": ${role.replace("-", "_")}.id'
        )

    # Source match
    role_clause = ", ".join(role_vars)
    source_lines = [
        f"match ({role_clause}) isa {rel_name};",
    ]
    for mp in match_parts:
        source_lines.append(f"{mp};")

    # Build fetch
    if attr_fetch_parts:
        fetch_line = "fetch { " + ", ".join(attr_fetch_parts) + " };"
    else:
        fetch_line = (
            "fetch { "
            + ", ".join(
                f'"{role.replace("-", "_")}_id": ${role.replace("-", "_")}.id'
                for role in old_rel.relates
            )
            + " };"
        )

    source_match = "\n".join(source_lines) + "\n" + fetch_line

    # Target insert: match role players by id, then insert relation
    insert_match_parts = []
    insert_role_vars = []
    for role in new_rel.relates:
        var = f"${role.replace('-', '_')}"
        var_id = f"${role.replace('-', '_')}_id"
        insert_match_parts.append(
            f"match {var} has id {var_id};"
        )
        insert_role_vars.append(f"{role}: {var}")

    insert_role_clause = ", ".join(insert_role_vars)
    insert_attr_parts = []
    for attr in rel_attrs:
        target_attr = attr
        if target_attr in [a for a in new_rel.owns]:
            insert_attr_parts.append(f"has {target_attr} ${attr}")

    insert_line = f"insert ({insert_role_clause}) isa {rel_name}"
    if insert_attr_parts:
        insert_line += ", " + ", ".join(insert_attr_parts)
    insert_line += ";"

    target_insert = "\n".join(insert_match_parts) + "\n" + insert_line

    # Determine entity dependencies: rules for role-player types should run first
    depends: list[str] = []
    for role in old_rel.relates:
        # Find which entity type plays this role
        for t_name, t_def in old_schema.items():
            if t_def.kind == "entity":
                for play in t_def.plays:
                    if play == f"{rel_name}:{role}":
                        dep_name = f"migrate_{t_name.replace('-', '_')}"
                        if dep_name not in depends:
                            depends.append(dep_name)

    # Skolem keys: use the role player ids
    skolem_keys = [
        f"${role.replace('-', '_')}_id" for role in old_rel.relates
    ]

    return {
        "name": f"migrate_{rel_name.replace('-', '_')}",
        "description": f"Migrate relation {rel_name}",
        "depends_on": sorted(depends),
        "idempotent": True,
        "source_match": source_match,
        "target_insert": target_insert,
        "skolem_keys": skolem_keys,
    }


def generate_rules(
    diff: SchemaDiff,
    old_schema: dict[str, SchemaType],
    new_schema: dict[str, SchemaType],
    intent: dict | None = None,
    output_dir: str = "rules",
) -> list[dict]:
    """Generate YAML migration rules from a schema diff.

    Rules are generated for:
    - Entity types that exist in both old and new schemas (migration rules)
    - Relation types that exist in both schemas (relation migration rules)
    - Types with hierarchy changes get appropriate descriptions
    - Unchanged types get identity rules (read and re-insert as-is)

    Uses the intent file for attribute renames.

    Returns the list of rule dicts and writes them to output_dir.
    """
    intent = intent or {}
    rename_map = _build_rename_map(intent)

    rules: list[dict] = []
    rule_index = 0

    # Generate entity rules (for types in both schemas)
    old_names = set(old_schema.keys())
    new_names = set(new_schema.keys())
    common = old_names & new_names

    # Entity rules first
    for name in sorted(common):
        t = old_schema[name]
        if t.kind == "entity" and not t.abstract:
            rule = _generate_entity_rule(
                name, old_schema, new_schema, rename_map, diff, rule_index
            )
            if rule:
                rules.append(rule)
                rule_index += 1

    # Relation rules (depend on entity rules)
    for name in sorted(common):
        t = old_schema[name]
        if t.kind == "relation":
            rule = _generate_relation_rule(name, old_schema, new_schema, diff)
            if rule:
                # Filter depends_on to only reference rules we actually generated
                existing_rule_names = {r["name"] for r in rules}
                rule["depends_on"] = [
                    d for d in rule["depends_on"] if d in existing_rule_names
                ]
                rules.append(rule)
                rule_index += 1

    # Write rules to output directory
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    for i, rule in enumerate(rules):
        filename = f"{i:03d}_{rule['name']}.yaml"
        filepath = out_path / filename
        with open(filepath, "w") as fh:
            yaml.dump(rule, fh, default_flow_style=False, sort_keys=False)

    return rules


# ---------------------------------------------------------------------------
# Summary / reporting
# ---------------------------------------------------------------------------


def format_diff_summary(diff: SchemaDiff) -> str:
    """Format a human-readable summary of schema changes."""
    lines: list[str] = []

    if not diff.has_changes:
        return "No schema changes detected."

    if diff.added_types:
        lines.append(f"Added types ({len(diff.added_types)}):")
        for t in diff.added_types:
            lines.append(f"  + {t}")

    if diff.removed_types:
        lines.append(f"Removed types ({len(diff.removed_types)}):")
        for t in diff.removed_types:
            lines.append(f"  - {t}")

    if diff.hierarchy_changes:
        lines.append(f"Hierarchy changes ({len(diff.hierarchy_changes)}):")
        for hc in diff.hierarchy_changes:
            lines.append(
                f"  ~ {hc['type']}: {hc['old_parent']} -> {hc['new_parent']}"
            )

    if diff.abstract_changes:
        lines.append(f"Abstract changes ({len(diff.abstract_changes)}):")
        for ac in diff.abstract_changes:
            old = "abstract" if ac["old_abstract"] else "concrete"
            new = "abstract" if ac["new_abstract"] else "concrete"
            lines.append(f"  ~ {ac['type']}: {old} -> {new}")

    if diff.value_type_changes:
        lines.append(f"Value type changes ({len(diff.value_type_changes)}):")
        for vc in diff.value_type_changes:
            lines.append(
                f"  ~ {vc['type']}: {vc['old_value_type']} -> {vc['new_value_type']}"
            )

    for label, data in [
        ("Added owns", diff.added_owns),
        ("Removed owns", diff.removed_owns),
        ("Added plays", diff.added_plays),
        ("Removed plays", diff.removed_plays),
        ("Added relates", diff.added_relates),
        ("Removed relates", diff.removed_relates),
    ]:
        if data:
            lines.append(f"{label}:")
            for type_name, items in sorted(data.items()):
                lines.append(f"  {type_name}: {', '.join(items)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _log(msg: str, level: str = "INFO") -> None:
    """Print a log message to stderr."""
    print(f"[schema-diff][{level}] {msg}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="TypeQL schema diff and migration rule generator for TypeDB 3.x.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- diff ---
    diff_parser = subparsers.add_parser(
        "diff",
        help="Compare two .tql schema files and report changes",
    )
    diff_parser.add_argument(
        "--old", required=True, help="Path to the old/source .tql schema file"
    )
    diff_parser.add_argument(
        "--new", required=True, help="Path to the new/target .tql schema file"
    )
    diff_parser.add_argument(
        "--generate-rules",
        action="store_true",
        help="Generate YAML migration rules from the diff",
    )
    diff_parser.add_argument(
        "--rules-dir",
        default="rules",
        help="Output directory for generated YAML rules (default: rules/)",
    )
    diff_parser.add_argument(
        "--intent",
        default=None,
        help="Path to migration intent YAML file (renames, etc.)",
    )
    diff_parser.add_argument(
        "--summary",
        action="store_true",
        help="Print human-readable summary to stderr",
    )

    # --- parse ---
    parse_parser = subparsers.add_parser(
        "parse",
        help="Parse a .tql file and output its structure as JSON",
    )
    parse_parser.add_argument(
        "file", help="Path to the .tql schema file to parse"
    )

    args = parser.parse_args()

    try:
        if args.command == "parse":
            schema = parse_tql(args.file)
            # Convert to JSON-serializable format
            output = {}
            for name, st in sorted(schema.items()):
                entry: dict[str, Any] = {"kind": st.kind, "name": st.name}
                if st.parent:
                    entry["parent"] = st.parent
                if st.abstract:
                    entry["abstract"] = True
                if st.owns:
                    entry["owns"] = st.owns
                if st.plays:
                    entry["plays"] = st.plays
                if st.relates:
                    entry["relates"] = st.relates
                if st.value_type:
                    entry["value_type"] = st.value_type
                if st.annotations:
                    entry["annotations"] = st.annotations
                output[name] = entry
            print(json.dumps(output, indent=2))

        elif args.command == "diff":
            old_schema = parse_tql(args.old)
            new_schema = parse_tql(args.new)

            _log(f"Old schema: {len(old_schema)} types from {args.old}")
            _log(f"New schema: {len(new_schema)} types from {args.new}")

            diff = diff_schemas(old_schema, new_schema)

            if args.summary:
                summary = format_diff_summary(diff)
                _log(summary)

            result: dict[str, Any] = {
                "success": True,
                "old_file": args.old,
                "new_file": args.new,
                "old_type_count": len(old_schema),
                "new_type_count": len(new_schema),
                "has_changes": diff.has_changes,
                "diff": diff.to_dict(),
            }

            if args.generate_rules:
                intent = _load_intent(args.intent)
                rules = generate_rules(
                    diff,
                    old_schema,
                    new_schema,
                    intent=intent,
                    output_dir=args.rules_dir,
                )
                result["rules_generated"] = len(rules)
                result["rules_dir"] = args.rules_dir
                _log(f"Generated {len(rules)} migration rules in {args.rules_dir}/")

            print(json.dumps(result, indent=2))

    except Exception as exc:
        error_result = {"success": False, "error": str(exc)}
        _log(str(exc), level="ERROR")
        print(json.dumps(error_result, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
