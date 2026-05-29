import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getDashboardStats, getBatches } from '../services/api'
import { fmtDateTime, fmtNum, sourceLabel } from '../utils/format'

const StatCard = ({ label, value, icon, accent = 'green', sub }) => {
  const accentMap = {
    green:  { color: 'var(--green-500)',  bg: 'var(--green-900)' },
    amber:  { color: 'var(--amber-400)',  bg: 'var(--amber-900)' },
    red:    { color: 'var(--red-400)',    bg: 'var(--red-900)' },
    blue:   { color: 'var(--blue-400)',   bg: 'var(--blue-900)' },
    purple: { color: 'var(--purple-400)', bg: 'var(--purple-900)' },
  }
  const { color, bg } = accentMap[accent] || accentMap.green

  return (
    <div className="stat-card" style={{ '--accent-color': color, '--accent-bg': bg }}>
      <div className="stat-icon">{icon}</div>
      <div className="stat-value">{fmtNum(value, 0)}</div>
      <div className="stat-label">{label}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  )
}

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [batches, setBatches] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getDashboardStats(), getBatches({ page_size: 5 })])
      .then(([sRes, bRes]) => {
        setStats(sRes.data)
        setBatches(bRes.data.results || bRes.data)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const statusDot = (s) => ({
    DONE: '🟢', PROCESSING: '🟡', FAILED: '🔴', PENDING: '⚪'
  }[s] || '⚪')

  return (
    <>
      <div className="page-header">
        <div className="page-title-row">
          <div>
            <div className="breadcrumb">Platform</div>
            <h1>Dashboard</h1>
          </div>
          <Link to="/upload" className="btn btn-primary">↑ Upload Data</Link>
        </div>
      </div>

      <div className="page-body">
        {loading ? (
          <div className="stats-grid">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="stat-card skeleton" style={{ height: 110 }} />
            ))}
          </div>
        ) : stats ? (
          <>
            {/* Main stats */}
            <div className="stats-grid">
              <StatCard label="Total Batches"    value={stats.total_batches}   icon="⊞" accent="blue"   sub="Ingestion runs" />
              <StatCard label="Total Activities" value={stats.total_activities} icon="◈" accent="green"  sub="Normalized rows" />
              <StatCard label="Pending Review"   value={stats.pending}         icon="○" accent="blue"   sub="Awaiting analyst" />
              <StatCard label="Flagged"          value={stats.flagged}         icon="⚠" accent="amber"  sub="Need attention" />
              <StatCard label="Approved"         value={stats.approved}        icon="✓" accent="green"  sub="Locked for audit" />
              <StatCard label="Rejected"         value={stats.rejected}        icon="✗" accent="red"    sub="Excluded from report" />
              <StatCard label="Suspicious Rows"  value={stats.suspicious}      icon="⊙" accent="amber"  sub="Auto-flagged" />
              <StatCard label="Locked for Audit" value={stats.locked}          icon="🔒" accent="purple" sub="Immutable" />
            </div>

            {/* Scope & Source breakdown */}
            <div className="flex gap-4 mb-6" style={{ flexWrap: 'wrap' }}>
              <div className="card" style={{ flex: 1, minWidth: 260 }}>
                <h4 className="mb-3">By GHG Scope</h4>
                <div className="breakdown-grid">
                  {['1','2','3'].map(s => (
                    <div key={s} className="breakdown-chip">
                      <div className="val" style={{ color: s==='1'?'var(--red-400)':s==='2'?'var(--blue-400)':'var(--purple-400)' }}>
                        {fmtNum(stats.scope_breakdown?.[`scope_${s}`] || 0, 0)}
                      </div>
                      <div className="lbl">Scope {s}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="card" style={{ flex: 1, minWidth: 260 }}>
                <h4 className="mb-3">By Data Source</h4>
                <div className="breakdown-grid">
                  {['sap','utility','travel'].map(src => (
                    <div key={src} className="breakdown-chip">
                      <div className="val" style={{ color: 'var(--green-500)' }}>
                        {fmtNum(stats.source_breakdown?.[src] || 0, 0)}
                      </div>
                      <div className="lbl">{src.toUpperCase()}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Recent batches */}
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <h3>Recent Ingestion Batches</h3>
                <Link to="/batches" className="btn btn-secondary btn-sm">View all →</Link>
              </div>
              {batches.length === 0 ? (
                <div className="alert alert-info">
                  No data ingested yet. <Link to="/upload">Upload a CSV file</Link> to get started.
                </div>
              ) : (
                <div className="table-wrapper">
                  <table>
                    <thead>
                      <tr>
                        <th>Source</th>
                        <th>File</th>
                        <th>Status</th>
                        <th>Rows</th>
                        <th>Failed</th>
                        <th>Suspicious</th>
                        <th>Uploaded</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {batches.map(b => (
                        <tr key={b.id}>
                          <td><span className={`badge badge-${b.source_type.toLowerCase()}`}>{b.source_type}</span></td>
                          <td><span className="truncate font-mono text-sm">{b.file_name}</span></td>
                          <td>{statusDot(b.status)} {b.status}</td>
                          <td>{fmtNum(b.total_rows, 0)}</td>
                          <td style={{ color: b.failed_count > 0 ? 'var(--red-400)' : 'inherit' }}>
                            {fmtNum(b.failed_count, 0)}
                          </td>
                          <td style={{ color: b.suspicious_count > 0 ? 'var(--amber-400)' : 'inherit' }}>
                            {fmtNum(b.suspicious_count, 0)}
                          </td>
                          <td className="text-muted">{fmtDateTime(b.uploaded_at)}</td>
                          <td>
                            <Link to={`/batches/${b.id}`} className="btn btn-secondary btn-sm">View</Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="alert alert-error">Failed to load stats. Is the backend running?</div>
        )}
      </div>
    </>
  )
}
