'use client';

import { ExternalLink, Check } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { TechReconSystem, SystemData } from '@/lib/tech-recon';

// Note topics we want to show as checkmarks in the grid
const TRACKED_TOPICS = ['architecture', 'api', 'data-model', 'assessment', 'context-storage', 'integration'];

interface SystemsTableProps {
  systems: TechReconSystem[];
  systemDataMap: Record<string, SystemData>;
}

export function SystemsTable({ systems, systemDataMap }: SystemsTableProps) {
  // Compute which topics are covered per system
  const topicsBySys: Record<string, Set<string>> = {};
  systems.forEach(s => {
    const notes = systemDataMap[s.id]?.notes ?? [];
    topicsBySys[s.id] = new Set(notes.map(n => n.topic?.toLowerCase()).filter(Boolean) as string[]);
  });

  // Find which tracked topics actually appear in the data
  const presentTopics = TRACKED_TOPICS.filter(t =>
    systems.some(s => topicsBySys[s.id]?.has(t))
  );

  return (
    <div className="space-y-3">
      <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
        Systems under investigation ({systems.length})
      </h2>
      <div className="overflow-x-auto rounded-lg border border-border/50">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border/50 bg-card/50">
              <th className="text-left px-3 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide">Name</th>
              <th className="text-left px-3 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide">Type</th>
              <th className="text-center px-3 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide">Artifacts</th>
              {presentTopics.map(t => (
                <th key={t} className="text-center px-4 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide whitespace-nowrap">
                  {t.replace(/-/g, ' ')}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {systems.map((s, idx) => {
              const topics = topicsBySys[s.id] ?? new Set();
              const isShallow = (s.artifacts_count ?? 0) < 3 && (s.artifacts_count ?? 0) > 0;
              return (
                <tr key={s.id} className={`border-b last:border-b-0 border-border/40 hover:bg-accent/10 transition-colors ${idx % 2 === 0 ? '' : 'bg-card/20'}`}>
                  <td className="px-3 py-2.5 font-medium text-foreground">{s.name}</td>
                  <td className="px-3 py-2.5">
                    {s.language && (
                      <Badge className="text-xs bg-slate-500/20 text-slate-300 border-slate-500/30">{s.language}</Badge>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    <span className="flex items-center justify-center gap-1">
                      <span className={isShallow ? 'text-amber-400' : 'text-foreground'}>
                        {s.artifacts_count ?? 0}
                      </span>
                      {s.url && (
                        <a href={s.url} target="_blank" rel="noopener noreferrer"
                          className="text-cyan-400 hover:text-blue-400 transition-colors ml-1">
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </span>
                  </td>
                  {presentTopics.map(t => (
                    <td key={t} className="px-4 py-2.5 text-center">
                      {topics.has(t) && <Check className="w-3.5 h-3.5 text-green-400 mx-auto" />}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
