// Schema inspector — surfaces the actual schema delta v2 needs.
//
// After mapping the dashboard against the live `show-opportunity` /
// `list-attention` JSON, the schema delta turned out to be exactly
// TWO new note subtypes. Everything else the dashboard renders is
// already in jobhunt.tql. This inspector documents that delta and
// shows each addition's JSON shape as it appears in the API response.

function SchemaInspector({ open, onClose, focus }) {
  if (!open) return null;
  const T = window.TOKENS;

  const ADDITIONS = [
    {
      name: 'jobhunt-cc-brief-note',
      role: 'CC → operator',
      summary: 'A running read on the opportunity, written by the career-coach agent. The most recent one is the dashboard\'s headline; older ones are history. Refreshed by CC on its own cadence and on demand after the operator sends feedback.',
      tql: `entity jobhunt-cc-brief-note sub note;
# inherits: name, content, created-at
# linked to opportunity via aboutness relation
# (no new attributes — type alone is the discriminator)`,
      json: `{
  "id": "n-augura-cb3",
  "type": "jobhunt-cc-brief-note",
  "name": "Brief · phone screen prep window",
  "content": "You are 6 days out from the Allen Kim phone screen and the recruiter ping is 2 days stale...",
  "created_at": "2026-04-30T09:00:00Z"
}`,
      cli: `# CC writes this via the agent, but operators can write/edit too:
jobhunt add-note --type cc-brief --about <opp-id> --content "..."`,
      list: `# Visible in list-attention as the latest_cc_brief field:
{
  "id": "pos-augura-staff-mle",
  "latest_cc_brief": "2026-04-30T09:00:00Z",
  "pending_feedback_count": 0,
  ...
}`,
    },
    {
      name: 'jobhunt-cc-feedback-note',
      role: 'operator → CC',
      summary: 'A short message from the operator to CC. Pushback, redirection, course correction. Writing one fires CC\'s channel — CC re-reads the dossier and emits a fresh brief that incorporates the feedback. The pending_feedback_count metric is the number of feedback notes newer than the latest brief.',
      tql: `entity jobhunt-cc-feedback-note sub note;
# inherits: name, content, created-at
# linked to opportunity via aboutness relation
# write triggers cc channel via existing event-bus subscription`,
      json: `{
  "id": "n-augura-f1",
  "type": "jobhunt-cc-feedback-note",
  "name": "Feedback · Devon thank-you",
  "content": "Drafted a thank-you to Devon Aoki for the referral coffee. Keep it short...",
  "created_at": "2026-04-28T18:00:00Z"
}`,
      cli: `# Operators write feedback from the dashboard composer or directly:
jobhunt add-note --type cc-feedback --about <opp-id> --content "..."`,
      list: `# Counted in list-attention as pending_feedback_count
# (feedback notes newer than latest_cc_brief):
{
  "id": "pos-celastra",
  "latest_cc_brief": "2026-04-25T10:00:00Z",
  "pending_feedback_count": 2,    // ← 2 feedback notes since
  ...
}`,
    },
  ];

  const NO_CHANGE = [
    { name: 'jobhunt-application-note', why: 'Already exists. Carries application_status + applied_date.' },
    { name: 'jobhunt-interaction-note', why: 'Already exists. Carries contact_name + interaction_date.' },
    { name: 'jobhunt-fit-analysis-note', why: 'Already exists. Carries fit_score + axes JSON.' },
    { name: 'jobhunt-research-note',    why: 'Already exists. Free-form prose, no extras needed.' },
    { name: 'jobhunt-strategy-note',    why: 'Already exists. Free-form prose.' },
    { name: 'jobhunt-skill-gap-note',   why: 'Already exists. Carries gap_skill, gap_level.' },
    { name: 'jobhunt-interview-note',   why: 'Already exists. Carries interviewer + interview_date.' },
    { name: 'jobhunt-requirement',      why: 'Already exists. show-position returns it with your_level for gap shading.' },
    { name: 'jobhunt-contact',          why: 'Already exists. show-opportunity now returns linked contacts via the dual-source query (interaction-notes ∪ works-at).' },
    { name: 'jobhunt-relevance',        why: 'Already exists. Used to surface background_reading collections.' },
    { name: 'jobhunt-opportunity (kind discriminator)', why: 'Schema already polymorphic via subtypes (jobhunt-position / -engagement / -venture / -lead). show-opportunity returns the type field; the dashboard dispatches on it.' },
  ];

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(7, 13, 28, 0.86)',
      backdropFilter: 'blur(6px)', zIndex: 100,
      display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
      padding: 32, overflowY: 'auto',
    }} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} style={{
        width: '100%', maxWidth: 980, background: T.bgRaised,
        border: `1px solid ${T.borderHi}`, borderRadius: 4,
        fontFamily: T.mono, color: T.fg, fontSize: 12.5,
      }}>
        {/* header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 20px', borderBottom: `1px solid ${T.border}` }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <window.Icon name="code" size={14} color={T.teal} />
            <span style={{ fontFamily: T.sans, fontSize: 13, fontWeight: 500, letterSpacing: 0.3 }}>Schema delta</span>
            <span style={{ color: T.fgFaint }}>· what v2 needs from jobhunt.tql</span>
            {focus && <span style={{ color: T.olive, marginLeft: 12, fontSize: 11 }}>focus: {focus}</span>}
          </div>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: T.fgDim, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontFamily: T.mono, fontSize: 11 }}>
            esc <window.Icon name="cross" size={14} />
          </button>
        </div>

        {/* TL;DR */}
        <div style={{ padding: '16px 20px', borderBottom: `1px solid ${T.border}`, background: 'rgba(184,200,74,0.06)' }}>
          <div style={{ fontFamily: T.sans, fontSize: 13.5, color: T.fg, lineHeight: 1.55 }}>
            <span style={{ fontWeight: 600, color: T.olive }}>Two new note subtypes.</span>{' '}
            That is the entire schema change to support this dashboard. Both inherit{' '}
            <code style={{ color: T.mint }}>name</code>, <code style={{ color: T.mint }}>content</code>,{' '}
            <code style={{ color: T.mint }}>created-at</code> from <code style={{ color: T.mint }}>note</code>.{' '}
            No new attributes, no new relations. The CLI gains two entries in <code style={{ color: T.mint }}>type_map</code>{' '}
            and a small extension to <code style={{ color: T.mint }}>NOTE_TYPE_ATTRS</code>; the rest of the dashboard
            is rendering existing data differently.
          </div>
        </div>

        {/* additions */}
        <div style={{ padding: 20 }}>
          <div style={{ color: T.olive, marginBottom: 14, fontSize: 10.5, letterSpacing: 1, textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: 8 }}>
            additions to jobhunt.tql
            <span style={{ flex: 1, height: 1, background: T.borderDim }} />
          </div>

          {ADDITIONS.map((a) => (
            <div key={a.name} style={{
              marginBottom: 22, paddingBottom: 22,
              borderBottom: `1px solid ${T.borderDim}`,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                <window.Icon name="plus" size={12} color={T.olive} />
                <span style={{ color: T.fg, fontSize: 14, fontWeight: 500 }}>{a.name}</span>
                <span style={{
                  fontFamily: T.mono, fontSize: 10, letterSpacing: 0.6,
                  padding: '2px 7px', borderRadius: 2,
                  border: `1px solid ${T.borderDim}`, color: T.fgDim,
                  textTransform: 'uppercase',
                }}>{a.role}</span>
              </div>
              <p style={{ margin: '4px 0 12px', color: T.fgDim, fontFamily: T.sans, fontSize: 12.5, lineHeight: 1.55 }}>
                {a.summary}
              </p>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <CodeBlock label="schema.tql" content={a.tql} color={T.olive} />
                <CodeBlock label="show-opportunity → notes[]" content={a.json} color={T.teal} />
                <CodeBlock label="CLI" content={a.cli} color={T.mint} />
                <CodeBlock label="list-attention" content={a.list} color={T.blue} />
              </div>
            </div>
          ))}

          <div style={{ color: T.fgDim, marginTop: 8, marginBottom: 10, fontSize: 10.5, letterSpacing: 1, textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: 8 }}>
            no schema change — already covered
            <span style={{ flex: 1, height: 1, background: T.borderDim }} />
          </div>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
            {NO_CHANGE.map((n) => (
              <li key={n.name} style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 12, padding: '5px 0', fontSize: 11.5 }}>
                <code style={{ color: T.mint, fontFamily: T.mono }}>{n.name}</code>
                <span style={{ color: T.fgDim, fontFamily: T.sans }}>{n.why}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* footer */}
        <div style={{ padding: '10px 20px', borderTop: `1px solid ${T.border}`, color: T.fgFaint, fontSize: 10.5, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>data source: <span style={{ color: T.fgDim }}>jobhunt.tql + jobhunt.py</span></span>
          <span>delta: <span style={{ color: T.olive }}>+2 entity types · +2 type_map entries</span></span>
        </div>
      </div>
    </div>
  );
}

function CodeBlock({ label, content, color }) {
  const T = window.TOKENS;
  return (
    <div>
      <div style={{
        fontFamily: T.mono, fontSize: 9.5, letterSpacing: 0.8, textTransform: 'uppercase',
        color: color, marginBottom: 4,
      }}>{label}</div>
      <pre style={{
        color: T.fgDim, fontSize: 11, margin: 0,
        padding: '8px 10px',
        background: T.bgSunken, border: `1px solid ${T.borderDim}`, borderRadius: 3,
        whiteSpace: 'pre-wrap', fontFamily: T.mono, lineHeight: 1.5,
        overflowX: 'auto',
      }}>{content}</pre>
    </div>
  );
}

window.SchemaInspector = SchemaInspector;
