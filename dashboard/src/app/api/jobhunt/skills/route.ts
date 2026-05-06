import { NextResponse } from 'next/server';
import { listSkills } from '@/lib/jobhunt';

export async function GET() {
  try {
    const data = await listSkills();
    return NextResponse.json(data);
  } catch (error) {
    console.error('listSkills error:', error);
    return NextResponse.json({ success: false, skills: [], error: String(error) }, { status: 500 });
  }
}
