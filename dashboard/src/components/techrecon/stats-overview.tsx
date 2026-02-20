import { Card, CardContent } from '@/components/ui/card';
import {
  Server,
  Puzzle,
  Lightbulb,
  FileText,
  StickyNote,
  Search,
} from 'lucide-react';

interface StatsOverviewProps {
  systems: number;
  components: number;
  concepts: number;
  artifacts: number;
  notes: number;
  investigations: number;
}

const STAT_ITEMS = [
  { key: 'systems', label: 'Systems', icon: Server, color: 'text-blue-400' },
  { key: 'components', label: 'Components', icon: Puzzle, color: 'text-purple-400' },
  { key: 'concepts', label: 'Concepts', icon: Lightbulb, color: 'text-amber-400' },
  { key: 'artifacts', label: 'Artifacts', icon: FileText, color: 'text-green-400' },
  { key: 'notes', label: 'Notes', icon: StickyNote, color: 'text-cyan-400' },
  { key: 'investigations', label: 'Investigations', icon: Search, color: 'text-orange-400' },
] as const;

export function StatsOverview(props: StatsOverviewProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      {STAT_ITEMS.map(({ key, label, icon: Icon, color }) => (
        <Card key={key}>
          <CardContent className="p-4 flex items-center gap-3">
            <Icon className={`w-5 h-5 ${color}`} />
            <div>
              <p className="text-2xl font-bold">{props[key]}</p>
              <p className="text-xs text-muted-foreground">{label}</p>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
