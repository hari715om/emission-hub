import { useState, useRef } from 'react'
import { uploadFile, getTenants } from '../services/api'
import { useEffect } from 'react'
import { fmtFileSize, fmtNum } from '../utils/format'

const SOURCES = [
  {
    key: 'sap',
    label: 'SAP Fuel & Procurement',
    badge: 'badge-sap',
    desc: 'SAP flat-file CSV export (MB51/ME2M). Expects columns: BUKRS, WERKS, LIFNR, MATNR, MAKTX, MENGE, MEINS, NETPR, WAERS, BLDAT.',
    icon: '⚙',
    scope: 'Scope 1 / 3',
  },
  {
    key: 'utility',
    label: 'Utility Electricity',
    badge: 'badge-utility',
    desc: 'Portal CSV export from utility supplier (EDF, British Gas, etc.). Expects: meter_id, site_name, billing_period_start/end, consumption_kwh, total_amount, currency.',
    icon: '⚡',
    scope: 'Scope 2',
  },
  {
    key: 'travel',
    label: 'Corporate Travel',
    badge: 'badge-travel',
    desc: 'Concur / Navan expense CSV export. Expects: expense_type, origin, destination, distance_km, class_of_service, amount, currency, traveler_name.',
    icon: '✈',
    scope: 'Scope 3',
  },
]

