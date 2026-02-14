import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface User {
  username: string;
  owner_group: string;
  display_name: string;
}

interface AuthContextValue {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const API_BASE = '';
const STORAGE_KEY = 'ownerDashAuth';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Restore session from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed.token && parsed.user) {
          // Validate token hasn't expired by calling /auth/me
          fetch(`${API_BASE}/api/auth/me`, {
            headers: { Authorization: `Bearer ${parsed.token}` },
          })
            .then(res => {
              if (res.ok) {
                setToken(parsed.token);
                setUser(parsed.user);
              } else {
                localStorage.removeItem(STORAGE_KEY);
              }
            })
            .catch(() => {
              localStorage.removeItem(STORAGE_KEY);
            })
            .finally(() => setLoading(false));
          return;
        }
      }
    } catch {
      localStorage.removeItem(STORAGE_KEY);
    }
    setLoading(false);
  }, []);

  const login = async (username: string, password: string) => {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Login failed' }));
      throw new Error(err.detail || 'Invalid credentials');
    }

    const data = await res.json();
    const userInfo: User = {
      username: data.username,
      owner_group: data.owner_group,
      display_name: data.display_name,
    };

    setToken(data.token);
    setUser(userInfo);
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ token: data.token, user: userInfo }));
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem(STORAGE_KEY);
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
