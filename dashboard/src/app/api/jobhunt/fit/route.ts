import { NextResponse } from 'next/server';
import { getSkillGaps } from '@/lib/jobhunt';

export async function GET() {
  try {
    const data = await getSkillGaps();
    return NextResponse.json(data);
  } catch (error) {
    console.error('fit computation error:', error);
    return NextResponse.json({ success: false, error: String(error) }, { status: 500 });
  }
}
