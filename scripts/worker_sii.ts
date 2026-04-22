/* eslint-disable @typescript-eslint/no-explicit-any */
import 'dotenv/config';
import os from 'os';
import pLimit from 'p-limit';
import crypto from 'crypto';
import fetch, { HeadersInit } from 'node-fetch';
import { HttpProxyAgent } from 'http-proxy-agent';
import { HttpsProxyAgent } from 'https-proxy-agent';
import { createClient } from '@supabase/supabase-js';

const WORKER_ID = process.env.WORKER_ID || `${os.hostname()}-${process.pid}`;

// ========= ENV (SOLO HTTPS a Supabase) =========
const PROXY_URL = process.env.PROXY_URL || ''; // vacío => sin proxy para SII
const SII_BASE = 'https://www4.sii.cl/mapasui/internet/#/contenido/index.html';
const SII_PREDIO_URL = 'https://www4.sii.cl/mapasui/services/data/mapasFacadeService/getPredioNacional';

const SUPABASE_URL = process.env.SUPABASE_URL!;
const SUPABASE_SERVICE_ROLE = process.env.SUPABASE_SERVICE_ROLE!;

const BATCH_SIZE = Number(process.env.BATCH_SIZE || 40);
const CONCURRENCY = Number(process.env.CONCURRENCY || 4);
const REQUEST_TIMEOUT_MS = Number(process.env.REQUEST_TIMEOUT_MS || 6500);
const MAX_RETRIES_CONN = Number(process.env.MAX_RETRIES_CONN || 2);
const MAX_RETRIES_504  = Number(process.env.MAX_RETRIES_504  || 0);
const BACKOFF_BASE_MS  = Number(process.env.BACKOFF_BASE_MS  || 900);
const SESSION_TTL_MS   = Number(process.env.SESSION_TTL_MS   || 60_000);

const MARK_NO_DATA = (process.env.MARK_NO_DATA ?? '1') === '1';
const NO_DATA_VALUE = process.env.NO_DATA_VALUE || 'NO ENCONTRADA';

// ========= Supabase client (REST/RPC) =========
if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE) {
  console.error('FATAL: faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE en .env');
  process.exit(1);
}
const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE, {
  auth: { persistSession: false, autoRefreshToken: false },
});

// ========= Helpers comunes =========
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function makeAgent() {
  if (!PROXY_URL) return undefined;
  return PROXY_URL.startsWith('https://')
    ? new HttpsProxyAgent(PROXY_URL)
    : new HttpProxyAgent(PROXY_URL);
}

function toNum(v: unknown): number | null {
  if (typeof v === 'number' && Number.isFinite(v)) return v;
  if (typeof v === 'string') {
    const n = Number(v.replace(/\s+/g, '').replace(',', '.'));
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function normalizeCoords(x: number | null, y: number | null): { lat: number | null; lng: number | null } {
  if (x == null || y == null) return { lat: 0, lng: 0 };
  const lonX = Math.abs(x) >= 60 && Math.abs(x) <= 80;
  const latY = Math.abs(y) >= 10 && Math.abs(y) <= 60;
  if (lonX && latY) return { lat: y, lng: x };
  const latX = Math.abs(x) >= 10 && Math.abs(x) <= 60;
  const lonY = Math.abs(y) >= 60 && Math.abs(y) <= 80;
  if (latX && lonY) return { lat: x, lng: y };
  return { lat: x, lng: y };
}

async function fetchWithTimeout(url: string, init: any, timeoutMs: number) {
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(t);
  }
}

// ========= Cookie / Sesión SII =========
const jar = new Map<string, string>();
let cookieFetchedAt = 0;
let DTPC: string | undefined;
let sessionAgent: any | undefined;
let warmupPromise: Promise<void> | null = null;

function cookieHeader(): string {
  return Array.from(jar.entries()).map(([k, v]) => `${k}=${v}`).join('; ');
}
function ingestSetCookie(headers: any) {
  const raw = (headers?.raw?.() || {})['set-cookie'] || [];
  for (const sc of raw) {
    const first = String(sc).split(';')[0]?.trim();
    if (!first) continue;
    const i = first.indexOf('=');
    if (i <= 0) continue;
    jar.set(first.slice(0, i).trim(), first.slice(i + 1).trim());
  }
}
function clearSession() {
  jar.clear(); DTPC = undefined; cookieFetchedAt = 0; sessionAgent = undefined; warmupPromise = null;
}
async function ensureSession() {
  const now = Date.now();
  const alive = now - cookieFetchedAt < SESSION_TTL_MS;
  if (alive && sessionAgent && cookieHeader()) return;

  if (warmupPromise) { await warmupPromise; return; }
  warmupPromise = (async () => {
    sessionAgent = makeAgent();
    const r = await fetch(SII_BASE, {
      method: 'GET',
      agent: sessionAgent,
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'es-CL,es;q=0.9',
      },
    });
    ingestSetCookie(r.headers);
    DTPC = r.headers.get('x-dtpc') || DTPC;
    cookieFetchedAt = Date.now();
  })();
  try { await warmupPromise; } finally { warmupPromise = null; }
}

