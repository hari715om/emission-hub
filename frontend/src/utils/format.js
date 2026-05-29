export const fmtDate = (d) => {
  if (!d) return '—'
  return new Date(d + 'T00:00:00').toLocaleDateString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric'
  })
}

export const fmtNum = (n, decimals = 2) => {
  if (n === null || n === undefined) return '—'
  return Number(n).toLocaleString('en-GB', {
    minimumFractionDigits: 0,
    maximumFractionDigits: decimals,
  })
}

export const fmtCurrency = (amount, currency = 'GBP') => {
  if (amount === null || amount === undefined) return '—'
  try {
    return new Intl.NumberFormat('en-GB', { style: 'currency', currency }).format(amount)
  } catch {
    return `${currency} ${fmtNum(amount)}`
  }
}

export const fmtDateTime = (d) => {
  if (!d) return '—'
  return new Date(d).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  })
}

export const fmtFileSize = (bytes) => {
  if (!bytes) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export const scopeLabel = (s) => ({ '1': 'Scope 1', '2': 'Scope 2', '3': 'Scope 3' }[s] || '—')

export const sourceLabel = (s) => ({
  SAP: 'SAP Fuel & Procurement',
  UTILITY: 'Utility Electricity',
  TRAVEL: 'Corporate Travel',
}[s] || s)
