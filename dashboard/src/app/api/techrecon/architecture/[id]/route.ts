import { NextResponse } from 'next/server';
import { getArchitecture } from '@/lib/techrecon';

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  try {
    const data = await getArchitecture(id);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Architecture error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch architecture' },
      { status: 500 }
    );
  }
}
