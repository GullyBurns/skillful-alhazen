'use client';

import { useMemo } from 'react';
import { colors, getNamespace, getNamespaceColor, getNamespaceColorRgba } from './tokens';

interface EntityTypeInfo {
  parent?: string;
  subtypes?: string[];
  instance_count?: number;
  owns?: string[];
  plays?: string[];
}

interface RelationTypeInfo {
  roles?: string[];
  owns?: string[];
}

interface TypeRelationsDiagramProps {
  typeName: string;
  direction: 'outgoing' | 'incoming';
  schema: {
    entities: Record<string, EntityTypeInfo>;
    relations?: Record<string, RelationTypeInfo>;
  };
  onSelectType?: (typeName: string) => void;
}

interface RelationLink {
  relationName: string;
  myRole: string;
  otherRole: string;
  otherTypes: string[];
  relAttrs: string[]; // attributes owned by this relation
}

export default function TypeRelationsDiagram({ typeName, direction, schema, onSelectType }: TypeRelationsDiagramProps) {
  const links = useMemo(() => {
    const info = schema.entities[typeName];
    if (!info) return [];

    const relations = schema.relations ?? {};
    const result: RelationLink[] = [];

    if (direction === 'outgoing') {
      // Outgoing: relations where THIS type plays a role, pointing to other types
      const plays = info.plays ?? [];
      for (const playStr of plays) {
        const colonIdx = playStr.indexOf(':');
        if (colonIdx < 0) continue;
        const relName = playStr.slice(0, colonIdx);
        const myRole = playStr.slice(colonIdx + 1);

        const relInfo = relations[relName];
        if (!relInfo) continue;

        const allRoles = (relInfo.roles ?? []).map(r => {
          const ci = r.indexOf(':');
          return ci >= 0 ? r.slice(ci + 1) : r;
        });
        const otherRoles = allRoles.filter(r => r !== myRole);

        for (const otherRole of otherRoles) {
          const otherTypes: string[] = [];
          for (const [entName, entInfo] of Object.entries(schema.entities)) {
            if ((entInfo.plays ?? []).includes(`${relName}:${otherRole}`)) {
              otherTypes.push(entName);
            }
          }

          const filtered = otherTypes.filter(t => {
            const subs = schema.entities[t]?.subtypes ?? [];
            return !subs.some(s => otherTypes.includes(s));
          });

          if (filtered.length === 0 || filtered.length > 8) continue;

          result.push({
            relationName: relName,
            myRole,
            otherRole,
            otherTypes: filtered.slice(0, 6),
            relAttrs: relInfo.owns ?? [],
          });
        }
      }
    } else {
      // Incoming: find OTHER types that participate in relations where THIS type plays a role
      // i.e., who points at me?
      const myPlays = new Set(info.plays ?? []);

      for (const [relName, relInfo] of Object.entries(relations)) {
        const allRoles = (relInfo.roles ?? []).map(r => {
          const ci = r.indexOf(':');
          return ci >= 0 ? r.slice(ci + 1) : r;
        });

        // Find which roles this type plays in this relation
        const myRolesInRel = allRoles.filter(r => myPlays.has(`${relName}:${r}`));
        if (myRolesInRel.length === 0) continue;

        for (const myRole of myRolesInRel) {
          const otherRoles = allRoles.filter(r => r !== myRole);

          for (const otherRole of otherRoles) {
            // Find types that play the other role — these are the "sources" pointing at us
            const sourceTypes: string[] = [];
            for (const [entName, entInfo] of Object.entries(schema.entities)) {
              if (entName === typeName) continue;
              if ((entInfo.plays ?? []).includes(`${relName}:${otherRole}`)) {
                sourceTypes.push(entName);
              }
            }

            const filtered = sourceTypes.filter(t => {
              const subs = schema.entities[t]?.subtypes ?? [];
              return !subs.some(s => sourceTypes.includes(s));
            });

            if (filtered.length === 0 || filtered.length > 8) continue;

            // For incoming, swap the perspective: otherTypes are the sources,
            // myRole is what I play, otherRole is what they play
            result.push({
              relationName: relName,
              myRole,
              otherRole,
              otherTypes: filtered.slice(0, 6),
              relAttrs: relInfo.owns ?? [],
            });
          }
        }
      }
    }

    // Sort: namespace-specific relations first
    const ns = getNamespace(typeName);
    result.sort((a, b) => {
      const aNs = getNamespace(a.relationName) === ns ? 0 : 1;
      const bNs = getNamespace(b.relationName) === ns ? 0 : 1;
      if (aNs !== bNs) return aNs - bNs;
      return a.relationName.localeCompare(b.relationName);
    });

    // Deduplicate (same relation+myRole+otherRole seen from outgoing already)
    const seen = new Set<string>();
    return result.filter(r => {
      const key = `${r.relationName}:${r.myRole}:${r.otherRole}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [typeName, direction, schema]);

  if (links.length === 0) {
    return (
      <div style={{
        background: colors.bgSunken,
        border: `1px solid ${colors.borderDim}`,
        borderRadius: 3,
        padding: '20px 24px',
        color: colors.fgFaint,
        fontFamily: 'var(--font-jetbrains-mono), monospace',
        fontSize: 11,
      }}>
        No {direction} relations for this type
      </div>
    );
  }

  return (
    <div style={{
      background: colors.bgSunken,
      border: `1px solid ${colors.borderDim}`,
      borderRadius: 3,
      padding: '16px 20px',
      overflowX: 'auto',
      display: 'flex',
      flexDirection: 'column',
      gap: 8,
    }}>
      {links.map((link, idx) => (
        <RelationRow
          key={`${link.relationName}-${link.myRole}-${link.otherRole}-${idx}`}
          link={link}
          typeName={typeName}
          direction={direction}
          onSelectType={onSelectType}
        />
      ))}
    </div>
  );
}

function RelationRow({
  link,
  typeName,
  direction,
  onSelectType,
}: {
  link: RelationLink;
  typeName: string;
  direction: 'outgoing' | 'incoming';
  onSelectType?: (name: string) => void;
}) {
  const relNs = getNamespace(link.relationName);
  const relColor = getNamespaceColor(relNs);
  const isIncoming = direction === 'incoming';

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 0,
      minWidth: 'fit-content',
    }}>
      {/* Left side: selected type (outgoing) or other types (incoming) */}
      {isIncoming ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {link.otherTypes.map(ot => (
            <TypeChip key={ot} name={ot} namespace={getNamespace(ot)} onClick={() => onSelectType?.(ot)} />
          ))}
        </div>
      ) : (
        <TypeChip name={typeName} isSelected namespace={getNamespace(typeName)} />
      )}

      {/* Arrow with relation name, role labels at ends */}
      <RelationArrow
        relName={link.relationName}
        relColor={relColor}
        relNs={relNs}
        relAttrs={link.relAttrs}
        leftRole={isIncoming ? link.otherRole : link.myRole}
        rightRole={isIncoming ? link.myRole : link.otherRole}
      />

      {/* Right side: other types (outgoing) or selected type (incoming) */}
      {isIncoming ? (
        <TypeChip name={typeName} isSelected namespace={getNamespace(typeName)} />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {link.otherTypes.map(ot => (
            <TypeChip key={ot} name={ot} namespace={getNamespace(ot)} onClick={() => onSelectType?.(ot)} />
          ))}
        </div>
      )}
    </div>
  );
}

function RelationArrow({
  relName,
  relColor,
  relNs,
  relAttrs,
  leftRole,
  rightRole,
}: {
  relName: string;
  relColor: string;
  relNs: string;
  relAttrs: string[];
  leftRole: string;
  rightRole: string;
}) {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      padding: '0 6px',
      flexShrink: 0,
    }}>
      {/* Role labels row */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        width: '100%',
        marginBottom: 2,
      }}>
        <div style={{
          fontFamily: 'var(--font-jetbrains-mono), monospace',
          fontSize: 8,
          color: colors.fgFaint,
        }}>
          {leftRole}
        </div>
        <div style={{
          fontFamily: 'var(--font-jetbrains-mono), monospace',
          fontSize: 8,
          color: colors.fgFaint,
        }}>
          {rightRole}
        </div>
      </div>

      {/* Arrow line + relation card */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <svg width="20" height="10" viewBox="0 0 20 10" style={{ flexShrink: 0 }}>
          <line x1="0" y1="5" x2="20" y2="5" stroke={relColor} strokeWidth="1" strokeOpacity="0.5" />
        </svg>
        <div style={{
          fontFamily: 'var(--font-jetbrains-mono), monospace',
          background: getNamespaceColorRgba(relNs, 0.08),
          borderRadius: 2,
          border: `1px solid ${getNamespaceColorRgba(relNs, 0.15)}`,
          padding: relAttrs.length > 0 ? '4px 8px' : '1px 6px',
        }}>
          <div style={{ fontSize: 9, color: relColor, whiteSpace: 'nowrap' }}>
            {relName}
          </div>
          {relAttrs.length > 0 && (
            <div style={{
              borderTop: `1px solid ${getNamespaceColorRgba(relNs, 0.12)}`,
              marginTop: 3,
              paddingTop: 3,
              display: 'flex',
              flexDirection: 'column',
              gap: 1,
            }}>
              {relAttrs.map(attr => (
                <div key={attr} style={{ fontSize: 8, color: colors.fgFaint, whiteSpace: 'nowrap' }}>
                  {attr}
                </div>
              ))}
            </div>
          )}
        </div>
        <svg width="24" height="10" viewBox="0 0 24 10" style={{ flexShrink: 0 }}>
          <line x1="0" y1="5" x2="18" y2="5" stroke={relColor} strokeWidth="1" strokeOpacity="0.5" />
          <polygon points="18,2 24,5 18,8" fill={relColor} fillOpacity="0.5" />
        </svg>
      </div>
    </div>
  );
}

function TypeChip({
  name,
  namespace,
  isSelected,
  onClick,
}: {
  name: string;
  namespace: string;
  isSelected?: boolean;
  onClick?: () => void;
}) {
  const nsColor = getNamespaceColor(namespace);
  const clickable = !!onClick && !isSelected;

  return (
    <div
      onClick={clickable ? onClick : undefined}
      style={{
        fontFamily: 'var(--font-jetbrains-mono), monospace',
        fontSize: 10,
        color: isSelected ? colors.teal : nsColor,
        background: isSelected ? 'rgba(90,173,175,0.08)' : colors.panel,
        border: `1px solid ${isSelected ? colors.teal : colors.borderDim}`,
        borderRadius: 3,
        padding: '4px 10px',
        whiteSpace: 'nowrap',
        cursor: clickable ? 'pointer' : 'default',
        transition: 'border-color 0.15s, background 0.15s',
        flexShrink: 0,
      }}
      onMouseEnter={e => {
        if (clickable) {
          e.currentTarget.style.borderColor = getNamespaceColorRgba(namespace, 0.6);
          e.currentTarget.style.background = getNamespaceColorRgba(namespace, 0.06);
        }
      }}
      onMouseLeave={e => {
        if (clickable) {
          e.currentTarget.style.borderColor = colors.borderDim;
          e.currentTarget.style.background = colors.panel;
        }
      }}
    >
      {name}
    </div>
  );
}
