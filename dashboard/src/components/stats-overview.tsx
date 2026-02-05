'use client';

import { Card, CardContent } from '@/components/ui/card';
import {
  Briefcase,
  Send,
  Phone,
  Users,
  Trophy,
  TrendingUp,
} from 'lucide-react';

interface Position {
  id: string;
  status: string;
  priority: string;
}

interface StatsOverviewProps {
  positions: Position[];
}

export function StatsOverview({ positions }: StatsOverviewProps) {
  const stats = {
    total: positions.length,
    active: positions.filter(
      (p) => !['rejected', 'withdrawn', 'offer'].includes(p.status)
    ).length,
    applied: positions.filter((p) => p.status === 'applied').length,
    interviewing: positions.filter(
      (p) => p.status === 'phone-screen' || p.status === 'interviewing'
    ).length,
    offers: positions.filter((p) => p.status === 'offer').length,
    highPriority: positions.filter((p) => p.priority === 'high').length,
  };

  const statCards = [
    {
      label: 'Total Positions',
      value: stats.total,
      icon: Briefcase,
      color: 'text-slate-600',
      bgColor: 'bg-slate-100',
    },
    {
      label: 'Active Applications',
      value: stats.active,
      icon: TrendingUp,
      color: 'text-blue-600',
      bgColor: 'bg-blue-100',
    },
    {
      label: 'Applied',
      value: stats.applied,
      icon: Send,
      color: 'text-purple-600',
      bgColor: 'bg-purple-100',
    },
    {
      label: 'In Interview Process',
      value: stats.interviewing,
      icon: Phone,
      color: 'text-amber-600',
      bgColor: 'bg-amber-100',
    },
    {
      label: 'High Priority',
      value: stats.highPriority,
      icon: Users,
      color: 'text-red-600',
      bgColor: 'bg-red-100',
    },
    {
      label: 'Offers',
      value: stats.offers,
      icon: Trophy,
      color: 'text-green-600',
      bgColor: 'bg-green-100',
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      {statCards.map((stat) => (
        <Card key={stat.label}>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-bold">{stat.value}</div>
                <div className="text-xs text-muted-foreground">
                  {stat.label}
                </div>
              </div>
              <div className={`p-2 rounded-lg ${stat.bgColor}`}>
                <stat.icon className={`w-5 h-5 ${stat.color}`} />
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
