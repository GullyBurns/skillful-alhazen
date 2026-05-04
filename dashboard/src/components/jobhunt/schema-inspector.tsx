'use client';

import { useEffect, useRef } from 'react';

const C = {
  bg: '#070d1c', bgR: '#0c1628', bgS: '#050a16',
  fg: '#c8dde8', fgD: '#8ba4b8', fgF: '#5e7387',
  teal: '#5aadaf', olive: '#b8c84a', mint: '#62c4bc',
  border: 'rgba(90,173,175,0.18)', borderD: 'rgba(200,221,232,0.08)',
  mono: "'JetBrains Mono', monospace", sans: "'DM Sans', sans-serif",
};

export interface SchemaTagProps { type: string; onOpen: () => void; }
export function SchemaTag({ type, onOpen }: SchemaTagProps) {
  return (
    <button onClick={onOpen} style={{
      fontFamily: C.mono, fontSize: 11, color: C.fgD, background: 'transparent',
      border: `1px dashed ${C.border}`, borderRadius: 4, padding: '2px 7px',
      cursor: 'pointer', letterSpacing: '0.01em', transition: 'border-color 0.15s, color 0.15s',
    }}
      onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = C.teal; (e.currentTarget as HTMLButtonElement).style.color = C.teal; }}
      onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = C.border; (e.currentTarget as HTMLButtonElement).style.color = C.fgD; }}
    >&lt;/&gt; {type}</button>
  );
}

const ENTITIES = [
  { cat: 'Opportunity types', items: [
    { name: 'jhunt-position', parent: 'jhunt-opportunity', attrs: 'id, name, status, url, location, jhunt-salary-range, work-type' },
    { name: 'jhunt-engagement', parent: 'jhunt-opportunity', attrs: 'id, name, status, jhunt-engagement-type' },
    { name: 'jhunt-venture', parent: 'jhunt-opportunity', attrs: 'id, name, status, stage' },
    { name: 'jhunt-lead', parent: 'jhunt-opportunity', attrs: 'id, name, status, source' },
  ]},
  { cat: 'Note types', items: [
    { name: 'jhunt-application-note', parent: 'note', attrs: 'id, content, created-at' },
    { name: 'jhunt-research-note', parent: 'note', attrs: 'id, content, created-at' },
    { name: 'jhunt-fit-analysis-note', parent: 'note', attrs: 'id, content, created-at' },
    { name: 'jhunt-interview-note', parent: 'note', attrs: 'id, content, created-at' },
    { name: 'jhunt-interaction-note', parent: 'note', attrs: 'id, content, created-at' },
    { name: 'jhunt-strategy-note', parent: 'note', attrs: 'id, content, created-at' },
    { name: 'jhunt-skill-gap-note', parent: 'note', attrs: 'id, content, created-at' },
    { name: 'jhunt-cc-brief-note', parent: 'note', attrs: 'id, content, created-at' },
    { name: 'jhunt-cc-feedback-note', parent: 'note', attrs: 'id, content, created-at' },
    { name: 'jhunt-dashboard-state-note', parent: 'note', attrs: 'id, content, created-at' },
  ]},
  { cat: 'Supporting types', items: [
    { name: 'jhunt-company', parent: 'organization', attrs: 'id, name, alh-linkedin-url, alh-company-url, location, industry' },
    { name: 'jhunt-contact', parent: 'person', attrs: 'id, name, alh-email-address, alh-linkedin-url, jhunt-contact-role' },
    { name: 'jhunt-requirement', parent: 'alh-domain-thing', attrs: 'id, name, description, requirement-type' },
    { name: 'jhunt-learning-resource', parent: 'alh-domain-thing', attrs: 'id, name, url, jhunt-resource-type' },
    { name: 'jhunt-your-skill', parent: 'alh-domain-thing', attrs: 'id, name, description, proficiency' },
  ]},
];

const RELATIONS = [
  { name: 'aboutness', roles: 'note: $n, subject: $s', desc: 'links any note to any entity' },
  { name: 'jhunt-position-at-company', roles: 'position: $p, employer: $c', desc: 'jhunt-position ↔ jhunt-company' },
  { name: 'alh-works-at', roles: 'employee: $p, employer: $o', desc: 'person ↔ organization' },
  { name: 'alh-collection-membership', roles: 'collection: $col, member: $m', desc: 'groups entities into collections' },
  { name: 'alh-interaction-participation', roles: 'interaction: $i, participant: $p', desc: 'interaction ↔ person' },
];

const CMDS = [
  { cmd: 'list-pipeline', arrow: '→ pipeline view', note: 'all positions with status' },
  { cmd: 'show-position / show-opportunity', arrow: '→ dossier view', note: 'full detail with notes' },
  { cmd: 'embedding_map.py map', arrow: '→ scatter plot', note: 'MDE embedding of all opportunities' },
  { cmd: 'add-note --type cc-brief', arrow: '→ CC brief note', note: 'attach a cover-letter brief' },
];

