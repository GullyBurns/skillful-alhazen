import { NextResponse } from 'next/server';
import { getLearningPlan } from '@/lib/jobhunt';

export async function GET() {
  try {
    const data = await getLearningPlan();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Learning plan error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch learning plan' },
      { status: 500 }
    );
  }
}
