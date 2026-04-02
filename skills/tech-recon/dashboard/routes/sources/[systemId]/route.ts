import { NextResponse } from 'next/server';
import { listArtifacts } from '@/lib/tech-recon';

export async function GET(req: Request, { params }: { params: Promise<{ systemId: string }> }) {
  try {
    const { systemId } = await params;
    const data = await listArtifacts(systemId);
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
