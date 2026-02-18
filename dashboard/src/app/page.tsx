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
import { LearningPlan, LearningCollection } from '@/components/learning-plan';
import { StatsOverview } from '@/components/stats-overview';
import { CandidatesTable, Candidate } from '@/components/candidates-table';
import {
  RefreshCw,
  Kanban,
  GraduationCap,
  Target,
  Filter,
  ArrowLeft,
  Search,
  List,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

interface Position {
  id: string;
  title: string;
  short_name: string | null;
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

const ALL_TRIAGED_PAGE_SIZE = 25;

export default function Dashboard() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [skillGaps, setSkillGaps] = useState<SkillGap[]>([]);
  const [learningResources, setLearningResources] = useState<LearningResource[]>([]);
  const [learningCollections, setLearningCollections] = useState<LearningCollection[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [candidatesLoading, setCandidatesLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [priorityFilter, setPriorityFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [hubUrl, setHubUrl] = useState('#');

  // All Triaged state
  const [allTriaged, setAllTriaged] = useState<Candidate[]>([]);
  const [allTriagedLoading, setAllTriagedLoading] = useState(false);
  const [allTriagedPage, setAllTriagedPage] = useState(0);
  const [allTriagedTotal, setAllTriagedTotal] = useState(0);
  const [allTriagedLoaded, setAllTriagedLoaded] = useState(false);

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

      // Deduplicate collections: group by ID, aggregate skill names
      const rawCollections = learningData.collections || [];
      const collectionMap = new Map<string, LearningCollection>();
      for (const c of rawCollections) {
        const existing = collectionMap.get(c.id);
        if (existing) {
          if (c.skill_name && !existing.skills.includes(c.skill_name)) {
            existing.skills.push(c.skill_name);
          }
        } else {
          collectionMap.set(c.id, {
            id: c.id,
            name: c.name,
            description: c.description || '',
            skills: c.skill_name ? [c.skill_name] : [],
          });
        }
      }
      setLearningCollections(Array.from(collectionMap.values()));
    } catch (err) {
      console.error('Fetch error:', err);
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [priorityFilter, statusFilter]);

  const fetchCandidates = useCallback(async () => {
    setCandidatesLoading(true);
    try {
      const res = await fetch('/api/jobhunt/candidates?status=reviewed');
      if (!res.ok) throw new Error('Failed to fetch candidates');
      const data = await res.json();
      setCandidates(data.candidates || []);
    } catch (err) {
      console.error('Candidates fetch error:', err);
    } finally {
      setCandidatesLoading(false);
    }
  }, []);

  const fetchAllTriaged = useCallback(async (page: number) => {
    setAllTriagedLoading(true);
    try {
      const offset = page * ALL_TRIAGED_PAGE_SIZE;
      const res = await fetch(
        `/api/jobhunt/candidates?all_triaged=true&limit=${ALL_TRIAGED_PAGE_SIZE}&offset=${offset}`
      );
      if (!res.ok) throw new Error('Failed to fetch all triaged candidates');
      const data = await res.json();
      setAllTriaged(data.candidates || []);
      setAllTriagedTotal(data.total ?? (data.candidates || []).length);
      setAllTriagedPage(page);
      setAllTriagedLoaded(true);
    } catch (err) {
      console.error('All triaged fetch error:', err);
    } finally {
      setAllTriagedLoading(false);
    }
  }, []);

  useEffect(() => {
    setHubUrl(`${window.location.protocol}//${window.location.hostname}:8080`);
  }, []);

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

  const handleCandidateAction = async (candidateId: string, action: 'promote' | 'dismiss') => {
    try {
      const res = await fetch('/api/jobhunt/candidates/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ candidateId, action }),
      });

      if (res.ok) {
        // Optimistic removal from reviewed list
        setCandidates((prev) => prev.filter((c) => c.id !== candidateId));
        // If promoted, refresh pipeline to show new position
        if (action === 'promote') {
          fetchData();
        }
      }
    } catch (err) {
      console.error('Candidate action error:', err);
    }
  };

  const handlePromote = async (id: string) => {
    await handleCandidateAction(id, 'promote');
  };

  const handleDismiss = async (id: string) => {
    await handleCandidateAction(id, 'dismiss');
  };

  const handleTabChange = (value: string) => {
    if (value === 'candidates' && candidates.length === 0) {
      fetchCandidates();
    }
    if (value === 'all-triaged' && !allTriagedLoaded) {
      fetchAllTriaged(0);
    }
  };

  const totalPages = Math.max(1, Math.ceil(allTriagedTotal / ALL_TRIAGED_PAGE_SIZE));

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-border/50 bg-card/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <a
                href={hubUrl}
                className="flex items-center gap-2 text-sm text-muted-foreground hover:text-primary transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                Hub
              </a>
              <div>
                <h1 className="text-2xl font-bold bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">
                  Job Hunt Dashboard
                </h1>
                <p className="text-sm text-muted-foreground">
                  Track your applications, skills, and learning progress
                </p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <Badge variant="outline" className="text-xs border-primary/30 text-primary">
                TypeDB Connected
              </Badge>
              <Button
                variant="outline"
                size="sm"
                onClick={fetchData}
                disabled={loading}
                className="border-border/50 hover:border-primary/50 hover:bg-primary/10"
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
        <Tabs defaultValue="pipeline" className="space-y-4" onValueChange={handleTabChange}>
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
            <TabsTrigger value="candidates" className="flex items-center gap-2">
              <Search className="w-4 h-4" />
              Candidates
            </TabsTrigger>
            <TabsTrigger value="all-triaged" className="flex items-center gap-2">
              <List className="w-4 h-4" />
              All Triaged
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
              <LearningPlan resources={learningResources} collections={learningCollections} />
            )}
          </TabsContent>

          <TabsContent value="candidates">
            {candidatesLoading ? (
              <div className="flex items-center justify-center py-12">
                <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <CandidatesTable
                candidates={candidates}
                onPromote={handlePromote}
                onDismiss={handleDismiss}
              />
            )}
          </TabsContent>

          <TabsContent value="all-triaged">
            {allTriagedLoading ? (
              <div className="flex items-center justify-center py-12">
                <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <div className="space-y-4">
                <CandidatesTable candidates={allTriaged} />
                {/* Pagination Controls */}
                {allTriagedLoaded && (
                  <div className="flex items-center justify-center gap-4 py-4">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => fetchAllTriaged(allTriagedPage - 1)}
                      disabled={allTriagedPage === 0 || allTriagedLoading}
                    >
                      <ChevronLeft className="w-4 h-4 mr-1" />
                      Prev
                    </Button>
                    <span className="text-sm text-muted-foreground">
                      Page {allTriagedPage + 1} of {totalPages}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => fetchAllTriaged(allTriagedPage + 1)}
                      disabled={allTriagedPage + 1 >= totalPages || allTriagedLoading}
                    >
                      Next
                      <ChevronRight className="w-4 h-4 ml-1" />
                    </Button>
                  </div>
                )}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </main>

      {/* Footer */}
      <footer className="border-t border-border/50 mt-8">
        <div className="container mx-auto px-4 py-4">
          <p className="text-xs text-muted-foreground text-center">
            Job Hunt Dashboard • Powered by TypeDB + Next.js
          </p>
        </div>
      </footer>
    </div>
  );
}
