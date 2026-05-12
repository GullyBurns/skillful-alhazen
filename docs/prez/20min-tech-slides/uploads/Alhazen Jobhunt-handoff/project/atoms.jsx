// Shared atoms — palette tokens, helpers, primitives.
// Sticks STRICTLY to the existing Starry Night identity from globals.css:
//   bg #070d1c | card #0c1628 | fg #c8dde8 | muted-fg #8ba4b8
//   teal #5aadaf (primary) | dusty-blue #5b8ab8 | olive #b8c84a (accent) | mint #62c4bc
// No gradients, no purple, no off-brand blue.

const TOKENS = {
  bg:        '#070d1c',
  bgRaised:  '#0c1628',
  bgSunken:  '#050a16',
  panel:     'rgba(12, 22, 40, 0.72)',
  panelHi:   'rgba(20, 34, 58, 0.85)',
  border:    'rgba(90, 173, 175, 0.18)',
  borderHi:  'rgba(90, 173, 175, 0.42)',
  borderDim: 'rgba(200, 221, 232, 0.08)',
  fg:        '#c8dde8',
  fgDim:     '#8ba4b8',
  fgFaint:   '#5e7387',
  teal:      '#5aadaf',
  tealDim:   'rgba(90, 173, 175, 0.18)',
  blue:      '#5b8ab8',
  blueDim:   'rgba(91, 138, 184, 0.18)',
  olive:     '#b8c84a',
  oliveDim:  'rgba(184, 200, 74, 0.18)',
  mint:      '#62c4bc',
  rust:      '#c87a4a',
  rustDim:   'rgba(200, 122, 74, 0.18)',
  mono:      'ui-monospace, "JetBrains Mono", "SF Mono", Menlo, monospace',
  serif:     '"DM Serif Display", "Iowan Old Style", Georgia, serif',
  sans:      '"DM Sans", -apple-system, system-ui, sans-serif',
};
window.TOKENS = TOKENS;

// Days delta helper for staleness / deadlines
window.daysBetween = (iso) => {
  if (!iso) return null;
  const ms = new Date(iso) - new Date('2026-04-30');
  return Math.round(ms / 86_400_000);
};