// ========= Llamada SII =========
type SiiOk = { ok: true; ah: string | null; lat: number | null; lng: number | null };
type SiiNo = { ok: false; kind: 'NO_DATA' | 'TIMEOUT' | 'HTTP_504' | 'HTTP_OTHER' | 'NON_JSON' | 'NET' | 'PROXY_LIMIT' };
type SiiResult = SiiOk | SiiNo;

const fastBad = new Set<string>();

async function getPredioNacional(comuna: string, manzana: number, predio: number): Promise<SiiResult> {
  const payload = {
    metaData: {
      namespace: 'cl.sii.sdi.lob.bbrr.mapas.data.api.interfaces.MapasFacadeService/getPredioNacional',
      conversationId: `UNAUTHENTICATED-CALL-${WORKER_ID}`,
      transactionId: crypto.randomUUID(),
    },
    data: {
      predio: { comuna: String(comuna), manzana: String(manzana), predio: String(predio) },
      servicios: [],
    },
  };

  let tries504 = 0;
  let connAttempts = 0;

  while (true) {
    try {
      await ensureSession();
      const headers: HeadersInit = {
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json;charset=UTF-8',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
        'Origin': 'https://www4.sii.cl',
        'Referer': 'https://www4.sii.cl/mapasui/internet/',
        ...(cookieHeader() ? { Cookie: cookieHeader() } : {}),
        ...(DTPC ? { 'x-dtpc': DTPC } : {}),
      };

      const resp = await fetchWithTimeout(
        SII_PREDIO_URL,
        { method: 'POST', agent: sessionAgent || makeAgent(), headers, body: JSON.stringify(payload) },
        REQUEST_TIMEOUT_MS
      );

      if (resp.status === 504) {
        if (tries504 < MAX_RETRIES_504) { tries504++; await sleep(BACKOFF_BASE_MS + Math.random()*400); continue; }
        return { ok: false, kind: 'HTTP_504' };
      }
      if (resp.status === 403 || resp.status === 429) {
        clearSession();
        return { ok: false, kind: 'HTTP_OTHER' };
      }

      const ct = resp.headers.get('content-type') || '';
      if (!ct.includes('application/json')) {
        const txt = (await resp.text()).replace(/\s+/g, ' ').slice(0, 240);
        if (/Bandwidth limit reached/i.test(txt)) return { ok: false, kind: 'PROXY_LIMIT' };
        return { ok: false, kind: 'NON_JSON' };
      }

      const json = (await resp.json()) as any;
      const d = json?.data || {};
      if (d.existePredio === 0) return { ok: false, kind: 'NO_DATA' };

      let ah = typeof d.ah === 'string' && d.ah.trim() ? d.ah.trim() : null;
      if (ah === null) {
        ah = NO_DATA_VALUE;
      }
      const x = toNum(d.ubicacionX);
      const y = toNum(d.ubicacionY);
      const norm = normalizeCoords(x, y);
      const hasCoords = norm.lat != null && norm.lng != null;

      if (!hasCoords && !ah) return { ok: false, kind: 'NO_DATA' };
      if (!hasCoords && ah)  return { ok: true, ah, lat: 0, lng: 0 };
      return { ok: true, ah, lat: norm.lat, lng: norm.lng };

    } catch (e: any) {
      const msg = String(e?.message || e);
      const code = String(e?.code || '');
      if (/aborted|AbortError/i.test(msg)) return { ok: false, kind: 'TIMEOUT' };
      if ((code === 'ECONNRESET' || /socket hang up/i.test(msg)) && connAttempts < MAX_RETRIES_CONN) {
        connAttempts++; clearSession();
        const wait = Math.min(BACKOFF_BASE_MS * 2 ** (connAttempts - 1), 8000) + Math.floor(Math.random()*500);
        await sleep(wait);
        continue;
      }
      return { ok: false, kind: 'NET' };
    }
  }
}

