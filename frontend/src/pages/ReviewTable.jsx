import { useEffect, useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getActivities, bulkApprove } from '../services/api'
import { fmtDate, fmtNum, fmtCurrency, scopeLabel } from '../utils/format'
import ActivityDrawer from '../components/ActivityDrawer'

const StatusBadge = ({ status }) => {
  const cls = {
    PENDING: 'badge-pending', APPROVED: 'badge-approved',
    REJECTED: 'badge-rejected', FLAGGED: 'badge-flagged'
  }[status] || ''
  return <span className={`badge ${cls}`}><span className="badge-dot" />{status}</span>
}

const ScopeBadge = ({ scope }) => {
  if (!scope) return <span className="text-muted">—</span>
  const cls = { '1': 'badge-scope1', '2': 'badge-scope2', '3': 'badge-scope3' }[scope]
  return <span className={`badge ${cls}`}>{scopeLabel(scope)}</span>
}

const PAGE_SIZE = 50

export default function ReviewTable() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [activities, setActivities] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(new Set())
  const [drawerOpen, setDrawerOpen] = useState(null)
  const [bulkLoading, setBulkLoading] = useState(false)
  const [successMsg, setSuccessMsg] = useState('')

  // Filters from URL params
  const page         = parseInt(searchParams.get('page') || '1')
  const statusFilter = searchParams.get('status') || ''
  const scopeFilter  = searchParams.get('scope') || ''
  const sourceFilter = searchParams.get('source_type') || ''
  const suspFilter   = searchParams.get('suspicious_flag') || ''
  const searchQ      = searchParams.get('search') || ''
  const batchFilter  = searchParams.get('batch') || ''

  const setParam = (key, val) => {
    const p = new URLSearchParams(searchParams)
    if (val) p.set(key, val); else p.delete(key)
    p.set('page', '1')
    setSearchParams(p)
    setSelected(new Set())
  }

  const fetchActivities = useCallback(() => {
    setLoading(true)
    getActivities({
      review_status: statusFilter || undefined,
      scope: scopeFilter || undefined,
      source_type: sourceFilter || undefined,
      suspicious_flag: suspFilter || undefined,
      search: searchQ || undefined,
      batch: batchFilter || undefined,
      page,
      page_size: PAGE_SIZE,
    })
      .then(r => {
        setActivities(r.data.results || r.data)
        setTotal(r.data.count || 0)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [statusFilter, scopeFilter, sourceFilter, suspFilter, searchQ, batchFilter, page])

  useEffect(() => { fetchActivities() }, [fetchActivities])

  const toggleSelect = (id) => {
    setSelected(s => {
      const n = new Set(s)
      n.has(id) ? n.delete(id) : n.add(id)
      return n
    })
  }

  const toggleAll = () => {
    if (selected.size === activities.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(activities.map(a => a.id)))
    }
  }

  const handleBulkApprove = async () => {
    if (!selected.size) return
    setBulkLoading(true)
    try {
      const res = await bulkApprove(Array.from(selected))
      setSuccessMsg(`✓ ${res.data.approved} rows approved and locked`)
      setSelected(new Set())
      fetchActivities()
      setTimeout(() => setSuccessMsg(''), 3000)
    } catch (e) {
      console.error(e)
    } finally { setBulkLoading(false) }
  }

  const allPending = activities.filter(a =>
    !a.locked_for_audit && (a.review_status === 'PENDING' || a.review_status === 'FLAGGED')
  )

  return (
    <>
      <div className="page-header">
        <div className="page-title-row">
          <div>
            <div className="breadcrumb">Platform › Review</div>
            <h1>Review & Approve</h1>
          </div>
          {selected.size > 0 && (
            <button
              id="bulk-approve-btn"
              className="btn btn-success"
              onClick={handleBulkApprove}
              disabled={bulkLoading}
            >
              {bulkLoading ? 'Approving…' : `✓ Approve ${selected.size} selected`}
            </button>
          )}
        </div>
      </div>

      <div className="page-body">
        {successMsg && <div className="alert alert-success mb-4">{successMsg}</div>}

        {/* Filter bar */}
        <div className="filters-bar">
          <input
            className="search-input"
            placeholder="Search vendor, site, reference, traveler…"
            value={searchQ}
            onChange={e => setParam('search', e.target.value)}
          />
          <select className="filter-select" value={statusFilter}
            onChange={e => setParam('status', e.target.value)}>
            <option value="">All Statuses</option>
            <option value="PENDING">Pending</option>
            <option value="FLAGGED">Flagged</option>
            <option value="APPROVED">Approved</option>
            <option value="REJECTED">Rejected</option>
          </select>
          <select className="filter-select" value={sourceFilter}
            onChange={e => setParam('source_type', e.target.value)}>
            <option value="">All Sources</option>
            <option value="SAP">SAP</option>
            <option value="UTILITY">Utility</option>
            <option value="TRAVEL">Travel</option>
          </select>
          <select className="filter-select" value={scopeFilter}
            onChange={e => setParam('scope', e.target.value)}>
            <option value="">All Scopes</option>
            <option value="1">Scope 1</option>
            <option value="2">Scope 2</option>
            <option value="3">Scope 3</option>
          </select>
          <select className="filter-select" value={suspFilter}
            onChange={e => setParam('suspicious_flag', e.target.value)}>
            <option value="">All rows</option>
            <option value="true">Suspicious only</option>
            <option value="false">Clean only</option>
          </select>
        </div>

        {/* Bulk action context bar */}
        {selected.size > 0 && (
          <div className="alert alert-info mb-3" style={{ justifyContent: 'space-between' }}>
            <span>{selected.size} row{selected.size > 1 ? 's' : ''} selected</span>
            <button className="btn btn-secondary btn-sm" onClick={() => setSelected(new Set())}>
              Clear selection
            </button>
          </div>
        )}

        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th className="checkbox-cell">
                  <input
                    type="checkbox"
                    checked={selected.size === allPending.length && allPending.length > 0}
                    onChange={toggleAll}
                    title="Select all reviewable"
                  />
                </th>
                <th>Source</th>
                <th>Category</th>
                <th>Scope</th>
                <th>Date</th>
                <th>Site / Route</th>
                <th>Quantity</th>
                <th>CO₂e kg</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Flags</th>
              </tr>
            </thead>
            <tbody>
              {loading
                ? [...Array(10)].map((_, i) => (
                    <tr key={i}>
                      {[...Array(11)].map((_, j) => (
                        <td key={j}><div className="skeleton" style={{ height: 14 }} /></td>
                      ))}
                    </tr>
                  ))
                : activities.length === 0
                ? (
                  <tr>
                    <td colSpan={11} style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-muted)' }}>
                      No activities match your filters.
                    </td>
                  </tr>
                )
                : activities.map(a => {
                    const isSelectable = !a.locked_for_audit &&
                      (a.review_status === 'PENDING' || a.review_status === 'FLAGGED')
                    const isSuspicious = a.suspicious_flag
                    return (
                      <tr
                        key={a.id}
                        className={`${selected.has(a.id) ? 'row-selected' : ''} ${isSuspicious && a.review_status !== 'APPROVED' ? 'row-suspicious' : ''}`}
                        onClick={() => setDrawerOpen(a.id)}
                      >
                        <td className="checkbox-cell" onClick={e => e.stopPropagation()}>
                          <input
                            type="checkbox"
                            checked={selected.has(a.id)}
                            disabled={!isSelectable}
                            onChange={() => toggleSelect(a.id)}
                          />
                        </td>
                        <td>
                          <span className={`badge badge-${a.source_type.toLowerCase()}`}>
                            {a.source_type}
                          </span>
                        </td>
                        <td style={{ fontWeight: 500 }}>
                          {a.category.replace(/_/g, ' ')}
                        </td>
                        <td><ScopeBadge scope={a.scope} /></td>
                        <td className="text-muted">{fmtDate(a.activity_date)}</td>
                        <td>
                          <span className="truncate">
                            {a.source_type === 'TRAVEL' && a.origin
                              ? `${a.origin} → ${a.destination}`
                              : a.site || a.raw_site_code || '—'}
                          </span>
                        </td>
                        <td className="font-mono">
                          {a.normalized_quantity
                            ? `${fmtNum(a.normalized_quantity, 1)} ${a.normalized_unit}`
                            : '—'}
                        </td>
                        <td className="font-mono" style={{ color: 'var(--green-400)' }}>
                          {a.co2e_kg ? fmtNum(a.co2e_kg, 1) : '—'}
                        </td>
                        <td>{fmtCurrency(a.amount, a.currency)}</td>
                        <td><StatusBadge status={a.review_status} /></td>
                        <td>
                          {a.suspicious_flag && (
                            <span className="badge badge-flagged" title={a.suspicious_reasons?.join('\n')}>
                              ⚠
                            </span>
                          )}
                          {a.locked_for_audit && (
                            <span style={{ marginLeft: 4 }}>🔒</span>
                          )}
                        </td>
                      </tr>
                    )
                  })
              }
            </tbody>
          </table>

          <div className="pagination">
            <span>{total} activities · {allPending.length} reviewable on this page</span>
            <div className="pagination-btns">
              <button
                className="btn btn-secondary btn-sm"
                disabled={page === 1}
                onClick={() => {
                  const p = new URLSearchParams(searchParams)
                  p.set('page', String(page - 1))
                  setSearchParams(p)
                }}
              >← Prev</button>
              <span className="btn btn-secondary btn-sm" style={{ cursor: 'default' }}>
                {page} / {Math.ceil(total / PAGE_SIZE) || 1}
              </span>
              <button
                className="btn btn-secondary btn-sm"
                disabled={page * PAGE_SIZE >= total}
                onClick={() => {
                  const p = new URLSearchParams(searchParams)
                  p.set('page', String(page + 1))
                  setSearchParams(p)
                }}
              >Next →</button>
            </div>
          </div>
        </div>
      </div>

      {drawerOpen && (
        <ActivityDrawer
          activityId={drawerOpen}
          onClose={() => setDrawerOpen(null)}
          onUpdated={() => {
            fetchActivities()
            setDrawerOpen(null)
          }}
        />
      )}
    </>
  )
}
