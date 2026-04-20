import { NextRequest, NextResponse } from 'next/server';
import { listSkills } from '@/lib/bioskills-index';

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const op = req.nextUrl.searchParams.get('op') || '';
    const topic = req.nextUrl.searchParams.get('topic') || '';
    if (!op && !topic) return NextResponse.json({ error: 'op or topic required' }, { status: 400 });
    const data = await listSkills(id, { op: op || undefined, topic: topic || undefined, limit: 300 });
    return NextResponse.json(data);
  } catch (error) {
    console.error('skills-by-edam error:', error);
    return NextResponse.json({ error: 'Failed to fetch skills by EDAM' }, { status: 500 });
  }
}
