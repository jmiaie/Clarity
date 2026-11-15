import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { auth as authAPI, onUnauthorized, tokenStore, type User } from './api';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, inviteCode?: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // If the server ever rejects our token, drop back to the login screen.
    onUnauthorized(() => setUser(null));

    if (tokenStore.get()) {
      authAPI
        .getMe()
        .then(setUser)
        .catch(() => tokenStore.clear())
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
    return () => onUnauthorized(null);
  }, []);

  const refresh = async () => {
    setUser(await authAPI.getMe());
  };

  const login = async (email: string, password: string) => {
    await authAPI.login(email, password);
    await refresh();
  };

  const signup = async (email: string, password: string, inviteCode?: string) => {
    await authAPI.signup(email, password, inviteCode);
    await login(email, password);
  };

  const logout = () => {
    authAPI.logout();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
