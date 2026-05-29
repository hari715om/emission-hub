import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getBatch } from '../services/api'
import { fmtDateTime, fmtNum, fmtFileSize } from '../utils/format'

export default function BatchDetail() {
  const { id } = useParams()
  const [batch, setBatch] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getBatch(id).then(r => setBatch(r.data)).catch(console.error).finally(() => setLoading(false))
  }, [id])

  if (loading) return <div className="page-body"><div className="skeleton" style={{ height: 200 }} /></div>
  if (!batch) return <div className="page-body"><div className="alert alert-error">Batch not found.</div></div>

  const successPct = batch.total_rows ? Math.round((batch.success_count / batch.total_rows) * 100) : 0

  return (
    <>
      <div className="page-header">
        <div className="page-title-row">
          <div>
            <div className="breadcrumb">
              <Link to="/batches">Batches</Link> › Detail
            </div>
            <h1>Batch Detail</h1>
          </div>
          <Link
            to={`/review?batch=${id}`}
            className="btn btn-primary"
          >Review Rows →</Link>
        </div>
      </div>

      <div className="page-body">
        {/* Metadata card */}
        <div className="card mb-4">
          <div className="flex items-center justify-between mb-4">
            <h3>{batch.file_name}</h3>
            <span className={`badge badge-${batch.source_type.toLowerCase()}`}>{batch.source_type}</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12, marginBottom: 20 }}>
            {[
              ['Status', batch.status],
              ['Tenant', batch.tenant_name],
              ['Uploaded by', batch.uploaded_by_username || 'System'],
              ['Uploaded at', fmtDateTime(batch.uploaded_at)],
              ['Completed at', fmtDateTime(batch.completed_at)],
              ['File size', fmtFileSize(batch.file_size_bytes)],
            ].map(([k, v]) => (
              <div key={k} className="kv-row" style={{ flexDirection: 'column', gap: 2, border: 'none', padding: 0 }}>
                <span className="kv-key">{k}</span>
                <span className="kv-val" style={{ textAlign: 'left', fontWeight: 500 }}>{v || '—'}</span>
              </div>
            ))}
          </div>

          {/* Progress bar */}
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm text-muted">Success rate</span>
            <span className="text-sm" style={{ color: 'var(--green-500)', fontWeight: 600 }}>{successPct}%</span>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${successPct}%` }} />
          </div>
        </div>

        {/* Row counts */}
        <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(4,1fr)', marginBottom: 24 }}>
          {[
            { label: 'Total Rows',   value: batch.total_rows,      icon: '⊞', accent: 'blue' },
            { label: 'Normalized',   value: batch.success_count,   icon: '✓', accent: 'green' },
            { label: 'Flagged',      value: batch.suspicious_count,icon: '⚠', accent: 'amber' },
            { label: 'Failed',       value: batch.failed_count,    icon: '✗', accent: 'red' },
          ].map(({ label, value, icon, accent }) => {
            const colors = {
              green: 'var(--green-500)', amber: 'var(--amber-400)',
              red: 'var(--red-400)', blue: 'var(--blue-400)'
            }
            const bgs = {
              green: 'var(--green-900)', amber: 'var(--amber-900)',
              red: 'var(--red-900)', blue: 'var(--blue-900)'
            }
            return (
              <div key={label} className="stat-card"
                style={{ '--accent-color': colors[accent], '--accent-bg': bgs[accent] }}>
                <div className="stat-icon">{icon}</div>
                <div className="stat-value">{fmtNum(value, 0)}</div>
                <div className="stat-label">{label}</div>
              </div>
            )
          })}
        </div>

        {/* Failed rows */}
        {batch.failed_rows?.length > 0 && (
          <div className="card">
            <h3 className="mb-3" style={{ color: 'var(--red-400)' }}>
              ✗ Failed Rows ({batch.failed_rows.length})
            </h3>
            <div className="alert alert-warning mb-4">
              These rows could not be parsed. The raw data is preserved below. Fix the source file and re-upload, or contact the data owner.
            </div>
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>Line #</th>
                    <th>Error</th>
                    <th>Raw Data (truncated)</th>
                  </tr>
                </thead>
                <tbody>
                  {batch.failed_rows.map(row => (
                    <tr key={row.id} style={{ background: 'var(--red-900)' }}>
                      <td style={{ color: 'var(--red-400)', fontWeight: 600 }}>L{row.line_number}</td>
                      <td style={{ color: 'var(--red-400)', maxWidth: 300 }}>{row.parse_error}</td>
                      <td>
                        <span className="font-mono text-xs text-muted">
                          {JSON.stringify(row.raw_payload).slice(0, 120)}…
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {batch.notes && (
          <div className="alert alert-warning mt-4">{batch.notes}</div>
        )}
      </div>
    </>
  )
}
