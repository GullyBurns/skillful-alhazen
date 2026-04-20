import { NextRequest, NextResponse } from 'next/server';
import { compose } from '@/lib/bioskills-index';

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const task = req.nextUrl.searchParams.get('task') || '';
    const maxSkills = parseInt(req.nextUrl.searchParams.get('max_skills') || '8');
    if (!task) return NextResponse.json({ error: 'task parameter required' }, { status: 400 });
    const data = await compose(id, task, maxSkills);
    return NextResponse.json(data);
  } catch (error) {
    console.error('compose error:', error);
    return NextResponse.json({ error: 'Compose failed' }, { status: 500 });
  }
}
