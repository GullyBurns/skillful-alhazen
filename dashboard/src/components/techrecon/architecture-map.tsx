import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Puzzle } from 'lucide-react';
import { CategoryBadge } from './badges';

interface ConceptLink {
  component_id: string;
  concept_id: string;
  concept_name: string;
  concept_category?: string;
}

interface Component {
  id: string;
  name: string;
  type?: string;
  role?: string;
  file_path?: string;
}

interface ComponentDep {
  from_id: string;
  to_id: string;
  to_name: string;
}

interface ArchitectureMapProps {
  components: Component[];
  conceptLinks: ConceptLink[];
  componentDependencies?: ComponentDep[];
}

export function ArchitectureMap({ components, conceptLinks, componentDependencies }: ArchitectureMapProps) {
  if (components.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-4">No components found.</p>
    );
  }

  // Build a map of component_id -> concepts
  const conceptsByComponent = new Map<string, ConceptLink[]>();
  for (const link of conceptLinks) {
    const existing = conceptsByComponent.get(link.component_id) || [];
    existing.push(link);
    conceptsByComponent.set(link.component_id, existing);
  }

  // Build a map of component_id -> dependencies
  const depsByComponent = new Map<string, ComponentDep[]>();
  for (const dep of componentDependencies || []) {
    const existing = depsByComponent.get(dep.from_id) || [];
    existing.push(dep);
    depsByComponent.set(dep.from_id, existing);
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {components.map((comp) => {
        const concepts = conceptsByComponent.get(comp.id) || [];
        const deps = depsByComponent.get(comp.id) || [];

        return (
          <Link key={comp.id} href={`/techrecon/component/${comp.id}`}>
            <Card className="hover:border-primary/50 transition-colors cursor-pointer h-full">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Puzzle className="w-4 h-4 text-purple-400 shrink-0" />
                  <span className="truncate">{comp.name}</span>
                </CardTitle>
                <div className="flex items-center gap-2 flex-wrap">
                  {comp.type && (
                    <Badge variant="outline" className="text-xs">
                      {comp.type}
                    </Badge>
                  )}
                  {comp.role && (
                    <span className="text-xs text-muted-foreground">{comp.role}</span>
                  )}
                </div>
              </CardHeader>
              <CardContent className="pt-0 space-y-2">
                {concepts.length > 0 && (
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {concepts.map((c) => (
                      <CategoryBadge key={c.concept_id} category={c.concept_category || c.concept_name} />
                    ))}
                  </div>
                )}
                {deps.length > 0 && (
                  <div className="text-xs text-muted-foreground">
                    Depends on: {deps.map((d) => d.to_name).join(', ')}
                  </div>
                )}
                {comp.file_path && (
                  <p className="text-xs text-muted-foreground font-mono truncate">
                    {comp.file_path}
                  </p>
                )}
              </CardContent>
            </Card>
          </Link>
        );
      })}
    </div>
  );
}