// ========= RPC/Updates por Supabase REST =========
type PredioRow = { cod_comuna: string; manzana_actual: number; predio_actual: number; clave_predio: string; };

async function claimBatch(workerId: string, limit: number, ttlMin: number): Promise<PredioRow[]> {
  const { data, error } = await supabase.rpc('claim_batch_predios', {
    p_worker: workerId, p_limit: limit, p_ttl_minutes: ttlMin,
  });
  if (error) throw error;
  return (data || []) as PredioRow[];
}

async function updateCoordsForRol(clave_predio: string, lat: number | null, lng: number | null, ah: string | null) {
  // usamos tu misma función en PG
  const { error } = await supabase.rpc('update_coords_for_rol', {
    p_clave_predio: clave_predio,
    p_lat: lat,
    p_lng: lng,
    p_area: ah,
  });
  if (error) throw error;
}

async function updateAhOnly(clave_predio: string, ah: string) {
  const { error } = await supabase.rpc('upsert_ah_for_rol', {
    p_clave_predio: clave_predio,
    p_area: ah,
  });
  if (error) throw error;
}


async function markNoData(clave_predio: string) {
  if (!MARK_NO_DATA) return;
  const { error } = await supabase.rpc('mark_no_data_for_rol', {
    p_clave_predio: clave_predio,
    p_value: NO_DATA_VALUE, // 'NO ENCONTRADA'
  });
  if (error) throw error;
}



async function clearClaim(clave_predio: string) {
  const { error } = await supabase
    .from('predios')
    .update({ geocode_claimed_by: null })
    .eq('clave_predio', clave_predio);
  if (error) throw error;
}

// ========= Worker loop =========
// dentro de processRow
async function processRow(row: PredioRow) {
  let releaseClaim = true;
  try {
    await sleep(40 + Math.floor(Math.random() * 120));
    const res = await getPredioNacional(row.cod_comuna, row.manzana_actual, row.predio_actual);

    if (res.ok) {
      if (res.lat != null && res.lng != null) {
        await updateCoordsForRol(row.clave_predio, res.lat, res.lng, res.ah ?? null);
        console.log(`${row.clave_predio} -> OK   AH=${res.ah ?? 'null'} LAT=${res.lat} LNG=${res.lng}`);
      } else if (res.ah) {
        await updateAhOnly(row.clave_predio, res.ah);
        console.log(`${row.clave_predio} -> AH_ONLY   AH=${res.ah}`);
      } else {
        console.log(`${row.clave_predio} -> NO_DATA (OK_BUT_EMPTY)`);
      }
      return;
    }

    if (res.kind === 'NO_DATA') {
      await markNoData(row.clave_predio);              // pone 'NO ENCONTRADA'
      releaseClaim = false;                            // NO liberar -> quedará “enfriado” por TTL
      console.log(`${row.clave_predio} -> NO_DATA (API)`);
      return;
    }

    if (res.kind === 'PROXY_LIMIT') {
      console.warn('Proxy sin ancho de banda (PROXY_LIMIT). Pauso 60s y salgo.');
      await sleep(60_000);
      process.exit(0);
    }

    console.log(`${row.clave_predio} -> TEMP (${res.kind})`);
    return;

  } finally {
    if (releaseClaim) {
      await clearClaim(row.clave_predio).catch(() => {});
    }
  }
}


async function main() {
  console.log(`WORKER(REST) worker_id=${WORKER_ID} proxy=${PROXY_URL ? 'ON' : 'OFF'} conc=${CONCURRENCY} timeout_ms=${REQUEST_TIMEOUT_MS}`);

  const limit = pLimit(CONCURRENCY);
  while (true) {
    const rows = await claimBatch(WORKER_ID, BATCH_SIZE, 5);
    if (!rows.length) break;
    await Promise.all(rows.map((r) => limit(() => processRow(r))));
  }

  console.log('FIN');
}

main().catch((e) => {
  console.error('FATAL', e?.message || e);
  process.exit(1);
});
