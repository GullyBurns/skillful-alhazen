// Starry Night design tokens for the Agentic Memory dashboard

export const colors = {
  bg: '#070d1c',
  bgRaised: '#0c1628',
  bgSunken: '#050a16',
  panel: 'rgba(12, 22, 40, 0.72)',
  panelHi: 'rgba(20, 34, 58, 0.85)',
  fg: '#c8dde8',
  fgDim: '#8ba4b8',
  fgFaint: '#5e7387',
  border: 'rgba(90, 173, 175, 0.18)',
  borderHi: 'rgba(90, 173, 175, 0.42)',
  borderDim: 'rgba(200, 221, 232, 0.08)',
  teal: '#5aadaf',
  blue: '#5b8ab8',
  olive: '#b8c84a',
  mint: '#62c4bc',
  rust: '#c87a4a',
} as const;

export const namespaceColors: Record<string, string> = {
  alh: colors.teal,
  jhunt: colors.blue,
  trec: colors.olive,
  nbmem: colors.mint,
  slog: colors.rust,
  scilit: colors.fgDim,
  sltrend: colors.fgDim,
  dm: colors.fgDim,
  unknown: colors.fgFaint,
};

export const namespaceBadges: Record<string, string> = {
  alh: 'CORE',
  jhunt: 'SKILL',
  trec: 'SKILL',
  nbmem: 'OS',
  slog: 'OS',
  scilit: 'SKILL',
  sltrend: 'SKILL',
  dm: 'SKILL',
  unknown: 'LEGACY',
};

export function getNamespace(typeName: string): string {
  if (typeName.startsWith('alh-')) return 'alh';
  if (typeName.startsWith('jhunt-')) return 'jhunt';
  if (typeName.startsWith('trec-')) return 'trec';
  if (typeName.startsWith('nbmem-')) return 'nbmem';
  if (typeName.startsWith('slog-')) return 'slog';
  if (typeName.startsWith('scilit-')) return 'scilit';
  if (typeName.startsWith('sltrend-')) return 'sltrend';
  if (typeName.startsWith('dm-')) return 'dm';
  return 'unknown';
}

export function getNamespaceColor(namespace: string): string {
  return namespaceColors[namespace] ?? colors.fgFaint;
}

export function getNamespaceColorRgba(namespace: string, alpha: number): string {
  const hex = getNamespaceColor(namespace);
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export function stripPrefix(typeName: string): string {
  const ns = getNamespace(typeName);
  if (ns === 'unknown') return typeName;
  return typeName.slice(ns.length + 1);
}

export function formatRelativeDate(isoDate: string): string {
  const now = new Date();
  const date = new Date(isoDate);
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return 'today';
  if (diffDays === 1) return '1d ago';
  if (diffDays < 30) return `${diffDays}d ago`;
  if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`;
  return `${Math.floor(diffDays / 365)}y ago`;
}

export function formatShortDate(isoDate: string): string {
  const date = new Date(isoDate);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export function formatTime(isoDate: string): string {
  const date = new Date(isoDate);
  return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
}

export function formatMonthYear(isoDate: string): string {
  const date = new Date(isoDate);
  return date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
}
