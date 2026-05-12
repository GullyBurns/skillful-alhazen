// Starry Night design tokens for tech-recon dashboard
// Full palette matching the jobhunt Dossier design reference.

export const T = {
  // Backgrounds
  bg: '#070d1c',
  bgRaised: '#0c1628',
  bgSunken: '#050a16',
  panel: 'rgba(12, 22, 40, 0.72)',
  panelHi: 'rgba(20, 34, 58, 0.85)',

  // Borders
  border: 'rgba(90, 173, 175, 0.18)',
  borderHi: 'rgba(90, 173, 175, 0.42)',
  borderDim: 'rgba(200, 221, 232, 0.08)',

  // Foreground
  fg: '#c8dde8',
  fgDim: '#8ba4b8',
  fgFaint: '#5e7387',

  // Accent palette
  teal: '#5aadaf',
  tealDim: 'rgba(90, 173, 175, 0.18)',
  blue: '#5b8ab8',
  blueDim: 'rgba(91, 138, 184, 0.18)',
  olive: '#b8c84a',
  oliveDim: 'rgba(184, 200, 74, 0.18)',
  mint: '#62c4bc',
  rust: '#c87a4a',
  rustDim: 'rgba(200, 122, 74, 0.18)',

  // Font stacks (CSS variable references from Next.js font loading)
  mono: "var(--font-jetbrains-mono, 'JetBrains Mono'), ui-monospace, 'SF Mono', Menlo, monospace",
  serif: "var(--font-dm-serif, 'DM Serif Display'), 'Iowan Old Style', Georgia, serif",
  sans: "var(--font-dm-sans, 'DM Sans'), -apple-system, system-ui, sans-serif",

  /** Badge tinted background: appends 18 hex (~9% opacity) to a hex color. */
  tintBg: (color: string) => `${color}18`,

  // Investigation status colors
  statusColor: (status: string | null | undefined): string => {
    const map: Record<string, string> = {
      active: '#5aadaf',
      completed: '#5b8ab8',
      paused: '#b8c84a',
      archived: '#5e7387',
      evaluating: '#62c4bc',
      synthesis: '#5b8ab8',
      done: '#5aadaf',
      scoping: '#b8c84a',
    };
    return map[(status || '').toLowerCase()] || '#5e7387';
  },

  // System status colors
  systemStatusColor: (status: string | null | undefined): string => {
    const map: Record<string, string> = {
      candidate: '#8ba4b8',
      confirmed: '#5b8ab8',
      ingested: '#b8c84a',
      analyzed: '#5aadaf',
      excluded: '#5e7387',
    };
    return map[(status || '').toLowerCase()] || '#5e7387';
  },

  // Artifact type colors
  artifactTypeColor: (type: string | null | undefined): string => {
    const map: Record<string, string> = {
      documentation: '#5b8ab8',
      'source-code': '#5aadaf',
      'api-response': '#b8c84a',
      screenshot: '#8ba4b8',
      config: '#5aadaf',
      analysis: '#5b8ab8',
      webpage: '#c87a4a',
      'source-file': '#5aadaf',
      'repo-clone': '#62c4bc',
      'file-tree': '#b8c84a',
      directory: '#5b8ab8',
    };
    return map[(type || '').toLowerCase()] || '#5e7387';
  },

  // Note format colors
  formatColor: (format: string | null | undefined): string => {
    const map: Record<string, string> = {
      md: '#5b8ab8',
      markdown: '#5b8ab8',
      yaml: '#5aadaf',
      json: '#b8c84a',
      html: '#c87a4a',
      text: '#8ba4b8',
      pdf: '#c87a4a',
    };
    return map[(format || '').toLowerCase()] || '#5e7387';
  },

  // Analysis type colors
  analysisTypeColor: (type: string | null | undefined): string => {
    const map: Record<string, string> = {
      comparison: '#5b8ab8',
      trend: '#8ba4b8',
      distribution: '#b8c84a',
      ranking: '#5aadaf',
      plot: '#5aadaf',
      table: '#b8c84a',
      prose: '#5b8ab8',
    };
    return map[(type || '').toLowerCase()] || '#5e7387';
  },

  // Language colors
  languageColor: (lang: string | null | undefined): string => {
    const map: Record<string, string> = {
      python: '#5b8ab8',
      typescript: '#5aadaf',
      javascript: '#b8c84a',
      rust: '#c87a4a',
      go: '#5b8ab8',
      java: '#c87a4a',
    };
    return map[(lang || '').toLowerCase()] || '#8ba4b8';
  },

  // Note topic config for timeline display
  topicConfig: (topic: string | null | undefined): { label: string; short: string; color: string; icon: string } => {
    const map: Record<string, { label: string; short: string; color: string; icon: string }> = {
      architecture: { label: 'Architecture', short: 'ARCH', color: '#5aadaf', icon: 'code' },
      api: { label: 'API', short: 'API', color: '#5b8ab8', icon: 'link' },
      'data-model': { label: 'Data model', short: 'DATA', color: '#b8c84a', icon: 'graph' },
      assessment: { label: 'Assessment', short: 'EVAL', color: '#62c4bc', icon: 'target' },
      'context-storage': { label: 'Context', short: 'CTX', color: '#8ba4b8', icon: 'square' },
      integration: { label: 'Integration', short: 'INTG', color: '#c87a4a', icon: 'share' },
      'synthesis-report': { label: 'Synthesis', short: 'SYN', color: '#5aadaf', icon: 'doc' },
      'completion-assessment': { label: 'Completion', short: 'DONE', color: '#b8c84a', icon: 'check' },
      'viz-plan': { label: 'Viz plan', short: 'VIZ', color: '#5b8ab8', icon: 'bar-chart' },
      fragments: { label: 'Fragments', short: 'FRAG', color: '#5e7387', icon: 'code' },
    };
    const key = (topic || '').toLowerCase();
    return map[key] || { label: topic || 'note', short: 'NOTE', color: '#8ba4b8', icon: 'sticky-note' };
  },
  // Investigation type config (reads from type prompt frontmatter values)
  investigationTypeConfig: (type: string | null | undefined): { label: string; short: string; color: string; icon: string } => {
    const map: Record<string, { label: string; short: string; color: string; icon: string }> = {
      landscape:  { label: 'Landscape',  short: 'LAND',  color: '#5aadaf', icon: 'search' },
      evaluation: { label: 'Evaluation', short: 'EVAL',  color: '#62c4bc', icon: 'target' },
      question:   { label: 'Question',   short: 'QUES',  color: '#5b8ab8', icon: 'circle' },
      survey:     { label: 'Survey',     short: 'SURV',  color: '#b8c84a', icon: 'book' },
      monitor:    { label: 'Monitor',    short: 'MON',   color: '#c87a4a', icon: 'clock' },
      brief:      { label: 'Brief',      short: 'BRIEF', color: '#8ba4b8', icon: 'doc' },
    };
    const key = (type || '').toLowerCase();
    return map[key] || { label: 'Recon', short: 'RECON', color: '#5aadaf', icon: 'search' };
  },
} as const;
