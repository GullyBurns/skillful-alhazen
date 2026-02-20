import { Badge } from '@/components/ui/badge';

const MATURITY_COLORS: Record<string, string> = {
  production: 'bg-green-500/20 text-green-400 border-green-500/30',
  mature: 'bg-green-500/20 text-green-400 border-green-500/30',
  beta: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  alpha: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  experimental: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  deprecated: 'bg-red-500/20 text-red-400 border-red-500/30',
};

const CATEGORY_COLORS: Record<string, string> = {
  architecture: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  protocol: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  'data-model': 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  algorithm: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  standard: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  pattern: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
};

const FORMAT_COLORS: Record<string, string> = {
  json: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  yaml: 'bg-green-500/20 text-green-400 border-green-500/30',
  graphql: 'bg-pink-500/20 text-pink-400 border-pink-500/30',
  sql: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  protobuf: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  openapi: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
};

const TYPE_COLORS: Record<string, string> = {
  documentation: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  'source-code': 'bg-green-500/20 text-green-400 border-green-500/30',
  'api-response': 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  screenshot: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  config: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  analysis: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
  investigation: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
};

function getBadgeColor(map: Record<string, string>, value: string): string {
  return map[value.toLowerCase()] || 'bg-slate-500/20 text-slate-300 border-slate-500/30';
}

export function MaturityBadge({ maturity }: { maturity: string }) {
  return (
    <Badge className={getBadgeColor(MATURITY_COLORS, maturity)}>
      {maturity}
    </Badge>
  );
}

export function CategoryBadge({ category }: { category: string }) {
  return (
    <Badge className={getBadgeColor(CATEGORY_COLORS, category)}>
      {category}
    </Badge>
  );
}

export function FormatBadge({ format }: { format: string }) {
  return (
    <Badge className={getBadgeColor(FORMAT_COLORS, format)}>
      {format}
    </Badge>
  );
}

export function TypeBadge({ type }: { type: string }) {
  return (
    <Badge className={getBadgeColor(TYPE_COLORS, type)}>
      {type}
    </Badge>
  );
}

export function LanguageBadge({ language }: { language: string }) {
  return (
    <Badge variant="outline" className="text-xs">
      {language}
    </Badge>
  );
}
