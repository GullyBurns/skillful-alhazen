'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import {
  Book,
  Video,
  Code,
  FileText,
  GraduationCap,
  ExternalLink,
  Clock,
  CheckCircle,
  PlayCircle,
  Circle,
} from 'lucide-react';

interface LearningResource {
  id: string;
  name: string;
  type: string;
  url: string;
  hours: number;
  status: string;
}

interface LearningPlanProps {
  resources: LearningResource[];
}

const TYPE_ICONS: Record<string, React.ReactNode> = {
  book: <Book className="w-4 h-4" />,
  video: <Video className="w-4 h-4" />,
  course: <GraduationCap className="w-4 h-4" />,
  tutorial: <FileText className="w-4 h-4" />,
  project: <Code className="w-4 h-4" />,
};

const STATUS_ICONS: Record<string, React.ReactNode> = {
  completed: <CheckCircle className="w-4 h-4 text-green-500" />,
  'in-progress': <PlayCircle className="w-4 h-4 text-blue-500" />,
  'not-started': <Circle className="w-4 h-4 text-gray-400" />,
};

const STATUS_COLORS: Record<string, string> = {
  completed: 'bg-green-100 text-green-800',
  'in-progress': 'bg-blue-100 text-blue-800',
  'not-started': 'bg-gray-100 text-gray-800',
};

export function LearningPlan({ resources }: LearningPlanProps) {
  // Calculate stats
  const totalHours = resources.reduce((sum, r) => sum + (r.hours || 0), 0);
  const completed = resources.filter((r) => r.status === 'completed').length;
  const inProgress = resources.filter((r) => r.status === 'in-progress').length;
  const completedHours = resources
    .filter((r) => r.status === 'completed')
    .reduce((sum, r) => sum + (r.hours || 0), 0);

  const progressPercent = totalHours > 0 ? Math.round((completedHours / totalHours) * 100) : 0;

  // Group by type
  const byType = resources.reduce((acc, r) => {
    const type = r.type || 'other';
    if (!acc[type]) acc[type] = [];
    acc[type].push(r);
    return acc;
  }, {} as Record<string, LearningResource[]>);

  return (
    <div className="space-y-6">
      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{resources.length}</div>
            <div className="text-sm text-muted-foreground">Total Resources</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{totalHours}h</div>
            <div className="text-sm text-muted-foreground">Estimated Time</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold text-green-600">{completed}</div>
            <div className="text-sm text-muted-foreground">Completed</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold text-blue-600">{inProgress}</div>
            <div className="text-sm text-muted-foreground">In Progress</div>
          </CardContent>
        </Card>
      </div>

      {/* Overall Progress */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Overall Progress</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <Progress value={progressPercent} className="flex-1" />
            <span className="text-sm font-medium">{progressPercent}%</span>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            {completedHours}h completed of {totalHours}h total
          </p>
        </CardContent>
      </Card>

      {/* Resources by Type */}
      {Object.entries(byType).map(([type, items]) => (
        <Card key={type}>
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2">
              {TYPE_ICONS[type] || <FileText className="w-4 h-4" />}
              <span className="capitalize">{type}s</span>
              <Badge variant="secondary">{items.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {items.map((resource) => (
                <div
                  key={resource.id}
                  className="flex items-center justify-between p-3 bg-muted rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    {STATUS_ICONS[resource.status] || STATUS_ICONS['not-started']}
                    <div>
                      <div className="font-medium text-sm">{resource.name}</div>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        {resource.hours > 0 && (
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {resource.hours}h
                          </span>
                        )}
                        <Badge
                          variant="outline"
                          className={`text-xs ${STATUS_COLORS[resource.status] || ''}`}
                        >
                          {resource.status?.replace('-', ' ') || 'not started'}
                        </Badge>
                      </div>
                    </div>
                  </div>
                  {resource.url && (
                    <Button variant="ghost" size="sm" asChild>
                      <a
                        href={resource.url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        <ExternalLink className="w-4 h-4" />
                      </a>
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ))}

      {resources.length === 0 && (
        <Card>
          <CardContent className="py-8">
            <div className="text-center text-muted-foreground">
              <GraduationCap className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No learning resources added yet.</p>
              <p className="text-sm mt-1">
                Add resources to track your learning journey.
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
