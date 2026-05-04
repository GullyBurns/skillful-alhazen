import type { EntityTypeInfo } from '@/lib/agentic-memory';

// ---------------------------------------------------------------------------
// Core interfaces
// ---------------------------------------------------------------------------

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  attributes?: Record<string, unknown>;
}

export interface GraphEdge {
  source: string;
  target: string;
  relationType: string;
  sourceRole: string;
  targetRole: string;
}

export interface TreeNode {
  name: string;
  children?: TreeNode[];
  entityCount?: number;
  type?: string; // leaf nodes have the entity type name
}

// ---------------------------------------------------------------------------
// Color palette — 15 distinct, legible colors for graph namespaces
// ---------------------------------------------------------------------------

const PALETTE = [
  '#3b82f6', // blue
  '#ef4444', // red
  '#10b981', // emerald
  '#f59e0b', // amber
  '#8b5cf6', // violet
  '#ec4899', // pink
  '#06b6d4', // cyan
  '#f97316', // orange
  '#14b8a6', // teal
  '#6366f1', // indigo
  '#84cc16', // lime
  '#e11d48', // rose
  '#0ea5e9', // sky
  '#a855f7', // purple
  '#22d3ee', // light cyan
];

// Core types that don't belong to a namespace prefix
const CORE_TYPE_NAMES = new Set([
  'identifiable-entity',
  'domain-thing',
  'information-content-entity',
  'collection',
  'artifact',
  'fragment',
  'note',
  'agent',
  'ai-agent',
  'person',
  'operator-user',
  'author',
  'organization',
  'interaction',
]);

// ---------------------------------------------------------------------------
// Utility: extract namespace from a type name
// ---------------------------------------------------------------------------

function getNamespace(typeName: string): string {
  if (CORE_TYPE_NAMES.has(typeName)) return 'core';
  const idx = typeName.indexOf('-');
  if (idx === -1) return 'core';
  const prefix = typeName.slice(0, idx);
  // Short prefixes like "ai" are likely core
  if (prefix.length <= 2) return 'core';
  return prefix;
}

// ---------------------------------------------------------------------------
// Simple string hash for deterministic palette selection
// ---------------------------------------------------------------------------

function hashString(s: string): number {
  let hash = 0;
  for (let i = 0; i < s.length; i++) {
    hash = (hash * 31 + s.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Groups entity type names by their namespace prefix.
 * Types with no hyphen or recognized core types go under "core".
 */
export function groupByNamespace(labels: string[]): Record<string, string[]> {
  const groups: Record<string, string[]> = {};
  for (const label of labels) {
    const ns = getNamespace(label);
    if (!groups[ns]) groups[ns] = [];
    groups[ns].push(label);
  }
  // Sort each group alphabetically
  for (const ns of Object.keys(groups)) {
    groups[ns].sort();
  }
  return groups;
}

/**
 * Deterministic color for a given type name, based on its namespace.
 */
export function typeToColor(typeName: string): string {
  const ns = getNamespace(typeName);
  const index = hashString(ns) % PALETTE.length;
  return PALETTE[index];
}

/**
 * Converts a flat entity-type map (from describeSchema) into a tree
 * grouped by namespace prefix.
 *
 * Returns an array of top-level TreeNode objects, one per namespace.
 * Each namespace node has children for its entity types.
 * Leaf nodes carry the `type` field and `entityCount` from instance_count.
 */
export function schemaToTree(
  entities: Record<string, EntityTypeInfo>
): TreeNode[] {
  const typeNames = Object.keys(entities);
  const grouped = groupByNamespace(typeNames);

  const namespaceNodes: TreeNode[] = [];

  for (const [ns, types] of Object.entries(grouped)) {
    const children: TreeNode[] = types.map((typeName) => {
      const info = entities[typeName];
      return {
        name: typeName,
        type: typeName,
        entityCount: info?.instance_count ?? 0,
      };
    });

    const totalCount = children.reduce(
      (sum, c) => sum + (c.entityCount ?? 0),
      0
    );

    namespaceNodes.push({
      name: ns,
      children,
      entityCount: totalCount,
    });
  }

  // Sort namespaces: "core" first, then alphabetical
  namespaceNodes.sort((a, b) => {
    if (a.name === 'core') return -1;
    if (b.name === 'core') return 1;
    return a.name.localeCompare(b.name);
  });

  return namespaceNodes;
}
