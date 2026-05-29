import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../App'
import { logout } from '../services/api'

const navItems = [
  { to: '/dashboard', icon: '◈', label: 'Dashboard' },
  { to: '/upload',    icon: '↑', label: 'Upload Data' },
  { to: '/batches',   icon: '⊞', label: 'Ingestion Batches' },
  { to: '/review',    icon: '✓', label: 'Review & Approve' },
]

export default function Layout() {
  const { user, setUser } = useAuth()
  const navigate = useNavigate()

  const handleLogout = async () => {
    try { await logout() } catch {}
    setUser(null)
    navigate('/login')
  }

  const initials = user?.username?.slice(0, 2).toUpperCase() || 'AN'

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-mark">
            <div className="logo-icon">🌿</div>
            <div className="logo-text">
              Emission Hub
              <span>Breathe ESG</span>
            </div>
          </div>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-section-label">Platform</div>
          {navItems.map(({ to, icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
            >
              <span className="nav-icon">{icon}</span>
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="user-chip">
            <div className="user-avatar">{initials}</div>
            <div className="user-info">
              <div className="user-name">{user?.username || 'Analyst'}</div>
              <div className="user-role">ESG Analyst</div>
            </div>
            <button
              onClick={handleLogout}
              className="btn btn-secondary btn-sm btn-icon"
              title="Logout"
              style={{ padding: '4px 6px', fontSize: '0.75rem' }}
            >↩</button>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <Outlet />
      </main>
    </div>
  )
}
