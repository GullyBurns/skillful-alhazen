'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Briefcase, Database, Dna, Layers, Search, MessageSquareWarning } from 'lucide-react';

type ServiceStatus = 'checking' | 'online' | 'offline';

const STATUS_STYLES: Record<ServiceStatus, string> = {
  checking: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  online: 'bg-green-500/20 text-green-400 border-green-500/30',
  offline: 'bg-red-500/20 text-red-400 border-red-500/30',
};

export default function HubPage() {
  const [typedbStatus, setTypedbStatus] = useState<ServiceStatus>('checking');

  useEffect(() => {
    fetch('/api/typedb-status')
      .then(r => r.json())
      .then(d => setTypedbStatus(d.status === 'online' ? 'online' : 'offline'))
      .catch(() => setTypedbStatus('offline'));
  }, []);

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="py-16 flex justify-center">
        <div className="flex items-center gap-5">
          <Image src="/hero-icon.svg" alt="" width={72} height={72} />
          <div>
            <h1 className="text-4xl font-bold bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">
              Skillful-Alhazen
            </h1>
            <p className="text-muted-foreground mt-1 text-lg">
              AI-Powered Knowledge Curation System
            </p>
          </div>
        </div>
      </header>

      {/* Dashboard Cards */}
      <main className="container mx-auto px-4 flex-1">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 max-w-5xl mx-auto">
          {/* Job Hunt Dashboard */}
          <Link href="/jobhunt" className="group">
            <Card className="h-full transition-all hover:border-indigo-500/50 hover:-translate-y-1">
              <CardHeader>
                <CardTitle className="flex items-center gap-3">
                  <Briefcase className="w-6 h-6 text-indigo-400" />
                  Job Hunt Dashboard
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Track job applications, analyze skill gaps, and manage your learning plan.
                </p>
                <span className="text-sm text-primary mt-4 inline-block group-hover:underline">
                  Open Dashboard &rarr;
                </span>
              </CardContent>
            </Card>
          </Link>

          {/* TechRecon Dashboard */}
          <Link href="/techrecon" className="group">
            <Card className="h-full transition-all hover:border-cyan-500/50 hover:-translate-y-1">
              <CardHeader>
                <CardTitle className="flex items-center gap-3">
                  <Search className="w-6 h-6 text-cyan-400" />
                  Tech Recon Dashboard
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Systematically investigate software systems, libraries, and frameworks.
                </p>
                <span className="text-sm text-cyan-400 mt-4 inline-block group-hover:underline">
                  Open Dashboard &rarr;
                </span>
              </CardContent>
            </Card>
          </Link>

          {/* Disease Mechanism Dashboard */}
          <Link href="/apt" className="group">
            <Card className="h-full transition-all hover:border-teal-500/50 hover:-translate-y-1">
              <CardHeader>
                <CardTitle className="flex items-center gap-3">
                  <Dna className="w-6 h-6 text-teal-400" />
                  Disease Mechanism Dashboard
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Investigate rare disease mechanisms of harm and therapeutic strategies from MONDO diagnoses.
                </p>
                <span className="text-sm text-teal-400 mt-4 inline-block group-hover:underline">
                  Open Dashboard &rarr;
                </span>
              </CardContent>
            </Card>
          </Link>

          {/* Domain Modeling Dashboard */}
          <Link href="/domain-modeling" className="group">
            <Card className="h-full transition-all hover:border-violet-500/50 hover:-translate-y-1">
              <CardHeader>
                <CardTitle className="flex items-center gap-3">
                  <Layers className="w-6 h-6 text-violet-400" />
                  Domain Modeling
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Track skill design processes, decisions, gaps, and experiments across all knowledge domains.
                </p>
                <span className="text-sm text-violet-400 mt-4 inline-block group-hover:underline">
                  Open Dashboard &rarr;
                </span>
              </CardContent>
            </Card>
          </Link>

          {/* They Said Whaaa Dashboard */}
          <Link href="/they-said-whaaa" className="group">
            <Card className="h-full transition-all hover:border-orange-500/50 hover:-translate-y-1">
              <CardHeader>
                <CardTitle className="flex items-center gap-3">
                  <MessageSquareWarning className="w-6 h-6 text-orange-400" />
                  They Said Whaaa
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Track politician statements, detect contradictions, and assess credibility over time.
                </p>
                <span className="text-sm text-orange-400 mt-4 inline-block group-hover:underline">
                  Open Dashboard &rarr;
                </span>
              </CardContent>
            </Card>
          </Link>

        </div>

        {/* Backend Services */}
        <div className="max-w-3xl mx-auto mt-12 pt-8 border-t border-border/50">
          <h3 className="text-sm text-muted-foreground mb-4">Backend Services</h3>
          <div className="flex flex-wrap gap-3">
            <div className="flex items-center gap-2 text-sm px-4 py-2 bg-card rounded-lg border border-border/50">
              <Database className="w-4 h-4 text-muted-foreground" />
              TypeDB :1729
              <Badge variant="outline" className={STATUS_STYLES[typedbStatus]}>
                {typedbStatus}
              </Badge>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-border/50 mt-12">
        <div className="container mx-auto px-4 py-4">
          <p className="text-xs text-muted-foreground text-center">
            Skillful-Alhazen &bull; Powered by TypeDB + Next.js
          </p>
        </div>
      </footer>
    </div>
  );
}
