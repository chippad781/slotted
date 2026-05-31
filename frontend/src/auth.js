// JWT storage. Using localStorage for simplicity.
// In production, httpOnly cookies are safer (XSS) but require backend changes.
const ACCESS_KEY = 'slotted_access'
const REFRESH_KEY = 'slotted_refresh'
const USER_KEY = 'slotted_user'

export const getAccessToken = () => localStorage.getItem(ACCESS_KEY)
export const getRefreshToken = () => localStorage.getItem(REFRESH_KEY)

export const setAccessToken = (token) => localStorage.setItem(ACCESS_KEY, token)

export const setTokens = ({ access, refresh }) => {
  localStorage.setItem(ACCESS_KEY, access)
  localStorage.setItem(REFRESH_KEY, refresh)
}

export const setUser = (user) => localStorage.setItem(USER_KEY, JSON.stringify(user))
export const getUser = () => {
  const raw = localStorage.getItem(USER_KEY)
  return raw ? JSON.parse(raw) : null
}

export const clearTokens = () => {
  localStorage.removeItem(ACCESS_KEY)
  localStorage.removeItem(REFRESH_KEY)
  localStorage.removeItem(USER_KEY)
}

export const isLoggedIn = () => !!getAccessToken()
