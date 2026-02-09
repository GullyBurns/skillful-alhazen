'use client';

import { useState, useEffect, use } from 'react';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import {
  ArrowLeft,
  Building2,
  MapPin,
  DollarSign,
  ExternalLink,
  RefreshCw,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Calendar,
  User,
  FileText,
  Target,
  MessageSquare,
  Lightbulb,
} from 'lucide-react';

// Helper to extract value from TypeDB fetch result
function getValue(attr: Array<{ value: unknown }> | undefined): string | null {
  if (!attr || attr.length === 0) return null;
  const val = String(attr[0].value);
  // Unescape newlines that may have been escaped during JSON serialization
  return val.replace(/\\n/g, '\n').replace(/\\t/g, '\t');
}

function getNumber(attr: Array<{ value: unknown }> | undefined): number | null {
  if (!attr || attr.length === 0) return null;
  return Number(attr[0].value);
}

// Note type icons
const NOTE_ICONS: Record<string, React.ReactNode> = {
  'fit-analysis': <Target className="w-4 h-4" />,
  'strategy': <Lightbulb className="w-4 h-4" />,
  'interaction': <User className="w-4 h-4" />,
  'research': <FileText className="w-4 h-4" />,
  'interview': <MessageSquare className="w-4 h-4" />,
  'skill-gap': <AlertCircle className="w-4 h-4" />,
};

const PRIORITY_COLORS: Record<string, string> = {
  high: 'bg-red-500/20 text-red-400 border-red-500/30',
  medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  low: 'bg-green-500/20 text-green-400 border-green-500/30',
};

const STATUS_COLORS: Record<string, string> = {
  researching: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
  applied: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  'phone-screen': 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  interviewing: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  offer: 'bg-green-500/20 text-green-400 border-green-500/30',
  rejected: 'bg-red-500/20 text-red-400 border-red-500/30',
  withdrawn: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
};

interface PositionPageProps {
  params: Promise<{ id: string }>;
}

