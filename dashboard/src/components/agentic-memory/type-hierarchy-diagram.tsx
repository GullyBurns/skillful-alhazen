'use client';

import { useMemo } from 'react';
import { colors, getNamespace, getNamespaceColor, getNamespaceColorRgba } from './tokens';

interface EntityTypeInfo {
  parent?: string;
  subtypes?: string[];
  instance_count?: number;
  owns?: string[];
}

interface TypeHierarchyDiagramProps {
  typeName: string;
  schema: {
    entities: Record<string, EntityTypeInfo>;
  };
  onSelectType?: (typeName: string) => void;
}

function getKeyAttributes(owns: string[], namespace: string): string[] {
  const skip = new Set([
    'id', 'name', 'description', 'created-at', 'updated-at',
    'provenance', 'source-uri', 'iri', 'license',
    'valid-from', 'valid-until',
    'content', 'content-hash', 'cache-path', 'format',
    'mime-type', 'file-size', 'token-count',
  ]);

  const nsPrefix = namespace === 'unknown' ? '' : namespace + '-';
  return owns
    .filter(a => !skip.has(a) && (nsPrefix ? a.startsWith(nsPrefix) || a.startsWith('alh-') : false))
    .slice(0, 3);
}

interface TypeNode {
  name: string;
  count: number;
  attrs: string[];
  namespace: string;
  isSelected: boolean;
  isClickable: boolean;
  hasChildren: boolean;
  hasParent: boolean;
}

export default function TypeHierarchyDiagram({ typeName, schema, onSelectType }: TypeHierarchyDiagramProps) {
  const { parent, children } = useMemo(() => {
    const info = schema.entities[typeName];
    if (!info) return { parent: null, children: [] };

    let parentNode: TypeNode | null = null;
    if (info.parent && schema.entities[info.parent]) {
      const pInfo = schema.entities[info.parent];
      const ns = getNamespace(info.parent);
      parentNode = {
        name: info.parent,
        count: pInfo.instance_count ?? 0,
        attrs: getKeyAttributes(pInfo.owns ?? [], ns),
        namespace: ns,
        isSelected: false,
        isClickable: true,
        hasChildren: true,
        hasParent: !!pInfo.parent,
      };
    }

    const childNodes: TypeNode[] = (info.subtypes ?? []).map(st => {
      const cInfo = schema.entities[st];
      const ns = getNamespace(st);
      return {
        name: st,
        count: cInfo?.instance_count ?? 0,
        attrs: getKeyAttributes(cInfo?.owns ?? [], ns),
        namespace: ns,
        isSelected: false,
        isClickable: true,
        hasChildren: (cInfo?.subtypes ?? []).length > 0,
        hasParent: true,
      };
    });

    return { parent: parentNode, children: childNodes };
  }, [typeName, schema]);

  const selectedInfo = schema.entities[typeName];
  const selectedNs = getNamespace(typeName);
  const selectedNode: TypeNode = {
    name: typeName,
    count: selectedInfo?.instance_count ?? 0,
    attrs: getKeyAttributes(selectedInfo?.owns ?? [], selectedNs),
    namespace: selectedNs,
    isSelected: true,
    isClickable: false,
    hasChildren: (selectedInfo?.subtypes ?? []).length > 0,
    hasParent: !!selectedInfo?.parent,
  };

  const handleClick = (name: string) => {
    if (onSelectType) onSelectType(name);
  };

  return (
    <div
      style={{
        background: colors.bgSunken,
        border: `1px solid ${colors.borderDim}`,
        borderRadius: 3,
        padding: '20px 24px',
        overflowX: 'auto',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 0,
          minWidth: 'fit-content',
        }}
      >
        {/* Parent */}
        {parent && (
          <>
            <NodeBox node={parent} onClick={() => handleClick(parent.name)} />
            <Arrow />
          </>
        )}
        {!parent && selectedInfo?.parent === undefined && (
          <div style={{
            fontFamily: 'var(--font-jetbrains-mono), monospace',
            fontSize: 9,
            color: colors.fgFaint,
            marginRight: 16,
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
          }}>
            root
          </div>
        )}

        {/* Selected type */}
        <NodeBox node={selectedNode} onClick={() => {}} />

        {/* Children */}
        {children.length > 0 && (
          <>
            <Arrow />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {children.map(child => (
                <NodeBox key={child.name} node={child} onClick={() => handleClick(child.name)} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function Arrow() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', flexShrink: 0, padding: '0 4px' }}>
      <svg width="32" height="16" viewBox="0 0 32 16">
        <line x1="0" y1="8" x2="24" y2="8" stroke={colors.fgFaint} strokeWidth="1.5" />
        <polygon points="24,4 32,8 24,12" fill={colors.fgFaint} />
      </svg>
    </div>
  );
}

function NodeBox({ node, onClick }: { node: TypeNode; onClick: () => void }) {
  const nsColor = getNamespaceColor(node.namespace);
  const isClickable = node.isClickable;

  return (
    <div
      onClick={isClickable ? onClick : undefined}
      style={{
        background: node.isSelected ? 'rgba(90, 173, 175, 0.08)' : colors.panel,
        border: `${node.isSelected ? 2 : 1}px solid ${node.isSelected ? colors.teal : colors.borderDim}`,
        borderRadius: 3,
        padding: '10px 14px',
        minWidth: 160,
        cursor: isClickable ? 'pointer' : 'default',
        transition: 'border-color 0.15s, background 0.15s',
        flexShrink: 0,
      }}
      onMouseEnter={e => {
        if (isClickable) {
          e.currentTarget.style.borderColor = getNamespaceColorRgba(node.namespace, 0.6);
          e.currentTarget.style.background = getNamespaceColorRgba(node.namespace, 0.06);
        }
      }}
      onMouseLeave={e => {
        if (isClickable) {
          e.currentTarget.style.borderColor = colors.borderDim;
          e.currentTarget.style.background = colors.panel;
        } else {
          e.currentTarget.style.borderColor = colors.teal;
          e.currentTarget.style.background = 'rgba(90, 173, 175, 0.08)';
        }
      }}
    >
      {/* Type name */}
      <div style={{
        fontFamily: 'var(--font-jetbrains-mono), "JetBrains Mono", monospace',
        fontSize: 11,
        fontWeight: 600,
        color: node.isSelected ? colors.teal : nsColor,
        marginBottom: 4,
      }}>
        {node.name}
      </div>

      {/* Instance count */}
      <div style={{
        fontFamily: 'var(--font-jetbrains-mono), "JetBrains Mono", monospace',
        fontSize: 9.5,
        color: colors.fgFaint,
        marginBottom: node.attrs.length > 0 ? 6 : 0,
      }}>
        {node.count.toLocaleString()} instances
        {node.hasChildren && !node.isSelected && (
          <span style={{ marginLeft: 6, color: colors.fgFaint }}>+subs</span>
        )}
      </div>

      {/* Key attributes */}
      {node.attrs.length > 0 && (
        <div style={{
          borderTop: `1px solid ${colors.borderDim}`,
          paddingTop: 4,
          display: 'flex',
          flexDirection: 'column',
          gap: 1,
        }}>
          {node.attrs.map(attr => (
            <div key={attr} style={{
              fontFamily: 'var(--font-jetbrains-mono), "JetBrains Mono", monospace',
              fontSize: 9,
              color: colors.fgFaint,
            }}>
              +{attr}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
