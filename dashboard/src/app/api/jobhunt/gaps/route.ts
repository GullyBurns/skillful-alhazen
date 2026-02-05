import { NextRequest, NextResponse } from 'next/server';
import { getSkillGaps } from '@/lib/jobhunt';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const priority = searchParams.get('priority') || undefined;

  try {
    const data = await getSkillGaps(priority);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Skill gaps error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch skill gaps' },
      { status: 500 }
    );
  }
}
