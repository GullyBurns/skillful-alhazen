'use client';

import { useState, useEffect, useCallback } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { PipelineBoard } from '@/components/pipeline-board';
import { SkillsMatrix } from '@/components/skills-matrix';
import { LearningPlan } from '@/components/learning-plan';
import { StatsOverview } from '@/components/stats-overview';
import {
  RefreshCw,
  Kanban,
  GraduationCap,
  Target,
  Filter,
} from 'lucide-react';

interface Position {
  id: string;
  title: string;
  company: string;
  url: string;
  location: string;
  remote_policy: string;
  salary: string;
  priority: string;
  status: string;
}

interface SkillGap {
  skill: string;
  level: string;
  your_level: string;
  positions: { id: string; title: string }[];
}

interface LearningResource {
  id: string;
  name: string;
  type: string;
  url: string;
  hours: number;
  status: string;
}

export default function Dashboard() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [skillGaps, setSkillGaps] = useState<SkillGap[]>([]);
  const [learningResources, setLearningResources] = useState<LearningResource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [priorityFilter, setPriorityFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      // Build query params
      const params = new URLSearchParams();
      if (priorityFilter !== 'all') params.set('priority', priorityFilter);
      if (statusFilter !== 'all') params.set('status', statusFilter);

      // Fetch all data in parallel
      const [pipelineRes, gapsRes, learningRes] = await Promise.all([
        fetch(`/api/jobhunt/pipeline?${params}`),
        fetch(`/api/jobhunt/gaps?${params}`),
        fetch('/api/jobhunt/learning'),
      ]);

      if (!pipelineRes.ok || !gapsRes.ok || !learningRes.ok) {
        throw new Error('Failed to fetch data');
      }

      const [pipelineData, gapsData, learningData] = await Promise.all([
        pipelineRes.json(),
        gapsRes.json(),
        learningRes.json(),
      ]);

      setPositions(pipelineData.positions || []);
      setSkillGaps(gapsData.skill_gaps || []);
      setLearningResources(learningData.learning_plan || []);
    } catch (err) {
      console.error('Fetch error:', err);
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [priorityFilter, statusFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleStatusChange = async (positionId: string, newStatus: string) => {
    try {
      const res = await fetch('/api/jobhunt/status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          positionId,
          status: newStatus,
          date: new Date().toISOString().split('T')[0],
        }),
      });

      if (res.ok) {
        // Refresh data
        fetchData();
      }
    } catch (err) {
      console.error('Status update error:', err);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold">Job Hunt Dashboard</h1>
              <p className="text-sm text-muted-foreground">
                Track your applications, skills, and learning progress
              </p>
            </div>
            <div className="flex items-center gap-4">
              <Badge variant="outline" className="text-xs">
                TypeDB Connected
              </Badge>
              <Button
                variant="outline"
                size="sm"
                onClick={fetchData}
                disabled={loading}
              >
                <RefreshCw
                  className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`}
                />
                Refresh
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6 space-y-6">
        {/* Error Alert */}
        {error && (
          <div className="bg-destructive/10 text-destructive px-4 py-3 rounded-lg">
            <strong>Error:</strong> {error}
            <p className="text-sm mt-1">
              Make sure TypeDB is running and the jobhunt skill is configured.
            </p>
          </div>
        )}

        {/* Stats Overview */}
        <StatsOverview positions={positions} />

        {/* Filters */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">Filters:</span>
          </div>
          <Select value={priorityFilter} onValueChange={setPriorityFilter}>
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder="Priority" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Priorities</SelectItem>
              <SelectItem value="high">High</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="low">Low</SelectItem>
            </SelectContent>
          </Select>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-[160px]">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Statuses</SelectItem>
              <SelectItem value="researching">Researching</SelectItem>
              <SelectItem value="applied">Applied</SelectItem>
              <SelectItem value="phone-screen">Phone Screen</SelectItem>
              <SelectItem value="interviewing">Interviewing</SelectItem>
              <SelectItem value="offer">Offer</SelectItem>
              <SelectItem value="rejected">Rejected</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Main Content Tabs */}
        <Tabs defaultValue="pipeline" className="space-y-4">
          <TabsList>
            <TabsTrigger value="pipeline" className="flex items-center gap-2">
              <Kanban className="w-4 h-4" />
              Pipeline
            </TabsTrigger>
            <TabsTrigger value="skills" className="flex items-center gap-2">
              <Target className="w-4 h-4" />
              Skills Matrix
            </TabsTrigger>
            <TabsTrigger value="learning" className="flex items-center gap-2">
              <GraduationCap className="w-4 h-4" />
              Learning Plan
            </TabsTrigger>
          </TabsList>

          <TabsContent value="pipeline">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <PipelineBoard
                positions={positions}
                onStatusChange={handleStatusChange}
              />
            )}
          </TabsContent>

          <TabsContent value="skills">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <SkillsMatrix gaps={skillGaps} />
            )}
          </TabsContent>

          <TabsContent value="learning">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <LearningPlan resources={learningResources} />
            )}
          </TabsContent>
        </Tabs>
      </main>

      {/* Footer */}
      <footer className="border-t mt-8">
        <div className="container mx-auto px-4 py-4">
          <p className="text-xs text-muted-foreground text-center">
            Job Hunt Dashboard • Powered by TypeDB + Next.js
          </p>
        </div>
      </footer>
    </div>
  );
}
