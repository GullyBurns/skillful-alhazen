import { NextResponse } from 'next/server';
import { getDataModel } from '@/lib/techrecon';

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  try {
    const data = await getDataModel(id);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Data model error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch data model' },
      { status: 500 }
    );
  }
}
