import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Star, GitBranch, ExternalLink } from 'lucide-react';
import { MaturityBadge, LanguageBadge } from './badges';

interface System {
  id: string;
  name: string;
  repo_url?: string;
  language?: string;
  stars?: number;
  maturity?: string;
  created_at?: string;
}

interface SystemsGridProps {
  systems: System[];
}

export function SystemsGrid({ systems }: SystemsGridProps) {
  if (systems.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-4">No systems found.</p>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {systems.map((system) => (
        <Link key={system.id} href={`/techrecon/system/${system.id}`}>
          <Card className="hover:border-primary/50 transition-colors cursor-pointer h-full">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <span className="truncate">{system.name}</span>
                {system.repo_url && (
                  <ExternalLink className="w-3 h-3 text-muted-foreground shrink-0" />
                )}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="flex items-center gap-2 flex-wrap">
                {system.language && <LanguageBadge language={system.language} />}
                {system.maturity && <MaturityBadge maturity={system.maturity} />}
                {system.stars != null && system.stars > 0 && (
                  <span className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Star className="w-3 h-3" />
                    {system.stars.toLocaleString()}
                  </span>
                )}
                {system.created_at && (
                  <span className="flex items-center gap-1 text-xs text-muted-foreground ml-auto">
                    <GitBranch className="w-3 h-3" />
                    {new Date(system.created_at).toLocaleDateString()}
                  </span>
                )}
              </div>
            </CardContent>
          </Card>
        </Link>
      ))}
    </div>
  );
}
