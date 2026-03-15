import { NextResponse } from 'next/server';
import * as net from 'net';

function checkTcp(host: string, port: number, timeoutMs = 3000): Promise<boolean> {
  return new Promise(resolve => {
    const socket = new net.Socket();
    socket.setTimeout(timeoutMs);
    socket.once('connect', () => { socket.destroy(); resolve(true); });
    socket.once('error', () => { socket.destroy(); resolve(false); });
    socket.once('timeout', () => { socket.destroy(); resolve(false); });
    socket.connect(port, host);
  });
}

export async function GET() {
  const host = process.env.TYPEDB_HOST ?? 'localhost';
  const port = parseInt(process.env.TYPEDB_PORT ?? '1729', 10);
  const online = await checkTcp(host, port);
  return NextResponse.json({ status: online ? 'online' : 'offline' });
}
