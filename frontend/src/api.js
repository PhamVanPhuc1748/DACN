// Lớp gọi API: tự gắn JWT, tự đăng xuất khi token hết hạn.
const KEY = 'pigderm.session'

export const session = {
  get: () => JSON.parse(localStorage.getItem(KEY) || 'null'),
  set: (s) => localStorage.setItem(KEY, JSON.stringify(s)),
  clear: () => localStorage.removeItem(KEY),
}

export async function api(path, { method = 'GET', body, form, raw } = {}) {
  const headers = {}
  const token = session.get()?.token
  if (token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const res = await fetch(path, { method, headers, body: form ?? (body !== undefined ? JSON.stringify(body) : undefined) })
  if (res.status === 401 && token) {
    session.clear()
    location.reload()
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(typeof err.detail === 'string' ? err.detail : `Lỗi ${res.status}`)
  }
  return raw ? res : res.json()
}

export async function download(path, filename) {
  const blob = await (await api(path, { raw: true })).blob()
  const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: filename })
  a.click()
  URL.revokeObjectURL(a.href)
}

export const qs = (o) => new URLSearchParams(Object.entries(o).filter(([, v]) => v !== '' && v != null && v !== false)).toString()