window.fmtDate = (iso) => {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

window.relDate = (iso) => {
  const d = window.daysBetween(iso);
  if (d === null) return '—';
  if (d === 0) return 'today';
  if (d === 1) return 'tomorrow';
  if (d === -1) return 'yesterday';
  if (d > 0) return `in ${d}d`;
  return `${-d}d ago`;
};

// Tiny inline icons — geometric, not emoji, not stock lucide colors.
function Icon({ name, size = 14, color = 'currentColor', style }) {
  const s = size;
  const common = { width: s, height: s, viewBox: '0 0 24 24', fill: 'none', stroke: color, strokeWidth: 1.6, strokeLinecap: 'round', strokeLinejoin: 'round', style };
  switch (name) {
    case 'circle':       return <svg {...common}><circle cx="12" cy="12" r="9"/></svg>;
    case 'dot':          return <svg {...common} fill={color}><circle cx="12" cy="12" r="4" stroke="none"/></svg>;
    case 'square':       return <svg {...common}><rect x="4" y="4" width="16" height="16" rx="2"/></svg>;
    case 'diamond':      return <svg {...common}><path d="M12 3 L21 12 L12 21 L3 12 Z"/></svg>;
    case 'triangle':     return <svg {...common}><path d="M12 4 L21 19 L3 19 Z"/></svg>;
    case 'arrow-right':  return <svg {...common}><path d="M5 12h14M13 6l6 6-6 6"/></svg>;
    case 'arrow-up-right': return <svg {...common}><path d="M7 17 17 7M9 7h8v8"/></svg>;
    case 'external':     return <svg {...common}><path d="M14 4h6v6"/><path d="M20 4l-9 9"/><path d="M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5"/></svg>;
    case 'clock':        return <svg {...common}><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>;
    case 'calendar':     return <svg {...common}><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>;
    case 'compass':      return <svg {...common}><circle cx="12" cy="12" r="9"/><path d="M16 8l-2 6-6 2 2-6z" fill={color} stroke="none" opacity="0.6"/></svg>;
    case 'target':       return <svg {...common}><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5" fill={color} stroke="none"/></svg>;
    case 'star':         return <svg {...common}><path d="M12 3l2.5 6 6.5.5-5 4.5 1.5 6.5L12 17l-5.5 3.5L8 14 3 9.5 9.5 9z"/></svg>;
    case 'spark':        return <svg {...common}><path d="M12 3v6M12 15v6M3 12h6M15 12h6"/></svg>;
    case 'link':         return <svg {...common}><path d="M10 14a4 4 0 0 0 5.66 0l3-3a4 4 0 0 0-5.66-5.66l-1 1"/><path d="M14 10a4 4 0 0 0-5.66 0l-3 3a4 4 0 0 0 5.66 5.66l1-1"/></svg>;
    case 'user':         return <svg {...common}><circle cx="12" cy="8" r="4"/><path d="M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1"/></svg>;
    case 'users':        return <svg {...common}><circle cx="9" cy="8" r="3.5"/><circle cx="17" cy="9" r="2.5"/><path d="M3 20v-1a5 5 0 0 1 5-5h2a5 5 0 0 1 5 5v1"/><path d="M15 20v-1a4 4 0 0 1 4-4h.5"/></svg>;
    case 'message':      return <svg {...common}><path d="M21 12a8 8 0 1 1-3.5-6.6L21 4l-1 4.5A8 8 0 0 1 21 12z"/></svg>;
    case 'doc':          return <svg {...common}><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/></svg>;
    case 'book':         return <svg {...common}><path d="M4 4v15a2 2 0 0 1 2-2h14V3H6a2 2 0 0 0-2 2z"/><path d="M4 19a2 2 0 0 0 2 2h14"/></svg>;
    case 'graph':        return <svg {...common}><circle cx="6" cy="18" r="2"/><circle cx="12" cy="6" r="2"/><circle cx="18" cy="14" r="2"/><path d="M7.5 17l3-9M13.5 7.5l3 5.5"/></svg>;
    case 'plus':         return <svg {...common}><path d="M12 5v14M5 12h14"/></svg>;
    case 'check':        return <svg {...common}><path d="M5 12l4 4 10-10"/></svg>;
    case 'cross':        return <svg {...common}><path d="M5 5l14 14M19 5L5 19"/></svg>;
    case 'pin':          return <svg {...common}><path d="M12 21s-7-7-7-12a7 7 0 0 1 14 0c0 5-7 12-7 12z"/><circle cx="12" cy="9" r="2.5"/></svg>;
    case 'flag':         return <svg {...common}><path d="M5 21V4M5 4h12l-2 4 2 4H5"/></svg>;
    case 'caret-down':   return <svg {...common}><path d="M6 9l6 6 6-6"/></svg>;
    case 'caret-right':  return <svg {...common}><path d="M9 6l6 6-6 6"/></svg>;
    case 'menu':         return <svg {...common}><path d="M4 7h16M4 12h16M4 17h16"/></svg>;
    case 'code':         return <svg {...common}><path d="M9 8l-5 4 5 4M15 8l5 4-5 4"/></svg>;
    case 'share':        return <svg {...common}><circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="M8 11l8-4M8 13l8 4"/></svg>;
    case 'sparkles':     return <svg {...common}><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M6 18l2.5-2.5M15.5 8.5L18 6"/></svg>;
    case 'orbit':        return <svg {...common}><ellipse cx="12" cy="12" rx="9" ry="3" transform="rotate(-30 12 12)"/><circle cx="12" cy="12" r="2.5" fill={color} stroke="none"/></svg>;
    default:             return <svg {...common}><circle cx="12" cy="12" r="6"/></svg>;
  }
}
window.Icon = Icon;

// Subtype catalogue
window.SUBTYPES = {
  position:   { label: 'Position',   icon: 'square',   color: TOKENS.teal,  short: 'POS' },
  engagement: { label: 'Engagement', icon: 'diamond',  color: TOKENS.blue,  short: 'ENG' },
  venture:    { label: 'Venture',    icon: 'triangle', color: TOKENS.olive, short: 'VEN' },
  lead:       { label: 'Lead',       icon: 'circle',   color: TOKENS.mint,  short: 'LED' },
};

// Application status order
window.STATUS_ORDER = ['researching', 'applied', 'phone-screen', 'interviewing', 'offer', 'rejected', 'withdrawn'];

// Action-engine urgency colors
window.URGENCY = {
  high:   { color: TOKENS.olive, label: 'now' },
  medium: { color: TOKENS.teal,  label: 'soon' },
  low:    { color: TOKENS.fgDim, label: 'later' },
};

// Kbd / chip primitives
window.Kbd = ({ children }) => (
  <span style={{
    fontFamily: TOKENS.mono, fontSize: 10.5, padding: '2px 6px',
    border: `1px solid ${TOKENS.borderDim}`, borderRadius: 3,
    color: TOKENS.fgDim, background: 'rgba(255,255,255,0.02)',
    letterSpacing: 0.5,
  }}>{children}</span>
);

window.SchemaTag = ({ type, id, onOpen }) => (
  <button
    onClick={onOpen}
    title={`schema: ${type}${id ? ` · ${id}` : ''}`}
    style={{
      fontFamily: TOKENS.mono, fontSize: 10, letterSpacing: 0.4,
      color: TOKENS.fgFaint, background: 'transparent',
      border: `1px dashed ${TOKENS.borderDim}`, borderRadius: 3,
      padding: '1px 5px', cursor: 'pointer', display: 'inline-flex',
      alignItems: 'center', gap: 4,
    }}
    onMouseEnter={(e) => { e.currentTarget.style.color = TOKENS.teal; e.currentTarget.style.borderColor = TOKENS.borderHi; }}
    onMouseLeave={(e) => { e.currentTarget.style.color = TOKENS.fgFaint; e.currentTarget.style.borderColor = TOKENS.borderDim; }}
  >
    <span style={{ opacity: 0.6 }}>{'</>'}</span>
    <span>{type}</span>
  </button>
);
