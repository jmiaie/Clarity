import type { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from './AuthContext';

const LINKS = [
  { to: '/dashboard', label: 'Home' },
  { to: '/journal', label: 'Journal' },
  { to: '/calendar', label: 'Calendar' },
  { to: '/insights', label: 'Patterns' },
  { to: '/account', label: 'Account' },
];

/** Shared top bar so every signed-in page can reach every other one. */
export default function Layout({ children }: { children: ReactNode }) {
  const { logout } = useAuth();

  return (
    <div className="app-shell">
      <nav className="app-nav" aria-label="Main">
        <NavLink to="/dashboard" className="app-brand">
          CLARITY
        </NavLink>
        <div className="app-links">
          {LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) => (isActive ? 'app-link active' : 'app-link')}
            >
              {link.label}
            </NavLink>
          ))}
        </div>
        <button onClick={logout} className="btn-secondary app-logout">
          Log out
        </button>
      </nav>
      <main className="app-main">{children}</main>
    </div>
  );
}
