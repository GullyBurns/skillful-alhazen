'use client';

import { useEffect, useState, useCallback, useMemo } from 'react';
import {
  colors,
  getNamespace,
  getNamespaceColor,
  getNamespaceColorRgba,
  stripPrefix,
} from './tokens';
import TypeHierarchyDiagram from './type-hierarchy-diagram';
import TypeRelationsDiagram from './type-relations-diagram';

interface TypeBrowserProps {
  typeName: string;
  onSelectEntity: (id: string) => void;
  onSelectType?: (typeName: string) => void;
}

interface InstanceRow {
  id: string;
  name: string;
  [key: string]: string | undefined;
}

interface SchemaTypeInfo {
  name: string;
  subtypes?: string[];
  instance_count?: number;
  owns?: string[];
}

// Extra columns to fetch and display for specific types
// Each entry: { attr: attribute name to fetch, label: column header }
// Special: { relation: ..., role: ..., targetRole: ..., label: ... } fetches a related entity name
interface AttrColumn {
  kind: 'attr';
  attr: string;
  label: string;
}

interface RelColumn {
  kind: 'rel';
  relation: string;
  entityRole: string;
  targetRole: string;
  label: string;
}

type ExtraColumn = AttrColumn | RelColumn;

// Map of type name patterns to extra columns
const TYPE_EXTRA_COLUMNS: Record<string, ExtraColumn[]> = {
  'jhunt-position': [
    { kind: 'rel', relation: 'jhunt-position-at-company', entityRole: 'position', targetRole: 'employer', label: 'Company' },
    { kind: 'attr', attr: 'jhunt-opportunity-status', label: 'Status' },
    { kind: 'attr', attr: 'alh-location', label: 'Location' },
  ],
  'jhunt-opportunity': [
    { kind: 'rel', relation: 'jhunt-opportunity-at-organization', entityRole: 'opportunity', targetRole: 'organization', label: 'Organization' },
    { kind: 'attr', attr: 'jhunt-opportunity-status', label: 'Status' },
  ],
  'jhunt-engagement': [
    { kind: 'rel', relation: 'jhunt-opportunity-at-organization', entityRole: 'opportunity', targetRole: 'organization', label: 'Organization' },
    { kind: 'attr', attr: 'jhunt-opportunity-status', label: 'Status' },
  ],
  'jhunt-venture': [
    { kind: 'rel', relation: 'jhunt-opportunity-at-organization', entityRole: 'opportunity', targetRole: 'organization', label: 'Organization' },
    { kind: 'attr', attr: 'jhunt-opportunity-status', label: 'Status' },
  ],
  'jhunt-lead': [
    { kind: 'rel', relation: 'jhunt-opportunity-at-organization', entityRole: 'opportunity', targetRole: 'organization', label: 'Organization' },
    { kind: 'attr', attr: 'jhunt-opportunity-status', label: 'Status' },
  ],
  'trec-system': [
    { kind: 'attr', attr: 'description', label: 'Description' },
  ],
  'trec-investigation': [
    { kind: 'attr', attr: 'description', label: 'Description' },
  ],
  'trec-artifact': [
    { kind: 'attr', attr: 'source-uri', label: 'Source' },
  ],
  'alh-person': [
    { kind: 'attr', attr: 'description', label: 'Description' },
  ],
  'alh-organization': [
    { kind: 'attr', attr: 'description', label: 'Description' },
    { kind: 'attr', attr: 'alh-location', label: 'Location' },
  ],
  'alh-collection': [
    { kind: 'attr', attr: 'description', label: 'Description' },
  ],
  'alh-tag': [
    { kind: 'attr', attr: 'description', label: 'Description' },
  ],
};

// For note subtypes, show a description snippet
const NOTE_TYPES = new Set([
  'alh-note', 'jhunt-application-note', 'jhunt-fit-analysis-note',
  'jhunt-interaction-note', 'jhunt-interview-note', 'jhunt-research-note',
  'jhunt-skill-gap-note', 'jhunt-strategy-note', 'jhunt-opp-summary-note',
  'trec-note', 'trec-analysis', 'nbmem-memory-claim-note',
]);

