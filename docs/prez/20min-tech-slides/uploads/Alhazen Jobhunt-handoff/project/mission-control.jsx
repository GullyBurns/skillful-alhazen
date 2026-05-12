// Dossier — kind-aware lead shell
//
// Consumes `show-opportunity` JSON directly. Renders:
//   - Header strip (kind chip, title, company, status, priority, deadline)
//   - CC Brief panel (most recent jobhunt-cc-brief-note + history)
//   - Timeline (all notes, chronological, color-coded by entity type)
//   - Feedback composer (writes a jobhunt-cc-feedback-note)
//   - Contacts
//   - Requirements (position only)
//   - Background reading
//
// All schema dispatch is on the FULL note `type` string from the CLI.

const T = window.TOKENS;

// ─── Note type catalogue ────────────────────────────────────────
// Maps the full TypeQL entity name → display config. Two new subtypes
// (cc-brief, cc-feedback) are visually elevated; the rest mirror existing
// note kinds in the schema.
const NOTE_TYPES = {
  'jobhunt-cc-brief-note':       { label: 'CC brief',     short: 'BRIEF',    color: T.olive,  icon: 'sparkles', author: 'cc',       elevated: true },
  'jobhunt-cc-feedback-note':    { label: 'Feedback',     short: 'FEEDBACK', color: T.rust,   icon: 'message',  author: 'operator', elevated: true },
  'jobhunt-application-note':    { label: 'Application',  short: 'APP',      color: T.teal,   icon: 'flag',     author: 'operator' },
  'jobhunt-interaction-note':    { label: 'Interaction',  short: 'TALK',     color: T.blue,   icon: 'users',    author: 'operator' },
  'jobhunt-interview-note':      { label: 'Interview',    short: 'INT',      color: T.blue,   icon: 'message',  author: 'operator' },
  'jobhunt-fit-analysis-note':   { label: 'Fit analysis', short: 'FIT',      color: T.mint,   icon: 'target',   author: 'cc' },
  'jobhunt-research-note':       { label: 'Research',     short: 'RES',      color: T.fgDim,  icon: 'book',     author: 'cc' },
  'jobhunt-strategy-note':       { label: 'Strategy',     short: 'STRAT',    color: T.fgDim,  icon: 'compass',  author: 'operator' },
  'jobhunt-skill-gap-note':      { label: 'Skill gap',    short: 'GAP',      color: T.rust,   icon: 'graph',    author: 'cc' },
};
const noteCfg = (t) => NOTE_TYPES[t] || { label: t.replace('jobhunt-', '').replace('-note', ''), short: '?', color: T.fgFaint, icon: 'circle', author: '—' };

// ─── Kind catalogue ─────────────────────────────────────────────
const KINDS = {
  'jobhunt-position':   { label: 'Position',   short: 'POS', color: T.teal,  icon: 'square',   showRequirements: true },
  'jobhunt-engagement': { label: 'Engagement', short: 'ENG', color: T.blue,  icon: 'diamond',  showRequirements: false },
  'jobhunt-venture':    { label: 'Venture',    short: 'VEN', color: T.olive, icon: 'triangle', showRequirements: false },
  'jobhunt-lead':       { label: 'Lead',       short: 'LED', color: T.mint,  icon: 'circle',   showRequirements: false },
};

// ─── Time helpers (this dossier only) ───────────────────────────
const fmtTimestamp = (iso) => {
  const d = new Date(iso); const today = new Date(window.TODAY);
  const days = Math.round((today - d) / 86_400_000);
  const time = d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', timeZone: 'UTC' });
  if (days === 0) return `today · ${time}`;
  if (days === 1) return `yesterday · ${time}`;
  if (days < 7)   return `${days}d ago`;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};
const fmtDate = (iso) => { if (!iso) return '—'; return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }); };
const daysUntil = (iso) => { if (!iso) return null; return Math.round((new Date(iso) - new Date(window.TODAY)) / 86_400_000); };

