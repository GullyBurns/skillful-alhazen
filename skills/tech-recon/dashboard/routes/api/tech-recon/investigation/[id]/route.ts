import { NextResponse } from 'next/server';
import { getInvestigation, listSystems, listNotes, listAnalyses } from '@/lib/tech-recon';

export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const [invData, systemsData, notesData, analysesData] = await Promise.all([
      getInvestigation(id),
      listSystems(id),
      listNotes(id),
      listAnalyses(id),
    ]);
    return NextResponse.json({
      ...invData,
      systems: systemsData.systems,
      notes: notesData.notes,
      analyses: analysesData.analyses,
    });
  } catch (error) {
    console.error('getInvestigation error:', error);
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