function getExtraColumns(typeName: string): ExtraColumn[] {
  // Direct match
  if (TYPE_EXTRA_COLUMNS[typeName]) return TYPE_EXTRA_COLUMNS[typeName];
  // Note types get a content snippet
  if (NOTE_TYPES.has(typeName)) {
    return [{ kind: 'attr', attr: 'content', label: 'Content' }];
  }
  // Default: try description
  return [{ kind: 'attr', attr: 'description', label: 'Description' }];
}

type SortKey = string;
type SortDir = 'asc' | 'desc';

export default function TypeBrowser({ typeName, onSelectEntity, onSelectType }: TypeBrowserProps) {
  const [instances, setInstances] = useState<InstanceRow[]>([]);
  const [schemaInfo, setSchemaInfo] = useState<SchemaTypeInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [sortKey, setSortKey] = useState<SortKey>('name');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [visibleCount, setVisibleCount] = useState(50);
  const [hoveredRow, setHoveredRow] = useState<string | null>(null);
  const [fullSchema, setFullSchema] = useState<{ entities: Record<string, { parent?: string; subtypes?: string[]; instance_count?: number; owns?: string[] }> } | null>(null);
  const [showDiagram, setShowDiagram] = useState(false);
  const [showOutgoing, setShowOutgoing] = useState(false);
  const [showIncoming, setShowIncoming] = useState(false);

  const extraColumns = useMemo(() => getExtraColumns(typeName), [typeName]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setVisibleCount(50);

    try {
      // Fetch schema info
      const schemaRes = await fetch('/api/agentic-memory/schema?full=true');
      let owns: string[] = [];
      let subtypesList: string[] = [];
      let schemaData: Record<string, unknown> = {};
      if (schemaRes.ok) {
        schemaData = await schemaRes.json();
        setFullSchema(schemaData as typeof fullSchema);
        const info = (schemaData as { entities?: Record<string, { subtypes?: string[]; instance_count?: number; owns?: string[] }> }).entities?.[typeName];
        if (info) {
          setSchemaInfo({
            name: typeName,
            subtypes: info.subtypes,
            instance_count: info.instance_count,
            owns: info.owns,
          });
          owns = info.owns ?? [];
          subtypesList = info.subtypes ?? [];
        }
      }

      // Build the main query with extra attribute columns
      const attrCols = extraColumns.filter((c): c is AttrColumn => c.kind === 'attr');
      const relCols = extraColumns.filter((c): c is RelColumn => c.kind === 'rel');

      // Only include attr columns that the type actually owns
      const validAttrCols = attrCols.filter(c => owns.includes(c.attr));

      // Build fetch fields
      const fetchFields = ['"id": $id', '"name": $name'];
      const matchClauses = [`$e isa ${typeName}, has id $id, has name $name`];

      for (const col of validAttrCols) {
        const varName = col.attr.replace(/-/g, '_');
        // Use optional match pattern: fetch directly from entity
        fetchFields.push(`"${col.attr}": $e.${col.attr}`);
      }

      const typeql = `match ${matchClauses.join('; ')}; fetch { ${fetchFields.join(', ')} };`;

      const res = await fetch('/api/agentic-memory/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ typeql, limit: 200 }),
      });

      let rows: InstanceRow[] = [];
      if (res.ok) {
        const data = await res.json();
        const results = data.results ?? [];
        rows = (Array.isArray(results) ? results : []).map(
          (row: Record<string, unknown>) => {
            const r: InstanceRow = {
              id: String(row.id ?? ''),
              name: String(row.name ?? ''),
            };
            for (const col of validAttrCols) {
              const val = row[col.attr];
              r[col.attr] = val != null ? String(val) : undefined;
            }
            return r;
          }
        );
      }

      // Resolve subtypes: for each subtype, query which IDs belong to it
      if (subtypesList.length > 0 && rows.length > 0) {
        // Collect all leaf subtypes (recursively) from schema
        const allEntities = (schemaData as { entities?: Record<string, { subtypes?: string[] }> }).entities ?? {};
        const leafTypes: string[] = [];
        const collectLeaves = (t: string) => {
          const subs = allEntities[t]?.subtypes ?? [];
          if (subs.length === 0) {
            leafTypes.push(t);
          } else {
            for (const s of subs) collectLeaves(s);
          }
        };
        // Also include the base type itself if it could have direct instances
        leafTypes.push(typeName);
        for (const st of subtypesList) collectLeaves(st);

        // Query each leaf type for its IDs
        const typePromises = [...new Set(leafTypes)].map(async (st) => {
          try {
            const r = await fetch('/api/agentic-memory/query', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                typeql: `match $e isa! ${st}, has id $id; fetch { "id": $id };`,
                limit: 500,
              }),
            });
            if (r.ok) {
              const d = await r.json();
              const ids = (d.results ?? []).map((row: Record<string, string>) => row.id);
              return { type: st, ids: ids as string[] };
            }
          } catch { /* skip */ }
          return { type: st, ids: [] as string[] };
        });

        const typeResults = await Promise.all(typePromises);
        const idToType = new Map<string, string>();
        for (const { type: t, ids } of typeResults) {
          for (const id of ids) {
            if (!idToType.has(id)) idToType.set(id, t);
          }
        }
        for (const row of rows) {
          row._type = idToType.get(row.id) ?? typeName;
        }
      } else {
        for (const row of rows) {
          row._type = typeName;
        }
      }

      // Fetch relation columns separately (e.g., company name for positions)
      if (relCols.length > 0 && rows.length > 0) {
        for (const relCol of relCols) {
          try {
            const relTypeql = `match $e isa ${typeName}, has id $eid; (${relCol.entityRole}: $e, ${relCol.targetRole}: $t) isa ${relCol.relation}; $t has name $tname; fetch { "eid": $eid, "tname": $tname };`;
            const relRes = await fetch('/api/agentic-memory/query', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ typeql: relTypeql, limit: 200 }),
            });
            if (relRes.ok) {
              const relData = await relRes.json();
              const relResults = relData.results ?? [];
              // Build lookup map: entity id -> related name
              const lookup = new Map<string, string>();
              for (const r of relResults as Array<Record<string, string>>) {
                if (r.eid && r.tname) lookup.set(r.eid, r.tname);
              }
              // Merge into rows
              for (const row of rows) {
                const val = lookup.get(row.id);
                if (val) row[relCol.label.toLowerCase()] = val;
              }
            }
          } catch {
            // relation data is supplementary
          }
        }
      }

      setInstances(rows);
    } catch (err) {
      console.error('TypeBrowser fetch error:', err);
      setInstances([]);
    } finally {
      setLoading(false);
    }
  }, [typeName, extraColumns]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const sorted = useMemo(() => {
    const copy = [...instances];
    copy.sort((a, b) => {
      const aVal = (a[sortKey] ?? '').toLowerCase();
      const bVal = (b[sortKey] ?? '').toLowerCase();
      const cmp = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return copy;
  }, [instances, sortKey, sortDir]);

  const visible = sorted.slice(0, visibleCount);
  const hasMore = sorted.length > visibleCount;
  const instanceCount = schemaInfo?.instance_count ?? instances.length;
  const subtypes = schemaInfo?.subtypes ?? [];

  const sortIndicator = (key: SortKey) => {
    if (sortKey !== key) return '';
    return sortDir === 'asc' ? ' \u25B2' : ' \u25BC';
  };

  // Build column definitions for display
  const hasSubtypes = (schemaInfo?.subtypes ?? []).length > 0;
  const displayColumns = useMemo(() => {
    const cols: { key: string; label: string; flex: string; isType?: boolean }[] = [
      { key: 'name', label: 'Name', flex: '1.5fr' },
    ];

    // Add type column if there are subtypes
    if (hasSubtypes) {
      cols.push({ key: '_type', label: 'Type', flex: '0.8fr', isType: true });
    }

    for (const ec of extraColumns) {
      if (ec.kind === 'attr') {
        const label = ec.label;
        const key = ec.attr;
        const flex = ec.attr === 'content' || ec.attr === 'description' ? '2fr' : '0.8fr';
        cols.push({ key, label, flex });
      } else {
        const key = ec.label.toLowerCase();
        cols.push({ key, label: ec.label, flex: '0.8fr' });
      }
    }

    return cols;
  }, [extraColumns, hasSubtypes]);

  const gridTemplate = displayColumns.map(c => c.flex).join(' ');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Header area */}
      <div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px' }}>
          <span
            style={{
              fontFamily: 'var(--font-dm-serif), "DM Serif Display", serif',
              fontSize: '22px',
              color: colors.fg,
            }}
          >
            {typeName}
          </span>
          <span
            style={{
              fontFamily: 'var(--font-jetbrains-mono), "JetBrains Mono", monospace',
              fontSize: '10px',
              color: colors.fgFaint,
            }}
          >
            {loading ? '...' : `${instanceCount} instances`}
          </span>
        </div>

        {/* Subtype chips */}
        {subtypes.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '8px' }}>
            {subtypes.map((st) => {
              const ns = getNamespace(st);
              const nsColor = getNamespaceColor(ns);
              return (
                <span
                  key={st}
                  style={{
                    fontFamily: 'var(--font-jetbrains-mono), "JetBrains Mono", monospace',
                    fontSize: '10px',
                    color: nsColor,
                    background: getNamespaceColorRgba(ns, 0.1),
                    border: `1px solid ${getNamespaceColorRgba(ns, 0.25)}`,
                    borderRadius: '3px',
                    padding: '2px 8px',
                  }}
                >
                  {stripPrefix(st)}
                </span>
              );
            })}
          </div>
        )}
      </div>

      {/* Schema Hierarchy + Relations toggles */}
      <div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={() => setShowDiagram((v) => !v)}
            style={{
              background: 'transparent',
              border: `1px solid ${showDiagram ? colors.teal : colors.border}`,
              borderRadius: '3px',
              color: showDiagram ? colors.teal : colors.fgFaint,
              fontFamily: 'var(--font-jetbrains-mono), "JetBrains Mono", monospace',
              fontSize: '10px',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              padding: '4px 12px',
              cursor: 'pointer',
              transition: 'color 0.15s, border-color 0.15s',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span style={{ fontSize: '8px' }}>{showDiagram ? '\u25BC' : '\u25B6'}</span>
            Hierarchy
          </button>

          <button
            onClick={() => setShowOutgoing((v) => !v)}
            style={{
              background: 'transparent',
              border: `1px solid ${showOutgoing ? colors.teal : colors.border}`,
              borderRadius: '3px',
              color: showOutgoing ? colors.teal : colors.fgFaint,
              fontFamily: 'var(--font-jetbrains-mono), "JetBrains Mono", monospace',
              fontSize: '10px',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              padding: '4px 12px',
              cursor: 'pointer',
              transition: 'color 0.15s, border-color 0.15s',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span style={{ fontSize: '8px' }}>{showOutgoing ? '\u25BC' : '\u25B6'}</span>
            Outgoing
          </button>

          <button
            onClick={() => setShowIncoming((v) => !v)}
            style={{
              background: 'transparent',
              border: `1px solid ${showIncoming ? colors.teal : colors.border}`,
              borderRadius: '3px',
              color: showIncoming ? colors.teal : colors.fgFaint,
              fontFamily: 'var(--font-jetbrains-mono), "JetBrains Mono", monospace',
              fontSize: '10px',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              padding: '4px 12px',
              cursor: 'pointer',
              transition: 'color 0.15s, border-color 0.15s',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span style={{ fontSize: '8px' }}>{showIncoming ? '\u25BC' : '\u25B6'}</span>
            Incoming
          </button>
        </div>

        {showDiagram && fullSchema && (
          <div style={{ marginTop: '8px' }}>
            <TypeHierarchyDiagram typeName={typeName} schema={fullSchema} onSelectType={onSelectType} />
          </div>
        )}

        {showOutgoing && fullSchema && (
          <div style={{ marginTop: '8px' }}>
            <TypeRelationsDiagram typeName={typeName} direction="outgoing" schema={fullSchema} onSelectType={onSelectType} />
          </div>
        )}

        {showIncoming && fullSchema && (
          <div style={{ marginTop: '8px' }}>
            <TypeRelationsDiagram typeName={typeName} direction="incoming" schema={fullSchema} onSelectType={onSelectType} />
          </div>
        )}
      </div>

      {/* Instance table */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '32px', color: colors.fgFaint, fontSize: '12px' }}>
          Loading...
        </div>
      ) : instances.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '48px', color: colors.fgFaint, fontSize: '13px' }}>
          No instances of this type
        </div>
      ) : (
        <div
          style={{
            border: `1px solid ${colors.borderDim}`,
            borderRadius: '3px',
            overflow: 'hidden',
          }}
        >
          {/* Table header */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: gridTemplate,
              padding: '6px 12px',
              background: colors.panel,
              fontFamily: 'var(--font-jetbrains-mono), "JetBrains Mono", monospace',
              fontSize: '10px',
              textTransform: 'uppercase',
              color: colors.fgFaint,
              letterSpacing: '0.05em',
              userSelect: 'none',
            }}
          >
            {displayColumns.map((col) => (
              <span
                key={col.key}
                style={{ cursor: 'pointer', padding: '2px 0' }}
                onClick={() => toggleSort(col.key)}
              >
                {col.label}{sortIndicator(col.key)}
              </span>
            ))}
          </div>

          {/* Data rows */}
          {visible.map((row) => {
            const isHovered = hoveredRow === row.id;

            return (
              <div
                key={row.id}
                onClick={() => onSelectEntity(row.id)}
                onMouseEnter={() => setHoveredRow(row.id)}
                onMouseLeave={() => setHoveredRow(null)}
                style={{
                  display: 'grid',
                  gridTemplateColumns: gridTemplate,
                  padding: '7px 12px',
                  fontSize: '12px',
                  borderTop: `1px solid ${colors.borderDim}`,
                  cursor: 'pointer',
                  background: isHovered ? 'rgba(90,173,175,0.06)' : 'transparent',
                  transition: 'background 0.1s ease',
                  alignItems: 'baseline',
                }}
              >
                {displayColumns.map((col, colIdx) => {
                  const val = row[col.key] ?? '';
                  const isName = colIdx === 0;

                  // Type column renders as a namespace-colored badge
                  if (col.isType) {
                    const typeNs = getNamespace(val);
                    const typeColor = getNamespaceColor(typeNs);
                    return (
                      <span
                        key={col.key}
                        style={{
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        <span
                          style={{
                            fontFamily: 'var(--font-jetbrains-mono), "JetBrains Mono", monospace',
                            fontSize: '9.5px',
                            color: typeColor,
                            background: getNamespaceColorRgba(typeNs, 0.1),
                            borderRadius: '2px',
                            padding: '1px 6px',
                          }}
                        >
                          {stripPrefix(val)}
                        </span>
                      </span>
                    );
                  }

                  // Truncate content/description to ~80 chars for table display
                  const displayVal = (col.key === 'content' || col.key === 'description')
                    ? (val.length > 80 ? val.slice(0, 80) + '...' : val).replace(/\n/g, ' ')
                    : val;

                  return (
                    <span
                      key={col.key}
                      style={{
                        color: isName ? colors.fg : colors.fgDim,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        fontFamily: isName ? 'var(--font-dm-sans), "DM Sans", sans-serif' : undefined,
                        ...(col.key === 'status' || col.key === 'location' ? {
                          fontFamily: 'var(--font-jetbrains-mono), "JetBrains Mono", monospace',
                          fontSize: '10px',
                        } : {}),
                      }}
                    >
                      {displayVal}
                    </span>
                  );
                })}
              </div>
            );
          })}

          {/* Load more */}
          {hasMore && (
            <div
              style={{
                textAlign: 'center',
                padding: '10px',
                borderTop: `1px solid ${colors.borderDim}`,
              }}
            >
              <button
                onClick={() => setVisibleCount((c) => c + 50)}
                style={{
                  background: 'transparent',
                  border: `1px solid ${colors.border}`,
                  borderRadius: '3px',
                  color: colors.teal,
                  fontFamily: 'var(--font-jetbrains-mono), "JetBrains Mono", monospace',
                  fontSize: '11px',
                  padding: '4px 16px',
                  cursor: 'pointer',
                }}
              >
                Load more ({sorted.length - visibleCount} remaining)
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
