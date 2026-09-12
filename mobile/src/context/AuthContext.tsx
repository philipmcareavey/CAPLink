import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import * as Keychain from 'react-native-keychain';
import { api, ApiError, decodeJwt, JwtClaims } from '../api/client';

// Technical Implementation Plan 6.a.ii — secure token storage (Keychain/
// Keystore via react-native-keychain, not AsyncStorage, since these are
// auth tokens) and silent refresh (POST /auth/refresh, exactly the
// endpoint the backend's own docstring built for this).

const KEYCHAIN_SERVICE = 'com.caplink.mobile.auth';

type TokenPair = { access_token: string; refresh_token: string };

type AuthState =
  | { status: 'loading' }
  | { status: 'signedOut' }
  | { status: 'signedIn'; accessToken: string; refreshToken: string; claims: JwtClaims };

type AuthContextValue = {
  state: AuthState;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  // Wraps api() with the current access token, and retries once after a
  // silent refresh if the call comes back 401 (access token expired).
  authedApi: <T = unknown>(path: string, opts?: { method?: string; body?: unknown }) => Promise<T>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

async function saveTokens(tokens: TokenPair): Promise<void> {
  await Keychain.setGenericPassword('caplink', JSON.stringify(tokens), { service: KEYCHAIN_SERVICE });
}

async function loadTokens(): Promise<TokenPair | null> {
  const result = await Keychain.getGenericPassword({ service: KEYCHAIN_SERVICE });
  if (!result) return null;
  try {
    return JSON.parse(result.password) as TokenPair;
  } catch {
    return null;
  }
}

async function clearTokens(): Promise<void> {
  await Keychain.resetGenericPassword({ service: KEYCHAIN_SERVICE });
}

function isExpiredOrExpiringSoon(claims: JwtClaims): boolean {
  const nowSeconds = Date.now() / 1000;
  return claims.exp - nowSeconds < 60; // refresh if under a minute of life left
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: 'loading' });

  const applyTokens = useCallback((tokens: TokenPair) => {
    const claims = decodeJwt(tokens.access_token);
    setState({ status: 'signedIn', accessToken: tokens.access_token, refreshToken: tokens.refresh_token, claims });
  }, []);

  const refresh = useCallback(async (refreshToken: string): Promise<TokenPair> => {
    const tokens = await api<TokenPair>('/auth/refresh', { method: 'POST', auth: false, body: { refresh_token: refreshToken } });
    await saveTokens(tokens);
    return tokens;
  }, []);

  // Silent restore on app start: load whatever's in the Keychain, refresh
  // if the access token's expired or close to it, and only fall back to
  // the login screen if there's truly nothing usable.
  useEffect(() => {
    (async () => {
      const stored = await loadTokens();
      if (!stored) {
        setState({ status: 'signedOut' });
        return;
      }
      try {
        const claims = decodeJwt(stored.access_token);
        if (isExpiredOrExpiringSoon(claims)) {
          const fresh = await refresh(stored.refresh_token);
          applyTokens(fresh);
        } else {
          applyTokens(stored);
        }
      } catch {
        await clearTokens();
        setState({ status: 'signedOut' });
      }
    })();
  }, [applyTokens, refresh]);

  const login = useCallback(
    async (email: string, password: string) => {
      const tokens = await api<TokenPair>('/auth/login', { method: 'POST', auth: false, body: { email, password } });
      await saveTokens(tokens);
      applyTokens(tokens);
    },
    [applyTokens],
  );

  const logout = useCallback(async () => {
    await clearTokens();
    setState({ status: 'signedOut' });
  }, []);

  const authedApi = useCallback(
    async <T,>(path: string, opts: { method?: string; body?: unknown } = {}): Promise<T> => {
      if (state.status !== 'signedIn') throw new Error('Not signed in');
      try {
        return await api<T>(path, { ...opts, token: state.accessToken });
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) {
          const fresh = await refresh(state.refreshToken);
          applyTokens(fresh);
          return await api<T>(path, { ...opts, token: fresh.access_token });
        }
        throw e;
      }
    },
    [state, refresh, applyTokens],
  );

  const value = useMemo(() => ({ state, login, logout, authedApi }), [state, login, logout, authedApi]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
