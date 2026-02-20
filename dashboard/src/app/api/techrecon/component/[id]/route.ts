import { NextResponse } from 'next/server';
import { getComponent } from '@/lib/techrecon';

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  try {
    const data = await getComponent(id);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Component error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch component' },
      { status: 500 }
    );
  }
}
