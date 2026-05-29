import { useEffect, useState } from 'react'
import {
  getActivity, editActivity, approveActivity,
  rejectActivity, getActivityHistory
} from '../services/api'
import { fmtDate, fmtNum, fmtCurrency, fmtDateTime, scopeLabel } from '../utils/format'

const KV = ({ label, value, mono }) => (
  <div className="kv-row">
    <span className="kv-key">{label}</span>
    <span className={`kv-val${mono ? ' font-mono' : ''}`}>{value ?? '—'}</span>
  </div>
)

const ScopeBadge = ({ scope }) => {
  const cls = { '1': 'badge-scope1', '2': 'badge-scope2', '3': 'badge-scope3' }[scope]
  return <span className={`badge ${cls || ''}`}>{scopeLabel(scope)}</span>
}

const StatusBadge = ({ status }) => {
  const cls = {
    PENDING: 'badge-pending', APPROVED: 'badge-approved',
    REJECTED: 'badge-rejected', FLAGGED: 'badge-flagged'
  }[status] || ''
  return <span className={`badge ${cls}`}><span className="badge-dot" />{status}</span>
}

export default function ActivityDrawer({ activityId, onClose, onUpdated }) {
  const [activity, setActivity] = useState(null)
  const [history, setHistory] = useState([])
  const [tab, setTab] = useState('detail')
  const [editing, setEditing] = useState(false)
  const [editData, setEditData] = useState({})
  const [rejectReason, setRejectReason] = useState('')
  const [showReject, setShowReject] = useState(false)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!activityId) return
    setLoading(true)
    setTab('detail')
    setEditing(false)
    setError('')
    Promise.all([getActivity(activityId), getActivityHistory(activityId)])
      .then(([aRes, hRes]) => {
        setActivity(aRes.data)
        setHistory(hRes.data)
      })
      .catch(() => setError('Failed to load activity.'))
      .finally(() => setLoading(false))
  }, [activityId])

  const handleApprove = async () => {
    setActionLoading(true)
    setError('')
    try {
      await approveActivity(activityId)
      const res = await getActivity(activityId)
      setActivity(res.data)
      onUpdated?.()
    } catch (e) {
      setError(e.response?.data?.error || 'Approve failed')
    } finally { setActionLoading(false) }
  }

  const handleReject = async () => {
    if (!rejectReason.trim()) { setError('Provide a rejection reason.'); return }
    setActionLoading(true)
    setError('')
    try {
      await rejectActivity(activityId, rejectReason)
      const res = await getActivity(activityId)
      setActivity(res.data)
      setShowReject(false)
      onUpdated?.()
    } catch (e) {
      setError(e.response?.data?.error || 'Reject failed')
    } finally { setActionLoading(false) }
  }

  const handleSaveEdit = async () => {
    setActionLoading(true)
    setError('')
    try {
      await editActivity(activityId, editData)
      const res = await getActivity(activityId)
      setActivity(res.data)
      setEditing(false)
      setEditData({})
      onUpdated?.()
    } catch (e) {
      setError(e.response?.data?.error || 'Save failed')
    } finally { setActionLoading(false) }
  }

  return (
    <>
      <div className="drawer-overlay" onClick={onClose} />
      <div className="drawer" role="dialog" aria-label="Activity detail">
        <div className="drawer-header">
          <div>
            <h3 style={{ marginBottom: 6 }}>Activity Detail</h3>
            {activity && (
              <div className="flex gap-2 items-center" style={{ flexWrap: 'wrap' }}>
                <span className={`badge badge-${activity.source_type.toLowerCase()}`}>
                  {activity.source_type}
                </span>
                <ScopeBadge scope={activity.scope} />
                <StatusBadge status={activity.review_status} />
                {activity.suspicious_flag && (
                  <span className="badge badge-flagged">⚠ Suspicious</span>
                )}
                {activity.locked_for_audit && (
                  <span className="badge" style={{ background:'var(--purple-900)', color:'var(--purple-400)', border:'1px solid rgba(167,139,250,0.2)' }}>
                    🔒 Locked
                  </span>
                )}
              </div>
            )}
          </div>
          <button className="btn btn-secondary btn-icon" onClick={onClose}>✕</button>
        </div>

        {/* Tabs */}
        <div className="tabs" style={{ padding: '0 24px', marginBottom: 0 }}>
          {['detail', 'raw', 'history'].map(t => (
            <button key={t} className={`tab${tab === t ? ' active' : ''}`}
              onClick={() => setTab(t)}>
              {{ detail: 'Normalized', raw: 'Raw Payload', history: `History (${history.length})` }[t]}
            </button>
          ))}
        </div>

        <div className="drawer-body">
          {error && <div className="alert alert-error mb-3">{error}</div>}

          {loading ? (
            [...Array(6)].map((_, i) => (
              <div key={i} className="skeleton mb-2" style={{ height: 28 }} />
            ))
          ) : activity ? (
            <>
              {/* --- DETAIL TAB --- */}
              {tab === 'detail' && (
                <>
                  {activity.suspicious_flag && activity.suspicious_reasons?.length > 0 && (
                    <div className="alert alert-warning mb-4">
                      <div>
                        <strong>⚠ Flagged</strong>
                        <ul style={{ margin: '6px 0 0 16px', fontSize: '0.82rem' }}>
                          {activity.suspicious_reasons.map((r, i) => <li key={i}>{r}</li>)}
                        </ul>
                      </div>
                    </div>
                  )}

                  {activity.review_status === 'REJECTED' && activity.rejection_reason && (
                    <div className="alert alert-error mb-4">
                      <strong>Rejection reason:</strong> {activity.rejection_reason}
                    </div>
                  )}

                  {editing ? (
                    <div className="card-sm mb-4" style={{ border: '1px solid var(--green-500)' }}>
                      <h4 className="mb-3">Edit Fields</h4>
                      {[
                        { field: 'category', label: 'Category' },
                        { field: 'scope', label: 'Scope' },
                        { field: 'activity_date', label: 'Date', type: 'date' },
                        { field: 'normalized_quantity', label: 'Norm. Quantity', type: 'number' },
                        { field: 'normalized_unit', label: 'Norm. Unit' },
                        { field: 'site', label: 'Site' },
                        { field: 'description', label: 'Description' },
                      ].map(({ field, label, type = 'text' }) => (
                        <div key={field} className="form-group" style={{ marginBottom: 10 }}>
                          <label className="form-label">{label}</label>
                          <input
                            type={type}
                            defaultValue={activity[field] ?? ''}
                            onChange={e => setEditData(d => ({ ...d, [field]: e.target.value }))}
                          />
                        </div>
                      ))}
                    </div>
                  ) : (
                    <>
                      <div className="data-compare" style={{ gridTemplateColumns: '1fr' }}>
                        <div className="data-panel">
                          <h4>Activity Details</h4>
                          <KV label="Category"    value={activity.category} />
                          <KV label="Scope"        value={scopeLabel(activity.scope)} />
                          <KV label="Date"         value={fmtDate(activity.activity_date)} />
                          <KV label="Period"
                            value={activity.period_start
                              ? `${fmtDate(activity.period_start)} → ${fmtDate(activity.period_end)}`
                              : null} />
                          <KV label="Site"         value={activity.site || activity.raw_site_code} />
                          <KV label="Country"      value={activity.country} />
                          <KV label="Vendor"       value={activity.vendor} />
                          <KV label="Description"  value={activity.description} />
                          <KV label="Reference"    value={activity.reference_id} mono />
                        </div>
                      </div>

                      <div className="data-compare">
                        <div className="data-panel">
                          <h4>Original</h4>
                          <KV label="Quantity" value={`${fmtNum(activity.quantity)} ${activity.unit || ''}`} />
                          <KV label="Amount"   value={fmtCurrency(activity.amount, activity.currency)} />
                        </div>
                        <div className="data-panel">
                          <h4>Normalized</h4>
                          <KV label="Quantity" value={`${fmtNum(activity.normalized_quantity)} ${activity.normalized_unit || ''}`} />
                          <KV label="CO₂e est." value={activity.co2e_kg ? `${fmtNum(activity.co2e_kg, 2)} kg` : 'n/a'} />
                        </div>
                      </div>

                      {(activity.source_type === 'TRAVEL') && (
                        <div className="data-panel mb-3">
                          <h4>Travel Details</h4>
                          <KV label="Traveler"      value={activity.traveler_name} />
                          <KV label="Origin"        value={activity.origin} />
                          <KV label="Destination"   value={activity.destination} />
                          <KV label="Class"         value={activity.class_of_service} />
                          <KV label="Hotel nights"  value={activity.hotel_nights} />
                        </div>
                      )}

                      <div className="data-panel">
                        <h4>Audit Info</h4>
                        <KV label="Approved by"  value={activity.approved_by_username} />
                        <KV label="Approved at"  value={fmtDateTime(activity.approved_at)} />
                        <KV label="Source row"   value={`Line ${activity.source_row_line}`} />
                        <KV label="Created"      value={fmtDateTime(activity.created_at)} />
                        <KV label="Updated"      value={fmtDateTime(activity.updated_at)} />
                      </div>
                    </>
                  )}
                </>
              )}

              {/* --- RAW PAYLOAD TAB --- */}
              {tab === 'raw' && (
                <div>
                  <div className="alert alert-info mb-3">
                    This is the exact data as it arrived from the source file. It has not been modified.
                  </div>
                  <pre className="raw-json">
                    {JSON.stringify(activity.raw_payload, null, 2)}
                  </pre>
                </div>
              )}

              {/* --- HISTORY TAB --- */}
              {tab === 'history' && (
                <div>
                  {history.length === 0 ? (
                    <p>No audit events yet.</p>
                  ) : (
                    <div className="timeline">
                      {history.map(ev => (
                        <div key={ev.id} className={`timeline-event action-${ev.action.toLowerCase()}`}>
                          <div className="timeline-time">{fmtDateTime(ev.timestamp)}</div>
                          <div className="timeline-desc">
                            <strong>{ev.actor_username || 'system'}</strong>
                            {' '}{ev.action.toLowerCase()}d this record
                            {ev.notes ? ` — "${ev.notes}"` : ''}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          ) : null}
        </div>

        {/* Footer actions */}
        {activity && !activity.locked_for_audit && (
          <div className="drawer-footer">
            {showReject ? (
              <div style={{ flex: 1 }}>
                <input
                  placeholder="Rejection reason (required)"
                  value={rejectReason}
                  onChange={e => setRejectReason(e.target.value)}
                  style={{ marginBottom: 8 }}
                />
                <div className="flex gap-2 justify-between">
                  <button className="btn btn-secondary btn-sm" onClick={() => setShowReject(false)}>
                    Cancel
                  </button>
                  <button className="btn btn-danger btn-sm" onClick={handleReject} disabled={actionLoading}>
                    {actionLoading ? '…' : 'Confirm Reject'}
                  </button>
                </div>
              </div>
            ) : editing ? (
              <>
                <button className="btn btn-secondary" onClick={() => { setEditing(false); setEditData({}) }}>
                  Cancel
                </button>
                <button className="btn btn-primary" onClick={handleSaveEdit} disabled={actionLoading}>
                  {actionLoading ? 'Saving…' : 'Save Changes'}
                </button>
              </>
            ) : (
              <>
                <button className="btn btn-secondary btn-sm" onClick={() => setEditing(true)}>
                  ✎ Edit
                </button>
                <button className="btn btn-danger btn-sm" onClick={() => setShowReject(true)}>
                  ✗ Reject
                </button>
                {activity.review_status !== 'APPROVED' && (
                  <button
                    className="btn btn-success"
                    onClick={handleApprove}
                    disabled={actionLoading}
                    id="approve-btn"
                  >
                    {actionLoading ? '…' : '✓ Approve & Lock'}
                  </button>
                )}
              </>
            )}
          </div>
        )}

        {activity?.locked_for_audit && (
          <div className="drawer-footer">
            <div className="alert alert-info" style={{ flex: 1, margin: 0 }}>
              🔒 This record is locked for audit and cannot be edited.
            </div>
          </div>
        )}
      </div>
    </>
  )
}
