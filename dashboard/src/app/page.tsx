'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Briefcase, Monitor, Database } from 'lucide-react';

type ServiceStatus = 'checking' | 'online' | 'offline';

const STATUS_STYLES: Record<ServiceStatus, string> = {
  checking: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  online: 'bg-green-500/20 text-green-400 border-green-500/30',
  offline: 'bg-red-500/20 text-red-400 border-red-500/30',
};

export default function HubPage() {
  const [typedbStatus, setTypedbStatus] = useState<ServiceStatus>('checking');

  useEffect(() => {
    async function checkTypeDB() {
      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 3000);
        await fetch(`${window.location.protocol}//${window.location.hostname}:1729`, {
          method: 'HEAD',
          mode: 'no-cors',
          signal: controller.signal,
        });
        clearTimeout(timeout);
        setTypedbStatus('online');
      } catch {
        setTypedbStatus('offline');
      }
    }
    checkTypeDB();
  }, []);

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="py-16 text-center">
        <h1 className="text-4xl font-bold bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">
          Skillful-Alhazen
        </h1>
        <p className="text-muted-foreground mt-2 text-lg">
          AI-Powered Knowledge Curation System
        </p>
      </header>

      {/* Dashboard Cards */}
      <main className="container mx-auto px-4 flex-1">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-3xl mx-auto">
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
                  <Monitor className="w-6 h-6 text-cyan-400" />
                  TechRecon Dashboard
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Explore technology reconnaissance investigations, system architectures, and concepts.
                </p>
                <span className="text-sm text-primary mt-4 inline-block group-hover:underline">
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