export default function PositionPage({ params }: PositionPageProps) {
  const { id } = use(params);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchPosition() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`/api/jobhunt/position/${id}`);
        if (!res.ok) throw new Error('Failed to fetch position');
        const json = await res.json();
        setData(json);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    }
    fetchPosition();
  }, [id]);

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <RefreshCw className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-background p-8">
        <Link href="/">
          <Button variant="ghost" className="mb-4">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Dashboard
          </Button>
        </Link>
        <div className="bg-destructive/10 text-destructive px-4 py-3 rounded-lg">
          <strong>Error:</strong> {error || 'Position not found'}
        </div>
      </div>
    );
  }

  const position = data.position;
  const company = data.company;
  const notes = data.notes || [];
  const requirements = data.requirements || [];
  const jobDescription = data.job_description;
  const tags = data.tags || [];

  // Extract position fields
  const title = getValue(position?.name) || 'Unknown Position';
  const url = getValue(position?.['job-url']);
  const location = getValue(position?.location);
  const salary = getValue(position?.['salary-range']);
  const remotePolicy = getValue(position?.['remote-policy']);
  const priority = getValue(position?.['priority-level']);

  // Extract company fields
  const companyName = getValue(company?.name);
  const companyUrl = getValue(company?.['company-url']);
  const companyDescription = getValue(company?.description);

  // Find status from notes
  const statusNote = notes.find(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (n: any) => n.type?.label === 'jobhunt-application-note'
  );
  const status = getValue(statusNote?.['application-status']) || 'researching';

  // Find fit analysis note
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fitNote = notes.find((n: any) =>
    n.type?.label === 'jobhunt-fit-analysis-note'
  );
  const fitScore = getNumber(fitNote?.['fit-score']);
  const fitSummary = getValue(fitNote?.['fit-summary']);

  // Group other notes by type
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const groupedNotes = notes.reduce((acc: Record<string, any[]>, note: any) => {
    const type = note.type?.label?.replace('jobhunt-', '').replace('-note', '') || 'general';
    if (type !== 'application' && type !== 'fit-analysis') {
      if (!acc[type]) acc[type] = [];
      acc[type].push(note);
    }
    return acc;
  }, {});

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-border/50 bg-card/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          <Link href="/">
            <Button variant="ghost" size="sm" className="mb-2 hover:bg-primary/10">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Dashboard
            </Button>
          </Link>
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">{title}</h1>
              {companyName && (
                <div className="flex items-center gap-2 text-muted-foreground mt-1">
                  <Building2 className="w-4 h-4" />
                  <span>{companyName}</span>
                  {companyUrl && (
                    <a
                      href={companyUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline"
                    >
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
              )}
            </div>
            <div className="flex items-center gap-2">
              {priority && (
                <Badge className={PRIORITY_COLORS[priority]}>
                  {priority} priority
                </Badge>
              )}
              <Badge className={STATUS_COLORS[status]}>
                {status.replace('-', ' ')}
              </Badge>
              {url && (
                <a href={url} target="_blank" rel="noopener noreferrer">
                  <Button variant="outline" size="sm">
                    <ExternalLink className="w-4 h-4 mr-2" />
                    View Posting
                  </Button>
                </a>
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6 space-y-6">
        {/* Quick Info */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {location && (
            <Card>
              <CardContent className="p-4 flex items-center gap-3">
                <MapPin className="w-5 h-5 text-muted-foreground" />
                <div>
                  <p className="text-xs text-muted-foreground">Location</p>
                  <p className="font-medium">{location}</p>
                </div>
              </CardContent>
            </Card>
          )}
          {salary && (
            <Card>
              <CardContent className="p-4 flex items-center gap-3">
                <DollarSign className="w-5 h-5 text-muted-foreground" />
                <div>
                  <p className="text-xs text-muted-foreground">Salary</p>
                  <p className="font-medium">{salary}</p>
                </div>
              </CardContent>
            </Card>
          )}
          {remotePolicy && (
            <Card>
              <CardContent className="p-4 flex items-center gap-3">
                <Building2 className="w-5 h-5 text-muted-foreground" />
                <div>
                  <p className="text-xs text-muted-foreground">Remote Policy</p>
                  <p className="font-medium">{remotePolicy}</p>
                </div>
              </CardContent>
            </Card>
          )}
          {fitScore !== null && (
            <Card>
              <CardContent className="p-4 flex items-center gap-3">
                <Target className="w-5 h-5 text-muted-foreground" />
                <div>
                  <p className="text-xs text-muted-foreground">Fit Score</p>
                  <p className="font-medium text-lg">{Math.round(fitScore * 100)}%</p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Tags */}
        {tags.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm text-muted-foreground">Tags:</span>
            {tags.map((tag: string) => (
              <Badge key={tag} variant="outline">
                {tag}
              </Badge>
            ))}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Fit Analysis & Requirements */}
          <div className="lg:col-span-2 space-y-6">
            {/* Fit Analysis */}
            {fitNote && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Target className="w-5 h-5" />
                    Fit Analysis
                    {fitScore !== null && (
                      <Badge variant="outline" className="ml-auto">
                        {Math.round(fitScore * 100)}%
                      </Badge>
                    )}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {fitSummary && (
                    <p className="text-sm font-medium mb-4">{fitSummary}</p>
                  )}
                  {getValue(fitNote?.content) && (
                    <div className="prose prose-sm max-w-none dark:prose-invert">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {getValue(fitNote?.content) || ''}
                      </ReactMarkdown>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Requirements */}
            {requirements.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Requirements ({requirements.length})</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                    {requirements.map((req: any, idx: number) => {
                      const skill = getValue(req['skill-name']);
                      const level = getValue(req['requirement-level']);
                      const yourLevel = getValue(req['your-level']);
                      const content = getValue(req.content);

                      const match =
                        yourLevel === 'strong'
                          ? 'match'
                          : yourLevel === 'some' || yourLevel === 'learning'
                          ? 'partial'
                          : 'gap';

                      return (
                        <div
                          key={idx}
                          className="flex items-start gap-3 p-3 rounded-lg bg-muted/50"
                        >
                          {match === 'match' && (
                            <CheckCircle2 className="w-5 h-5 text-green-500 mt-0.5" />
                          )}
                          {match === 'partial' && (
                            <AlertCircle className="w-5 h-5 text-yellow-500 mt-0.5" />
                          )}
                          {match === 'gap' && (
                            <XCircle className="w-5 h-5 text-red-500 mt-0.5" />
                          )}
                          <div className="flex-1">
                            <div className="flex items-center gap-2">
                              <span className="font-medium">{skill}</span>
                              <Badge variant="outline" className="text-xs">
                                {level}
                              </Badge>
                              {yourLevel && (
                                <Badge variant="secondary" className="text-xs">
                                  You: {yourLevel}
                                </Badge>
                              )}
                            </div>
                            {content && (
                              <p className="text-sm text-muted-foreground mt-1">
                                {content}
                              </p>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Company Info */}
            {company && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Building2 className="w-5 h-5" />
                    About {companyName}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {companyDescription && (
                    <p className="text-sm">{companyDescription}</p>
                  )}
                  {companyUrl && (
                    <a
                      href={companyUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline text-sm flex items-center gap-1 mt-2"
                    >
                      <ExternalLink className="w-3 h-3" />
                      {companyUrl}
                    </a>
                  )}
                </CardContent>
              </Card>
            )}
          </div>

          {/* Right Column - Notes */}
          <div className="space-y-6">
            {/* Notes by Type */}
            {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
            {(Object.entries(groupedNotes) as [string, any[]][]).map(([type, typeNotes]) => (
              <Card key={type}>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm flex items-center gap-2 capitalize">
                    {NOTE_ICONS[type] || <FileText className="w-4 h-4" />}
                    {type.replace('-', ' ')} Notes
                    <Badge variant="secondary" className="ml-auto">
                      {typeNotes.length}
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                  {typeNotes.map((note: any, idx: number) => {
                    const content = getValue(note.content);
                    const createdAt = getValue(note['created-at']);
                    const interactionType = getValue(note['interaction-type']);
                    const interactionDate = getValue(note['interaction-date']);

                    return (
                      <div key={idx} className="text-sm">
                        {(interactionType || interactionDate) && (
                          <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
                            {interactionType && (
                              <Badge variant="outline" className="text-xs">
                                {interactionType}
                              </Badge>
                            )}
                            {interactionDate && (
                              <span className="flex items-center gap-1">
                                <Calendar className="w-3 h-3" />
                                {interactionDate}
                              </span>
                            )}
                          </div>
                        )}
                        <div className="prose prose-sm max-w-none dark:prose-invert">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {content || ''}
                          </ReactMarkdown>
                        </div>
                        {createdAt && (
                          <p className="text-xs text-muted-foreground mt-1">
                            {new Date(createdAt).toLocaleDateString()}
                          </p>
                        )}
                        {idx < typeNotes.length - 1 && (
                          <Separator className="mt-3" />
                        )}
                      </div>
                    );
                  })}
                </CardContent>
              </Card>
            ))}

            {/* Raw Job Description */}
            {jobDescription && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <FileText className="w-4 h-4" />
                    Job Description
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <details className="text-sm">
                    <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                      View raw content
                    </summary>
                    <pre className="mt-2 whitespace-pre-wrap text-xs bg-muted p-3 rounded-lg overflow-auto max-h-96">
                      {getValue(jobDescription.content)}
                    </pre>
                  </details>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
