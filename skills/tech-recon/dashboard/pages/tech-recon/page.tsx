import { listInvestigations } from '@/lib/tech-recon';
import { InvestigationCard } from '@/components/tech-recon/investigation-card';
import { Search, ArrowLeft } from 'lucide-react';
import Link from 'next/link';

const linkClass =
  'text-cyan-400 font-semibold underline underline-offset-2 hover:text-blue-400 transition-colors';

export const dynamic = 'force-dynamic';

export default async function TechReconPage() {
  let investigations: Awaited<ReturnType<typeof listInvestigations>>['investigations'] = [];
  let error: string | null = null;

  try {
    const data = await fetch(`${process.env.NEXT_PUBLIC_BASE_URL || 'http://localhost:3000'}/api/tech-recon/investigations`, { cache: 'no-store' });
    if (data.ok) {
      const json = await data.json();
      investigations = json.investigations || [];
    } else {
      error = `API returned ${data.status}`;
    }
  } catch (err) {
    error = String(err);
  }

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-border/50 bg-card/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center gap-6">
            <Link
              href="/"
              className={`flex items-center gap-2 text-sm ${linkClass}`}
            >
              <ArrowLeft className="w-4 h-4" />
              Hub
            </Link>
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
                Tech Recon
              </h1>
              <p className="text-sm text-muted-foreground">
                Systematic technology investigations
              </p>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6">
        {/* Error */}
        {error && (
          <div className="bg-destructive/10 text-destructive px-4 py-3 rounded-lg mb-6">
            <strong>Error:</strong> {error}
            <p className="text-sm mt-1">
              Make sure TypeDB is running and the tech-recon skill is configured.
            </p>
          </div>
        )}

        {/* Investigations Grid */}
        {investigations.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {investigations.map((inv) => (
              <InvestigationCard key={inv.id} investigation={inv} />
            ))}
          </div>
        )}

        {/* Empty State */}
        {investigations.length === 0 && !error && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <Search className="w-12 h-12 text-muted-foreground/50 mb-4" />
            <h2 className="text-lg font-medium mb-2">No investigations yet</h2>
            <p className="text-sm text-muted-foreground max-w-md">
              Start a Tech Recon investigation using the CLI to explore software systems,
              then come back here to see your findings.
            </p>
          </div>
        )}
      </main>

      <footer className="border-t border-border/50 mt-8">
        <div className="container mx-auto px-4 py-4">
          <p className="text-xs text-muted-foreground text-center">
            Tech Recon &bull; Powered by TypeDB + Next.js
          </p>
        </div>
      </footer>
    </div>
  );
}
