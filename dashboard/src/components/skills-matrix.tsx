'use client';

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { CheckCircle, AlertCircle, XCircle, HelpCircle } from 'lucide-react';

interface SkillGap {
  skill: string;
  level: string;
  your_level: string;
  positions: { id: string; title: string }[];
}

interface SkillsMatrixProps {
  gaps: SkillGap[];
}

const LEVEL_ICONS: Record<string, React.ReactNode> = {
  strong: <CheckCircle className="w-4 h-4 text-green-500" />,
  some: <AlertCircle className="w-4 h-4 text-yellow-500" />,
  none: <XCircle className="w-4 h-4 text-red-500" />,
};

const LEVEL_COLORS: Record<string, string> = {
  required: 'bg-red-100 text-red-800',
  preferred: 'bg-yellow-100 text-yellow-800',
  'nice-to-have': 'bg-blue-100 text-blue-800',
};

export function SkillsMatrix({ gaps }: SkillsMatrixProps) {
  // Sort by number of positions (most needed first)
  const sortedGaps = [...gaps].sort(
    (a, b) => b.positions.length - a.positions.length
  );

  // Calculate coverage stats
  const totalGaps = gaps.length;
  const strongSkills = gaps.filter((g) => g.your_level === 'strong').length;
  const coveragePercent = totalGaps > 0 ? Math.round((strongSkills / totalGaps) * 100) : 0;

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="flex items-center gap-4 p-4 bg-muted rounded-lg">
        <div className="flex-1">
          <div className="text-sm font-medium mb-1">Skills Coverage</div>
          <Progress value={coveragePercent} className="h-2" />
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold">{coveragePercent}%</div>
          <div className="text-xs text-muted-foreground">
            {strongSkills} of {totalGaps} skills
          </div>
        </div>
      </div>

      {/* Skills Table */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Skill</TableHead>
            <TableHead>Required By</TableHead>
            <TableHead>Level</TableHead>
            <TableHead>Your Level</TableHead>
            <TableHead>Positions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sortedGaps.map((gap) => (
            <TableRow key={gap.skill}>
              <TableCell className="font-medium">{gap.skill}</TableCell>
              <TableCell>
                <Badge variant="secondary">{gap.positions.length}</Badge>
              </TableCell>
              <TableCell>
                {gap.level && (
                  <Badge className={LEVEL_COLORS[gap.level] || ''}>
                    {gap.level}
                  </Badge>
                )}
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-2">
                  {gap.your_level ? (
                    <>
                      {LEVEL_ICONS[gap.your_level] || (
                        <HelpCircle className="w-4 h-4 text-gray-400" />
                      )}
                      <span className="capitalize">{gap.your_level}</span>
                    </>
                  ) : (
                    <>
                      <HelpCircle className="w-4 h-4 text-gray-400" />
                      <span className="text-muted-foreground">Unknown</span>
                    </>
                  )}
                </div>
              </TableCell>
              <TableCell>
                <div className="flex flex-wrap gap-1">
                  {gap.positions.slice(0, 3).map((pos) => (
                    <Badge key={pos.id} variant="outline" className="text-xs">
                      {pos.title.slice(0, 20)}
                      {pos.title.length > 20 ? '...' : ''}
                    </Badge>
                  ))}
                  {gap.positions.length > 3 && (
                    <Badge variant="outline" className="text-xs">
                      +{gap.positions.length - 3} more
                    </Badge>
                  )}
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {sortedGaps.length === 0 && (
        <div className="text-center py-8 text-muted-foreground">
          No skill requirements found. Add requirements to positions to see the matrix.
        </div>
      )}
    </div>
  );
}
