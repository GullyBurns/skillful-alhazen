#!/usr/bin/env python3
"""
Compile schema_map from skill.yaml files into skills-registry.yaml.

Reads each resolved skill's skill.yaml for schema.namespace and schema.depends_on,
computes a topological load order, and writes the schema_map section into the registry.

Usage:
    uv run python scripts/compile_schema_map.py [--registry skills-registry.yaml]
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

import yaml


def find_skill_yaml(skill_dir: Path) -> dict | None:
    """Read skill.yaml from a skill directory."""
    for name in ["skill.yaml", "skill.yml"]:
        path = skill_dir / name
        if path.exists():
            return yaml.safe_load(path.read_text()) or {}
    return None


def topological_sort(skills: dict[str, dict]) -> list[str]:
    """
    Topological sort of skill names by depends_on.
    Returns ordered list. Raises ValueError on cycles.
    """
    # Build adjacency: skill -> set of skills it depends on
    deps = {}
    for name, info in skills.items():
        dep_names = info.get("depends_on", []) or []
        # Map dependency skill names to actual registered skill names
        deps[name] = set(d for d in dep_names if d in skills)

    # Kahn's algorithm
    in_degree = defaultdict(int)
    for name in skills:
        in_degree.setdefault(name, 0)
    for name, dep_set in deps.items():
        for d in dep_set:
            in_degree[name] += 1  # name depends on d

    queue = [n for n in skills if in_degree[n] == 0]
    queue.sort()  # deterministic order for skills with no deps
    result = []

    while queue:
        node = queue.pop(0)
        result.append(node)
        # Find skills that depend on this node
        for name, dep_set in deps.items():
            if node in dep_set:
                in_degree[name] -= 1
                if in_degree[name] == 0:
                    queue.append(name)
                    queue.sort()

    if len(result) != len(skills):
        missing = set(skills.keys()) - set(result)
        raise ValueError(f"Cycle detected involving: {missing}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Compile schema_map into skills-registry.yaml")
    parser.add_argument("--registry", default="skills-registry.yaml", help="Path to skills-registry.yaml")
    args = parser.parse_args()

    registry_path = Path(args.registry)
    if not registry_path.exists():
        print(f"Registry not found: {registry_path}", file=sys.stderr)
        sys.exit(1)

    registry = yaml.safe_load(registry_path.read_text()) or {}
    skills_list = registry.get("skills", [])

    local_skills = Path("local_skills")
    schema_skills = {}  # name -> {namespace, depends_on, schema_path}

    for skill_entry in skills_list:
        name = skill_entry["name"]
        skill_dir = local_skills / name

        # Resolve symlinks to get actual path
        if skill_dir.is_symlink():
            skill_dir = skill_dir.resolve()

        if not skill_dir.exists():
            continue

        # Check for schema.tql
        schema_tql = None
        for candidate in [skill_dir / "schema.tql", skill_dir / f"{name}.tql"]:
            if candidate.exists():
                schema_tql = candidate
                break
        if not schema_tql:
            continue

        # Read skill.yaml
        skill_yaml = find_skill_yaml(skill_dir)
        if not skill_yaml:
            print(f"  Warning: {name} has schema.tql but no skill.yaml", file=sys.stderr)
            continue

        schema_section = skill_yaml.get("schema", {})
        if isinstance(schema_section, str):
            # Old format: schema: schema.tql (not the new namespace section)
            continue

        namespace = schema_section.get("namespace")
        depends_on = schema_section.get("depends_on", []) or []

        schema_skills[name] = {
            "namespace": namespace,
            "depends_on": depends_on,
            "schema_path": str(schema_tql.relative_to(Path.cwd())) if schema_tql.is_relative_to(Path.cwd()) else str(schema_tql),
        }

    if not schema_skills:
        print("No skills with schema.namespace declarations found.", file=sys.stderr)
        sys.exit(0)

    # Topological sort
    try:
        load_order = topological_sort(schema_skills)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Build schema_map
    schema_map = {
        "load_order": load_order,
        "namespaces": {},
    }
    for name in load_order:
        info = schema_skills[name]
        if info["namespace"]:
            schema_map["namespaces"][info["namespace"]] = {
                "skill": name,
                "schema": info["schema_path"],
                "depends_on": info["depends_on"],
            }

    # Write back to registry
    registry["schema_map"] = schema_map
    registry_path.write_text(yaml.dump(registry, default_flow_style=False, sort_keys=False))

    # Print summary
    print(f"Schema map compiled: {len(load_order)} skills in load order:")
    for i, name in enumerate(load_order, 1):
        info = schema_skills[name]
        ns = info["namespace"] or "(core extensions)"
        deps = info["depends_on"]
        dep_str = f" (after: {', '.join(deps)})" if deps else ""
        print(f"  {i}. {name} → {ns}{dep_str}")


if __name__ == "__main__":
    main()
