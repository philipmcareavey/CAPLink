// CAPLink mobile API client — a direct port of static/app/js/api.js's
// pattern (same auth-header injection, same error shape) so the mobile app
// behaves identically to the existing web reference app against the same
// backend. Points at the real, live staging API — no mock server.
export const API_BASE = 'https://caplink-api.onrender.com/api/v1';

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export interface JwtClaims {
  sub: string;
  role: 'student' | 'business' | 'university_admin' | 'platform_admin';
  university_id: string | null;
  exp: number;
}

// Hermes doesn't provide atob/Buffer — decode base64url by hand (same
// base64url -> base64 translation the web app's own decodeJwt does, just
// without a browser/Node built-in to lean on).
const BASE64_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';

function base64Decode(base64: string): string {
  let output = '';
  let buffer = 0;
  let bits = 0;
  for (const char of base64) {
    if (char === '=') break;
    const value = BASE64_CHARS.indexOf(char);
    if (value === -1) continue;
    buffer = (buffer << 6) | value;
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      output += String.fromCharCode((buffer >> bits) & 0xff);
    }
  }
  return output;
}

function base64UrlDecode(input: string): string {
  const base64 = input.replace(/-/g, '+').replace(/_/g, '/');
  const binary = base64Decode(base64);
  let result = '';
  for (let i = 0; i < binary.length; i++) {
    result += '%' + binary.charCodeAt(i).toString(16).padStart(2, '0');
  }
  return decodeURIComponent(result);
}

export function decodeJwt(token: string): JwtClaims {
  const payload = token.split('.')[1];
  return JSON.parse(base64UrlDecode(payload));
}

type ApiOptions = {
  method?: string;
  body?: unknown;
  auth?: boolean;
  token?: string | null;
};

export async function api<T = unknown>(
  path: string,
  { method = 'GET', body, auth = true, token = null }: ApiOptions = {},
): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (auth && token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    // no body
  }

  if (!res.ok) {
    const detail =
      data && typeof data === 'object' && 'detail' in (data as Record<string, unknown>)
        ? typeof (data as Record<string, unknown>).detail === 'string'
          ? ((data as Record<string, unknown>).detail as string)
          : JSON.stringify((data as Record<string, unknown>).detail)
        : res.statusText;
    throw new ApiError(detail, res.status);
  }

  return data as T;
}
