// Starry Night design tokens — shared with tech-recon dashboard
export const T = {
  bg: '#070d1c',
  bgRaised: '#0c1628',
  bgSunken: '#050a16',
  panel: 'rgba(12, 22, 40, 0.72)',
  panelHi: 'rgba(20, 34, 58, 0.85)',

  border: 'rgba(90, 173, 175, 0.18)',
  borderHi: 'rgba(90, 173, 175, 0.42)',
  borderDim: 'rgba(200, 221, 232, 0.08)',

  fg: '#c8dde8',
  fgDim: '#8ba4b8',
  fgFaint: '#5e7387',

  teal: '#5aadaf',
  tealDim: 'rgba(90, 173, 175, 0.18)',
  blue: '#5b8ab8',
  blueDim: 'rgba(91, 138, 184, 0.18)',
  olive: '#b8c84a',
  oliveDim: 'rgba(184, 200, 74, 0.18)',
  mint: '#62c4bc',
  mintDim: 'rgba(98, 196, 188, 0.18)',
  rust: '#c87a4a',
  rustDim: 'rgba(200, 122, 74, 0.18)',

  mono: "var(--font-jetbrains-mono, 'JetBrains Mono'), ui-monospace, 'SF Mono', Menlo, monospace",
  serif: "var(--font-dm-serif, 'DM Serif Display'), 'Iowan Old Style', Georgia, serif",
  sans: "var(--font-dm-sans, 'DM Sans'), -apple-system, system-ui, sans-serif",

  claimTypeColor: (type: string): string => {
    const map: Record<string, string> = {
      primary: '#62c4bc',
      secondary: '#5b8ab8',
      peripheral: '#b8c84a',
    };
    return map[type] || '#8ba4b8';
  },

  evidenceTypeColor: (type: string): string => {
    const map: Record<string, string> = {
      experimental: '#5aadaf',
      observational: '#5b8ab8',
      computational: '#b8c84a',
      review: '#8ba4b8',
      theoretical: '#c87a4a',
      anecdotal: '#5e7387',
    };
    return map[type] || '#8ba4b8';
  },

  impactTypeColor: (type: string): string => {
    const map: Record<string, string> = {
      supports: '#62c4bc',
      extends: '#5b8ab8',
      nuances: '#b8c84a',
      refutes: '#c87a4a',
      uses: '#8ba4b8',
      unrelated: '#5e7387',
    };
    return map[type] || '#8ba4b8';
  },

  statusColor: (status: string): string => {
    const map: Record<string, string> = {
      complete: '#62c4bc',
      'in-progress': '#5b8ab8',
      'scope-exhausted': '#b8c84a',
    };
    return map[status] || '#8ba4b8';
  },
} as const;
