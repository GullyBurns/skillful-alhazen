import { NextRequest, NextResponse } from 'next/server';
import { showSkill } from '@/lib/bioskills-index';

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ sid: string }> }
) {
  try {
    const { sid } = await params;
    const data = await showSkill(sid);
    return NextResponse.json(data);
  } catch (error) {
    console.error('show-skill error:', error);
    return NextResponse.json({ error: 'Failed to fetch skill' }, { status: 500 });
  }
}
