import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getBatches } from '../services/api'
import { fmtDateTime, fmtFileSize, fmtNum } from '../utils/format'

const STATUS_DOT = { DONE:'🟢', PROCESSING:'🟡', FAILED:'🔴', PENDING:'⚪' }

export default function BatchList() {
  const [batches, setBatches] = useState([])
  const [loading, setLoading] = useState(true)
  const [sourceFilter, setSourceFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const PAGE_SIZE = 20

  useEffect(() => {
    setLoading(true)
    getBatches({
      source_type: sourceFilter || undefined,
      status: statusFilter || undefined,
      page,
      page_size: PAGE_SIZE,
    })
      .then(r => {
        setBatches(r.data.results || r.data)
        setTotal(r.data.count || 0)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [sourceFilter, statusFilter, page])

  return (
    <>
      <div className="page-header">
        <div className="page-title-row">
          <div>
            <div className="breadcrumb">Platform › Batches</div>
            <h1>Ingestion Batches</h1>
          </div>
          <Link to="/upload" className="btn btn-primary">↑ New Upload</Link>
        </div>
      </div>

      <div className="page-body">
        <div className="filters-bar">
          <select
            id="filter-source"
            className="filter-select"
            value={sourceFilter}
            onChange={e => { setSourceFilter(e.target.value); setPage(1) }}
          >
            <option value="">All Sources</option>
            <option value="SAP">SAP</option>
            <option value="UTILITY">Utility</option>
            <option value="TRAVEL">Travel</option>
          </select>
          <select
            id="filter-status"
            className="filter-select"
            value={statusFilter}
            onChange={e => { setStatusFilter(e.target.value); setPage(1) }}
          >
            <option value="">All Statuses</option>
            <option value="DONE">Done</option>
            <option value="PROCESSING">Processing</option>
            <option value="FAILED">Failed</option>
            <option value="PENDING">Pending</option>
          </select>
        </div>

        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Source</th>
                <th>File Name</th>
                <th>Status</th>
                <th>Total</th>
                <th>OK</th>
                <th>Failed</th>
                <th>Flagged</th>
                <th>Size</th>
                <th>Uploaded</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {loading
                ? [...Array(8)].map((_, i) => (
                    <tr key={i}>
                      {[...Array(10)].map((_, j) => (
                        <td key={j}><div className="skeleton" style={{ height: 14, width: '80%' }} /></td>
                      ))}
                    </tr>
                  ))
                : batches.map(b => (
                    <tr key={b.id}>
                      <td><span className={`badge badge-${b.source_type.toLowerCase()}`}>{b.source_type}</span></td>
                      <td><span className="truncate font-mono" style={{ maxWidth: 220 }}>{b.file_name}</span></td>
                      <td>{STATUS_DOT[b.status]} {b.status}</td>
                      <td>{fmtNum(b.total_rows, 0)}</td>
                      <td style={{ color: 'var(--green-500)' }}>{fmtNum(b.success_count, 0)}</td>
                      <td style={{ color: b.failed_count > 0 ? 'var(--red-400)' : 'var(--text-muted)' }}>
                        {fmtNum(b.failed_count, 0)}
                      </td>
                      <td style={{ color: b.suspicious_count > 0 ? 'var(--amber-400)' : 'var(--text-muted)' }}>
                        {fmtNum(b.suspicious_count, 0)}
                      </td>
                      <td className="text-muted">{fmtFileSize(b.file_size_bytes)}</td>
                      <td className="text-muted">{fmtDateTime(b.uploaded_at)}</td>
                      <td>
                        <Link to={`/batches/${b.id}`} className="btn btn-secondary btn-sm">Details</Link>
                      </td>
                    </tr>
                  ))
              }
            </tbody>
          </table>

          <div className="pagination">
            <span>{total} batches total</span>
            <div className="pagination-btns">
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
              >← Prev</button>
              <span className="btn btn-secondary btn-sm" style={{ cursor: 'default' }}>
                Page {page} of {Math.ceil(total / PAGE_SIZE) || 1}
              </span>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setPage(p => p + 1)}
                disabled={page * PAGE_SIZE >= total}
              >Next →</button>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
