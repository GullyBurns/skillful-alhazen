'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Briefcase, Database, Dna, LayoutDashboard, Layers, Megaphone, Search } from 'lucide-react';

type ServiceStatus = 'checking' | 'online' | 'offline';

type SkillConfig = {
  slug: string;
  name: string;
  description: string;
  url_path: string;
  icon: string;
  color: string;
};

const STATUS_STYLES: Record<ServiceStatus, string> = {
  checking: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  online: 'bg-green-500/20 text-green-400 border-green-500/30',
  offline: 'bg-red-500/20 text-red-400 border-red-500/30',
};

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  Briefcase,
  Search,
  Dna,
  Layers,
  Megaphone,
  LayoutDashboard,
};

const COLOR_MAP: Record<string, { border: string; text: string; icon: string }> = {
  indigo: { border: 'hover:border-indigo-500/50', text: 'text-primary',    icon: 'text-indigo-400' },
  cyan:   { border: 'hover:border-cyan-500/50',   text: 'text-cyan-400',   icon: 'text-cyan-400' },
  teal:   { border: 'hover:border-teal-500/50',   text: 'text-teal-400',   icon: 'text-teal-400' },
  violet: { border: 'hover:border-violet-500/50', text: 'text-violet-400', icon: 'text-violet-400' },
  amber:  { border: 'hover:border-amber-500/50',  text: 'text-amber-400',  icon: 'text-amber-400' },
};

export default function HubPage() {
  const [typedbStatus, setTypedbStatus] = useState<ServiceStatus>('checking');
  const [skills, setSkills] = useState<SkillConfig[]>([]);

  useEffect(() => {
    fetch('/api/typedb-status')
      .then(r => r.json())
      .then(d => setTypedbStatus(d.status === 'online' ? 'online' : 'offline'))
      .catch(() => setTypedbStatus('offline'));
  }, []);

  useEffect(() => {
    fetch('/skills-config.json')
      .then(r => r.json())
      .then(setSkills)
      .catch(() => {});
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
          {skills.map(skill => {
            const Icon = ICON_MAP[skill.icon] ?? LayoutDashboard;
            const c = COLOR_MAP[skill.color] ?? COLOR_MAP.indigo;
            return (
              <Link key={skill.slug} href={skill.url_path} className="group">
                <Card className={`h-full transition-all ${c.border} hover:-translate-y-1`}>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-3">
                      <Icon className={`w-6 h-6 ${c.icon}`} />
                      {skill.name}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">{skill.description}</p>
                    <span className={`text-sm ${c.text} mt-4 inline-block group-hover:underline`}>
                      Open Dashboard &rarr;
                    </span>
                  </CardContent>
                </Card>
              </Link>
            );
          })}
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