export interface SchemaInspectorProps { open: boolean; onClose: () => void; focus?: string | null; }
export function SchemaInspector({ open, onClose, focus }: SchemaInspectorProps) {
  const focusRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  useEffect(() => {
    if (open && focus && focusRef.current) {
      setTimeout(() => focusRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 80);
    }
  }, [open, focus]);

  if (!open) return null;

  const pill = (label: string, color = C.fgF) => (
    <span style={{ fontFamily: C.mono, fontSize: 10, color, background: C.bgS, border: `1px solid ${C.borderD}`, borderRadius: 3, padding: '1px 6px', marginRight: 4 }}>{label}</span>
  );

  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, zIndex: 9999, display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
      background: 'rgba(5,10,22,0.82)', backdropFilter: 'blur(6px)', padding: '40px 16px', overflowY: 'auto',
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        width: '100%', maxWidth: 900, background: C.bgR, border: `1px solid ${C.border}`,
        borderRadius: 10, padding: '28px 32px', fontFamily: C.sans, color: C.fg,
      }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
          <div>
            <span style={{ fontFamily: C.mono, fontSize: 18, color: C.teal, letterSpacing: '-0.02em' }}>&lt;/&gt; Schema Inspector</span>
            {focus && <span style={{ marginLeft: 14, fontFamily: C.mono, fontSize: 12, color: C.olive, background: C.bgS, border: `1px solid ${C.olive}44`, borderRadius: 4, padding: '2px 8px' }}>focus: {focus}</span>}
          </div>
          <button onClick={onClose} style={{ fontFamily: C.mono, fontSize: 12, color: C.fgF, background: C.bgS, border: `1px solid ${C.borderD}`, borderRadius: 4, padding: '3px 10px', cursor: 'pointer' }}>esc</button>
        </div>

        {/* Entity Types */}
        <section style={{ marginBottom: 28 }}>
          <div style={{ fontSize: 11, letterSpacing: '0.12em', color: C.fgF, textTransform: 'uppercase', marginBottom: 14 }}>Entity Types</div>
          {ENTITIES.map(({ cat, items }) => (
            <div key={cat} style={{ marginBottom: 18 }}>
              <div style={{ fontSize: 12, color: C.fgD, marginBottom: 8 }}>{cat}</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {items.map(item => {
                  const isFocus = focus === item.name;
                  return (
                    <div key={item.name} ref={isFocus ? focusRef : null} style={{
                      display: 'flex', alignItems: 'baseline', gap: 10, padding: '7px 12px',
                      background: isFocus ? `${C.olive}12` : C.bgS,
                      border: `1px solid ${isFocus ? C.olive : C.borderD}`,
                      borderRadius: 6, flexWrap: 'wrap',
                    }}>
                      <span style={{ fontFamily: C.mono, fontSize: 13, color: C.mint, minWidth: 240 }}>{item.name}</span>
                      {pill(`sub ${item.parent}`, C.fgF)}
                      <span style={{ fontFamily: C.mono, fontSize: 11, color: C.fgF }}>{item.attrs}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </section>

        {/* Relations */}
        <section style={{ marginBottom: 28 }}>
          <div style={{ fontSize: 11, letterSpacing: '0.12em', color: C.fgF, textTransform: 'uppercase', marginBottom: 14 }}>Relations</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {RELATIONS.map(r => (
              <div key={r.name} style={{ display: 'flex', alignItems: 'baseline', gap: 10, padding: '7px 12px', background: C.bgS, border: `1px solid ${C.borderD}`, borderRadius: 6, flexWrap: 'wrap' }}>
                <span style={{ fontFamily: C.mono, fontSize: 13, color: C.teal, minWidth: 220 }}>{r.name}</span>
                <span style={{ fontFamily: C.mono, fontSize: 11, color: C.fgD, minWidth: 220 }}>{r.roles}</span>
                <span style={{ fontSize: 12, color: C.fgF }}>{r.desc}</span>
              </div>
            ))}
          </div>
        </section>

        {/* CLI Commands */}
        <section>
          <div style={{ fontSize: 11, letterSpacing: '0.12em', color: C.fgF, textTransform: 'uppercase', marginBottom: 14 }}>CLI Commands</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {CMDS.map(c => (
              <div key={c.cmd} style={{ display: 'flex', alignItems: 'baseline', gap: 10, padding: '7px 12px', background: C.bgS, border: `1px solid ${C.borderD}`, borderRadius: 6, flexWrap: 'wrap' }}>
                <span style={{ fontFamily: C.mono, fontSize: 12, color: C.olive, minWidth: 260 }}>{c.cmd}</span>
                <span style={{ fontFamily: C.mono, fontSize: 11, color: C.teal, minWidth: 160 }}>{c.arrow}</span>
                <span style={{ fontSize: 12, color: C.fgF }}>{c.note}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
