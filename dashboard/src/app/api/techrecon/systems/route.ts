import { NextResponse } from 'next/server';
import { listSystems } from '@/lib/techrecon';

export async function GET() {
  try {
    const data = await listSystems();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Systems error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch systems' },
      { status: 500 }
    );
  }
}