export default function Upload() {
  const [sourceType, setSourceType] = useState('')
  const [file, setFile] = useState(null)
  const [tenantId, setTenantId] = useState('')
  const [tenants, setTenants] = useState([])
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const fileRef = useRef()

  useEffect(() => {
    getTenants().then(r => {
      const list = r.data.results || r.data
      setTenants(list)
      if (list.length === 1) setTenantId(list[0].id)
    }).catch(() => {})
  }, [])

  const handleFile = (f) => {
    if (!f) return
    if (!f.name.endsWith('.csv')) { setError('Only .csv files are accepted.'); return }
    setFile(f)
    setError('')
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    handleFile(e.dataTransfer.files[0])
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!sourceType) { setError('Select a data source type.'); return }
    if (!file) { setError('Choose a CSV file to upload.'); return }
    if (!tenantId && tenants.length > 1) { setError('Select a tenant.'); return }

    setLoading(true)
    setResult(null)
    setError('')
    try {
      const res = await uploadFile(sourceType, file, tenantId || null)
      setResult(res.data)
      setFile(null)
    } catch (err) {
      setError(err.response?.data?.error || 'Upload failed. Check backend logs.')
    } finally {
      setLoading(false)
    }
  }

  const selectedSource = SOURCES.find(s => s.key === sourceType)

  return (
    <>
      <div className="page-header">
        <div className="page-title-row">
          <div>
            <div className="breadcrumb">Platform › Upload</div>
            <h1>Upload Data</h1>
          </div>
        </div>
      </div>

      <div className="page-body" style={{ maxWidth: 780 }}>
        <p className="mb-6">
          Upload a CSV file from one of the three supported sources. The system will parse,
          normalize, and flag rows for analyst review automatically.
        </p>

        {/* Source selector */}
        <div className="card mb-4">
          <h3 className="mb-3">1. Select data source</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
            {SOURCES.map(s => (
              <button
                key={s.key}
                id={`source-${s.key}`}
                className="card-sm"
                onClick={() => { setSourceType(s.key); setResult(null); setError('') }}
                style={{
                  cursor: 'pointer',
                  border: sourceType === s.key
                    ? '1px solid var(--green-500)'
                    : '1px solid var(--border)',
                  background: sourceType === s.key ? 'var(--green-900)' : 'var(--bg-elevated)',
                  textAlign: 'left',
                  transition: 'all 0.18s',
                }}
              >
                <div style={{ fontSize: '1.5rem', marginBottom: 8 }}>{s.icon}</div>
                <div style={{ fontWeight: 600, fontSize: '0.875rem', marginBottom: 4 }}>{s.label}</div>
                <span className={`badge ${s.badge}`}>{s.scope}</span>
                <p className="text-xs text-muted" style={{ marginTop: 8, lineHeight: 1.5 }}>{s.desc}</p>
              </button>
            ))}
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          {/* Tenant selector (only if multiple) */}
          {tenants.length > 1 && (
            <div className="card mb-4">
              <h3 className="mb-3">2. Select tenant</h3>
              <select
                id="tenant-select"
                value={tenantId}
                onChange={e => setTenantId(e.target.value)}
                className="filter-select"
                style={{ width: '100%' }}
              >
                <option value="">— Select tenant —</option>
                {tenants.map(t => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>
          )}

          {/* File upload zone */}
          <div className="card mb-4">
            <h3 className="mb-3">{tenants.length > 1 ? '3.' : '2.'} Upload CSV file</h3>
            <div
              className={`upload-zone${dragging ? ' dragging' : ''}`}
              onDragOver={e => { e.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
              onClick={() => fileRef.current?.click()}
            >
              <input
                ref={fileRef}
                type="file"
                accept=".csv"
                onChange={e => handleFile(e.target.files[0])}
                style={{ display: 'none' }}
              />
              {file ? (
                <div>
                  <span className="upload-icon">📄</span>
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>{file.name}</div>
                  <div className="text-sm text-muted">{fmtFileSize(file.size)}</div>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm mt-4"
                    onClick={e => { e.stopPropagation(); setFile(null) }}
                  >Remove</button>
                </div>
              ) : (
                <div>
                  <span className="upload-icon">☁</span>
                  <div style={{ fontWeight: 600, marginBottom: 6 }}>Drop CSV here or click to browse</div>
                  <div className="text-sm text-muted">Maximum 20 MB · .csv only</div>
                </div>
              )}
            </div>
          </div>

          {error && <div className="alert alert-error">{error}</div>}

          <button
            id="upload-submit"
            type="submit"
            className="btn btn-primary btn-lg"
            disabled={loading || !file || !sourceType}
          >
            {loading ? 'Processing…' : '↑ Ingest & Normalize'}
          </button>
        </form>

        {/* Result summary */}
        {result && (
          <div className="card mt-4" style={{ borderColor: 'var(--border-accent)' }}>
            <div className="alert alert-success mb-4">
              ✓ Ingestion complete — {fmtNum(result.success_count, 0)} rows normalized successfully
            </div>
            <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(4,1fr)' }}>
              <div className="stat-card" style={{ '--accent-color': 'var(--green-500)', '--accent-bg': 'var(--green-900)' }}>
                <div className="stat-icon">⊞</div>
                <div className="stat-value">{fmtNum(result.total_rows, 0)}</div>
                <div className="stat-label">Total rows</div>
              </div>
              <div className="stat-card" style={{ '--accent-color': 'var(--green-500)', '--accent-bg': 'var(--green-900)' }}>
                <div className="stat-icon">✓</div>
                <div className="stat-value">{fmtNum(result.success_count, 0)}</div>
                <div className="stat-label">Normalized</div>
              </div>
              <div className="stat-card" style={{ '--accent-color': 'var(--amber-400)', '--accent-bg': 'var(--amber-900)' }}>
                <div className="stat-icon">⚠</div>
                <div className="stat-value">{fmtNum(result.suspicious_count, 0)}</div>
                <div className="stat-label">Flagged</div>
              </div>
              <div className="stat-card" style={{ '--accent-color': 'var(--red-400)', '--accent-bg': 'var(--red-900)' }}>
                <div className="stat-icon">✗</div>
                <div className="stat-value">{fmtNum(result.failed_count, 0)}</div>
                <div className="stat-label">Failed</div>
              </div>
            </div>
            <div style={{ marginTop: 16, display: 'flex', gap: 10 }}>
              <a href="/review" className="btn btn-primary btn-sm">Review rows →</a>
              <a href={`/batches/${result.batch_id}`} className="btn btn-secondary btn-sm">View batch →</a>
            </div>
          </div>
        )}
      </div>
    </>
  )
}
