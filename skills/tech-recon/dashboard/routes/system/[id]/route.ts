import { NextResponse } from 'next/server';
import { getSystem, listArtifacts, listNotes } from '@/lib/tech-recon';

export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const [systemData, artifactsData, notesData] = await Promise.all([
      getSystem(id),
      listArtifacts(id),
      listNotes(id),
    ]);
    return NextResponse.json({
      ...systemData,
      artifacts: artifactsData.artifacts,
      notes: notesData.notes,
    });
  } catch (error) {
    console.error('getSystem error:', error);
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
