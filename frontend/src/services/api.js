import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || ''

const api = axios.create({
  baseURL: `${BASE}/api/v1`,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

// Attach CSRF token from cookie for Django session auth
api.interceptors.request.use((config) => {
  const csrfToken = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='))
    ?.split('=')[1]
  if (csrfToken) config.headers['X-CSRFToken'] = csrfToken
  return config
})

// Dashboard
export const getDashboardStats = (tenantId) =>
  api.get('/dashboard/stats/', { params: tenantId ? { tenant_id: tenantId } : {} })

// Auth
export const login = (username, password) =>
  axios.post(`${BASE}/api/auth/login/`, { username, password }, { withCredentials: true })

export const logout = () =>
  axios.post(`${BASE}/api/auth/logout/`, {}, { withCredentials: true })

export const getMe = () =>
  axios.get(`${BASE}/api/auth/me/`, { withCredentials: true })

// Tenants
export const getTenants = () => api.get('/tenants/')

// Batches
export const getBatches = (params) => api.get('/batches/', { params })
export const getBatch = (id) => api.get(`/batches/${id}/`)

// Activities (review)
export const getActivities = (params) => api.get('/activities/', { params })
export const getActivity = (id) => api.get(`/activities/${id}/`)
export const editActivity = (id, data) => api.patch(`/activities/${id}/`, data)
export const approveActivity = (id) => api.post(`/activities/${id}/approve/`)
export const rejectActivity = (id, reason) => api.post(`/activities/${id}/reject/`, { reason })
export const bulkApprove = (ids) => api.post('/activities/bulk-approve/', { ids })
export const getActivityHistory = (id) => api.get(`/activities/${id}/history/`)

// Upload
export const uploadFile = (sourceType, file, tenantId) => {
  const form = new FormData()
  form.append('file', file)
  if (tenantId) form.append('tenant_id', tenantId)
  return api.post(`/ingestion/${sourceType}/upload/`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// Audit
export const getAuditEvents = (params) => api.get('/audit-events/', { params })

export default api