// ─── Layout primitives ──────────────────────────────────────────
function Panel({ title, action, schema, children, style }) {
  return (
    <section style={{
      background: T.panel, border: `1px solid ${T.border}`, borderRadius: 4,
      padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 12, ...style,
    }}>
      {(title || action) && (
        <header style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <h3 style={{ margin: 0, fontFamily: T.mono, fontSize: 10.5, fontWeight: 600,
            letterSpacing: 1.4, textTransform: 'uppercase', color: T.fgDim }}>{title}</h3>
          {schema && <window.SchemaTag type={schema} onOpen={() => window.__openSchema?.(schema)} />}
          <div style={{ flex: 1 }} />
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

// ─── Header strip ───────────────────────────────────────────────
function HeaderStrip({ data }) {
  const { type, opportunity: o, company, tags } = data;
  const kind = KINDS[type] || KINDS['jobhunt-position'];
  const dDays = daysUntil(o.deadline);

  return (
    <header style={{
      background: T.bgRaised, border: `1px solid ${T.border}`, borderRadius: 4,
      padding: '18px 22px', display: 'flex', flexDirection: 'column', gap: 14,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          padding: '3px 8px', borderRadius: 3,
          background: 'transparent', border: `1px solid ${kind.color}`, color: kind.color,
          fontFamily: T.mono, fontSize: 10.5, letterSpacing: 1, fontWeight: 600,
        }}>
          <window.Icon name={kind.icon} size={11} />{kind.short}
        </span>
        <span style={{ color: T.fgFaint, fontFamily: T.mono, fontSize: 11 }}>·</span>
        <span style={{ color: T.fgDim, fontSize: 13, fontFamily: T.mono }}>{company.name}</span>
        <div style={{ flex: 1 }} />
        <window.SchemaTag type={type} onOpen={() => window.__openSchema?.(type)} />
      </div>

      <h1 style={{
        margin: 0, fontFamily: T.serif, fontSize: 28, lineHeight: 1.15,
        fontWeight: 400, color: T.fg, letterSpacing: -0.4,
      }}>{o.name}</h1>

      <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.55, color: T.fgDim, maxWidth: 720 }}>
        {o.description}
      </p>

      {/* Status row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap',
        paddingTop: 10, borderTop: `1px solid ${T.borderDim}`, marginTop: 4 }}>
        <KV label="Status" value={o.status} mono />
        <KV label="Priority" value={o.priority} mono accent={o.priority === 'high' ? T.olive : null} />
        <KV label="Deadline" value={o.deadline ? `${fmtDate(o.deadline)} · ${dDays > 0 ? `in ${dDays}d` : `${-dDays}d ago`}` : '—'}
          accent={dDays !== null && dDays <= 7 ? T.olive : null} />
        {o.application_status && <KV label="Application" value={o.application_status} mono />}
        {o.salary_range && <KV label="Comp" value={o.salary_range} />}
        {o.location && <KV label="Location" value={o.location} />}
        {o.engagement_type && <KV label="Type" value={o.engagement_type} mono />}
        {o.rate && <KV label="Rate" value={o.rate} />}
        {o.start_date && <KV label="Start" value={fmtDate(o.start_date)} />}
        {o.venture_type && <KV label="Type" value={o.venture_type} mono />}
        {o.stage && <KV label="Stage" value={o.stage} />}
      </div>

      {tags && tags.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {tags.map((t) => (
            <span key={t} style={{
              fontFamily: T.mono, fontSize: 10.5, color: T.fgDim,
              padding: '2px 7px', border: `1px solid ${T.borderDim}`, borderRadius: 3,
            }}>{t}</span>
          ))}
        </div>
      )}
    </header>
  );
}

function KV({ label, value, mono, accent }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
      <span style={{ fontFamily: T.mono, fontSize: 9.5, letterSpacing: 1.2, textTransform: 'uppercase', color: T.fgFaint }}>{label}</span>
      <span style={{ fontSize: 13, color: accent || T.fg, fontFamily: mono ? T.mono : T.sans }}>{value}</span>
    </div>
  );
}

// ─── CC Brief panel (the most recent cc-brief-note + history) ───
function CCBriefPanel({ notes }) {
  const briefs = notes.filter((n) => n.type === 'jobhunt-cc-brief-note')
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  const [showHistory, setShowHistory] = React.useState(false);

  if (briefs.length === 0) {
    return (
      <Panel title="CC brief" schema="jobhunt-cc-brief-note">
        <div style={{ fontSize: 13, color: T.fgFaint, fontStyle: 'italic', padding: '12px 0' }}>
          No brief yet. CC will write one once it has enough context.
        </div>
      </Panel>
    );
  }

  const current = briefs[0];
  const history = briefs.slice(1);

  return (
    <Panel
      title="CC brief"
      schema="jobhunt-cc-brief-note"
      action={
        <span style={{ fontFamily: T.mono, fontSize: 10.5, color: T.fgFaint }}>
          {fmtTimestamp(current.created_at)}
        </span>
      }
      style={{ borderColor: 'rgba(184,200,74,0.32)', background: 'rgba(184,200,74,0.04)' }}
    >
      <div style={{
        fontFamily: T.serif, fontSize: 17, lineHeight: 1.55, color: T.fg,
        textWrap: 'pretty',
      }}>
        {current.content}
      </div>

      {history.length > 0 && (
        <div style={{ borderTop: `1px solid ${T.borderDim}`, paddingTop: 10, marginTop: 4 }}>
          <button
            onClick={() => setShowHistory((v) => !v)}
            style={{
              background: 'transparent', border: 'none', padding: 0, cursor: 'pointer',
              fontFamily: T.mono, fontSize: 11, color: T.fgDim,
              display: 'inline-flex', alignItems: 'center', gap: 6,
            }}
          >
            <window.Icon name={showHistory ? 'caret-down' : 'caret-right'} size={12} />
            {history.length} earlier brief{history.length === 1 ? '' : 's'}
          </button>
          {showHistory && (
            <ol style={{ listStyle: 'none', margin: '10px 0 0', padding: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
              {history.map((b) => (
                <li key={b.id} style={{ fontSize: 12.5, color: T.fgDim, lineHeight: 1.5, paddingLeft: 14, borderLeft: `2px solid ${T.borderDim}` }}>
                  <div style={{ fontFamily: T.mono, fontSize: 10, color: T.fgFaint, marginBottom: 3 }}>{fmtTimestamp(b.created_at)}</div>
                  {b.content}
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </Panel>
  );
}

// ─── Timeline (all notes, chronological, color-coded by type) ───
function Timeline({ notes }) {
  const sorted = [...notes].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  const [filter, setFilter] = React.useState('all');
  const visible = filter === 'all' ? sorted : sorted.filter((n) => n.type === filter);

  // Build filter chips: every type that appears in this dossier
  const present = Array.from(new Set(sorted.map((n) => n.type)));

  return (
    <Panel title="Timeline" schema="jobhunt-aboutness">
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        <FilterChip active={filter === 'all'} onClick={() => setFilter('all')} color={T.fg}>
          all <span style={{ opacity: 0.5, marginLeft: 4 }}>{sorted.length}</span>
        </FilterChip>
        {present.map((t) => {
          const cfg = noteCfg(t);
          const count = sorted.filter((n) => n.type === t).length;
          return (
            <FilterChip key={t} active={filter === t} onClick={() => setFilter(t)} color={cfg.color}>
              {cfg.label.toLowerCase()} <span style={{ opacity: 0.5, marginLeft: 4 }}>{count}</span>
            </FilterChip>
          );
        })}
      </div>

      <ol style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 0, position: 'relative' }}>
        {/* timeline rail */}
        <div style={{ position: 'absolute', left: 7, top: 4, bottom: 4, width: 1, background: T.borderDim }} />
        {visible.map((n) => <TimelineEntry key={n.id} note={n} />)}
      </ol>
    </Panel>
  );
}

function FilterChip({ active, onClick, color, children }) {
  return (
    <button
      onClick={onClick}
      style={{
        fontFamily: T.mono, fontSize: 10.5, letterSpacing: 0.4,
        padding: '3px 8px', borderRadius: 3, cursor: 'pointer',
        background: active ? color : 'transparent',
        color: active ? T.bg : color,
        border: `1px solid ${active ? color : T.borderDim}`,
        textTransform: 'lowercase',
      }}
    >{children}</button>
  );
}

function TimelineEntry({ note }) {
  const cfg = noteCfg(note.type);
  const isCC = cfg.author === 'cc';
  return (
    <li style={{ display: 'flex', gap: 12, padding: '10px 0 12px', borderBottom: `1px solid ${T.borderDim}`, position: 'relative' }}>
      {/* dot */}
      <div style={{
        width: 15, height: 15, marginTop: 3, flexShrink: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: T.bg, position: 'relative', zIndex: 1,
      }}>
        <window.Icon name={cfg.icon} size={12} color={cfg.color} />
      </div>

      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
          <span style={{
            fontFamily: T.mono, fontSize: 9.5, letterSpacing: 1.1, fontWeight: 600,
            color: cfg.color, textTransform: 'uppercase',
          }}>{cfg.short}</span>
          <span style={{ fontSize: 13, color: T.fg, fontWeight: 500 }}>{note.name}</span>
          <span style={{ flex: 1 }} />
          {isCC && (
            <span style={{ fontFamily: T.mono, fontSize: 9.5, color: T.fgFaint, letterSpacing: 0.8 }}>
              ↩ cc
            </span>
          )}
          <span style={{ fontFamily: T.mono, fontSize: 10.5, color: T.fgFaint, whiteSpace: 'nowrap' }}>
            {fmtTimestamp(note.created_at)}
          </span>
        </div>
        <div style={{ fontSize: 13, lineHeight: 1.5, color: T.fgDim, textWrap: 'pretty' }}>
          {note.content}
        </div>
        {/* Type-specific extras */}
        {note.contact_name && (
          <div style={{ fontFamily: T.mono, fontSize: 10.5, color: T.fgFaint }}>
            with <span style={{ color: T.fgDim }}>{note.contact_name}</span>
            {note.interaction_date && <span> · {fmtDate(note.interaction_date)}</span>}
          </div>
        )}
        {note.fit_score != null && (
          <div style={{ display: 'flex', gap: 8, marginTop: 4, flexWrap: 'wrap' }}>
            <span style={{ fontFamily: T.mono, fontSize: 10.5, color: cfg.color }}>fit {(note.fit_score * 100).toFixed(0)}</span>
            {note.axes && Object.entries(note.axes).map(([k, v]) => (
              <span key={k} style={{ fontFamily: T.mono, fontSize: 10, color: T.fgFaint }}>
                {k} <span style={{ color: T.fgDim }}>{(v * 100).toFixed(0)}</span>
              </span>
            ))}
          </div>
        )}
        {note.application_status && (
          <div style={{ fontFamily: T.mono, fontSize: 10.5, color: T.fgFaint }}>
            → status: <span style={{ color: cfg.color }}>{note.application_status}</span>
          </div>
        )}
      </div>
    </li>
  );
}

// ─── Feedback composer (writes a jobhunt-cc-feedback-note) ──────
function FeedbackComposer({ oppId }) {
  const [draft, setDraft] = React.useState('');
  const [sending, setSending] = React.useState(false);
  const [sent, setSent] = React.useState(false);

  const submit = () => {
    if (!draft.trim() || sending) return;
    setSending(true);
    // Simulate the CLI write: jobhunt add-note --type cc-feedback --about <opp>
    setTimeout(() => {
      setSending(false); setSent(true); setDraft('');
      setTimeout(() => setSent(false), 2200);
    }, 600);
  };

  const placeholders = [
    'Push back, redirect, or course-correct…',
    'What is CC missing? What changed?',
    'Tell CC what you want different next time…',
  ];
  const ph = placeholders[oppId.charCodeAt(4) % placeholders.length];

  return (
    <Panel
      title="Send feedback to CC"
      schema="jobhunt-cc-feedback-note"
      action={
        <span style={{ fontFamily: T.mono, fontSize: 10, color: T.fgFaint }}>
          → triggers cc channel
        </span>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={ph}
          rows={3}
          style={{
            background: T.bgSunken, border: `1px solid ${T.borderDim}`, borderRadius: 3,
            color: T.fg, fontFamily: T.sans, fontSize: 13.5, lineHeight: 1.5,
            padding: '10px 12px', resize: 'vertical', minHeight: 64, outline: 'none',
          }}
          onFocus={(e) => (e.target.style.borderColor = T.borderHi)}
          onBlur={(e) => (e.target.style.borderColor = T.borderDim)}
        />
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontFamily: T.mono, fontSize: 10.5, color: T.fgFaint, flex: 1 }}>
            {sent ? <span style={{ color: T.olive }}>✓ feedback note written · cc will pick this up</span>
              : draft.length > 0 ? `${draft.length} chars` : 'no draft'}
          </span>
          <button
            onClick={submit}
            disabled={!draft.trim() || sending}
            style={{
              fontFamily: T.mono, fontSize: 11, fontWeight: 600, letterSpacing: 0.6,
              padding: '6px 14px', borderRadius: 3, cursor: draft.trim() && !sending ? 'pointer' : 'not-allowed',
              background: draft.trim() && !sending ? T.olive : 'transparent',
              color: draft.trim() && !sending ? T.bg : T.fgFaint,
              border: `1px solid ${draft.trim() && !sending ? T.olive : T.borderDim}`,
              textTransform: 'uppercase',
            }}
          >
            {sending ? 'sending…' : 'send →'}
          </button>
        </div>
      </div>
    </Panel>
  );
}

// ─── Contacts panel ─────────────────────────────────────────────
function ContactsPanel({ contacts }) {
  if (!contacts || contacts.length === 0) {
    return (
      <Panel title="Contacts" schema="jobhunt-contact">
        <div style={{ fontSize: 13, color: T.fgFaint, fontStyle: 'italic' }}>No contacts linked yet.</div>
      </Panel>
    );
  }
  return (
    <Panel title="Contacts" schema="jobhunt-contact">
      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 0 }}>
        {contacts.map((c, i) => (
          <li key={c.id} style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '8px 0', borderTop: i === 0 ? 'none' : `1px solid ${T.borderDim}`,
          }}>
            <div style={{
              width: 28, height: 28, borderRadius: 14,
              background: 'rgba(90,173,175,0.12)', color: T.teal,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: T.mono, fontSize: 11, fontWeight: 600, flexShrink: 0,
            }}>{c.name.split(' ').map((p) => p[0]).slice(0, 2).join('')}</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, color: T.fg }}>{c.name}</div>
              {c.contact_email && <div style={{ fontFamily: T.mono, fontSize: 10.5, color: T.fgFaint }}>{c.contact_email}</div>}
            </div>
            <span style={{
              fontFamily: T.mono, fontSize: 10, letterSpacing: 0.6, textTransform: 'uppercase',
              padding: '2px 7px', borderRadius: 3,
              border: `1px solid ${T.borderDim}`, color: T.fgDim,
            }}>{c.contact_role}</span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// ─── Requirements panel (position only) ─────────────────────────
