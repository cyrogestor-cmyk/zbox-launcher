// Drop-in Next.js App Router endpoint for zmax-marketplace (Railway 24h server):
// Place at: src/app/api/zbox/latest/route.ts
//
// Serves the latest published ZBOX version.json directly from cyrogestor-cmyk/zbox-launcher
// with in-memory 5-minute caching so ZMAX Marketplace can display the live "Baixar ZBOX"
// button (Windows/Linux/macOS) and act as a 24h version mirror.

import { NextResponse } from "next/server";

const ZBOX_VERSION_URL =
  "https://github.com/cyrogestor-cmyk/zbox-launcher/releases/latest/download/version.json";
const CACHE_TTL_MS = 5 * 60 * 1000;

let cached: { data: unknown; at: number } | null = null;

export async function GET() {
  const now = Date.now();
  if (cached && now - cached.at < CACHE_TTL_MS) {
    return NextResponse.json(cached.data, {
      headers: { "Cache-Control": "public, max-age=300, stale-while-revalidate=600" },
    });
  }

  try {
    const res = await fetch(ZBOX_VERSION_URL, {
      headers: { "User-Agent": "ZMAX-Server/1.0" },
      redirect: "follow",
      cache: "no-store",
    });
    if (!res.ok) {
      if (cached) return NextResponse.json(cached.data);
      return NextResponse.json({ error: "ZBOX release not published yet" }, { status: 503 });
    }
    const data = await res.json();
    cached = { data, at: now };
    return NextResponse.json(data, {
      headers: { "Cache-Control": "public, max-age=300, stale-while-revalidate=600" },
    });
  } catch {
    if (cached) return NextResponse.json(cached.data);
    return NextResponse.json({ error: "Failed to reach GitHub Releases" }, { status: 502 });
  }
}