function RequirementsPanel({ requirements }) {
  if (!requirements || requirements.length === 0) return null;
  const levelColor = { strong: T.mint, some: T.olive, learning: T.rust, none: T.fgFaint };
  const levelOrder = { required: 0, preferred: 1, 'nice-to-have': 2 };
  const sorted = [...requirements].sort((a, b) => (levelOrder[a.level] ?? 9) - (levelOrder[b.level] ?? 9));

  return (
    <Panel title="Requirements vs you" schema="jobhunt-requirement">
      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 0 }}>
        {sorted.map((r, i) => (
          <li key={r.id} style={{
            display: 'grid', gridTemplateColumns: '1fr auto auto', gap: 12, alignItems: 'center',
            padding: '7px 0', borderTop: i === 0 ? 'none' : `1px solid ${T.borderDim}`,
          }}>
            <span style={{ fontSize: 13, color: T.fg }}>{r.skill}</span>
            <span style={{
              fontFamily: T.mono, fontSize: 10, letterSpacing: 0.6, textTransform: 'uppercase',
              color: r.level === 'required' ? T.olive : r.level === 'preferred' ? T.teal : T.fgFaint,
            }}>{r.level}</span>
            <span style={{
              fontFamily: T.mono, fontSize: 10.5, letterSpacing: 0.4,
              color: levelColor[r.your_level] || T.fgDim,
              padding: '2px 8px', borderRadius: 3,
              border: `1px solid ${levelColor[r.your_level] || T.borderDim}40`,
              minWidth: 64, textAlign: 'center',
            }}>you · {r.your_level}</span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// ─── Background reading ─────────────────────────────────────────
function BackgroundReading({ collections }) {
  if (!collections || collections.length === 0) return null;
  return (
    <Panel title="Background reading" schema="jobhunt-relevance">
      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {collections.map((c) => (
          <li key={c.collection_id} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <window.Icon name="book" size={13} color={T.fgDim} />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, color: T.fg }}>{c.collection_name}</div>
              {c.description && <div style={{ fontFamily: T.mono, fontSize: 10.5, color: T.fgFaint }}>{c.description}</div>}
            </div>
            <window.Icon name="external" size={12} color={T.fgFaint} />
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// ─── Composition: the whole dossier ─────────────────────────────
function Dossier({ data }) {
  const kind = KINDS[data.type] || KINDS['jobhunt-position'];

  return (
    <div style={{
      padding: 20, height: '100%', overflow: 'auto',
      background: T.bg, color: T.fg, fontFamily: T.sans,
      display: 'flex', flexDirection: 'column', gap: 14,
    }}>
      <HeaderStrip data={data} />

      <CCBriefPanel notes={data.notes} />

      <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 14, alignItems: 'start' }}>
        {/* Left column: timeline + composer */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Timeline notes={data.notes} />
          <FeedbackComposer oppId={data.opportunity.id} />
        </div>

        {/* Right column: contacts, requirements, reading */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <ContactsPanel contacts={data.contacts} />
          {kind.showRequirements && <RequirementsPanel requirements={data.requirements} />}
          <BackgroundReading collections={data.background_reading} />
        </div>
      </div>

      {/* Tiny footer attribution */}
      <footer style={{
        marginTop: 8, paddingTop: 12, borderTop: `1px solid ${T.borderDim}`,
        display: 'flex', alignItems: 'center', gap: 10,
        fontFamily: T.mono, fontSize: 10, color: T.fgFaint,
      }}>
        <span>lead · {data.opportunity.id}</span>
        <span>·</span>
        <span>shape: show-opportunity --json</span>
      </footer>
    </div>
  );
}

window.Dossier = Dossier;
window.NOTE_TYPES = NOTE_TYPES;
window.KINDS = KINDS;
