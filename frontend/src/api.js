import axios from 'axios'
import { getAccessToken, clearTokens, setAccessToken, getRefreshToken } from './auth'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

const api = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// crude refresh-on-401 retry. Not bulletproof but works for the portfolio.
let isRefreshing = false
api.interceptors.response.use(
  (resp) => resp,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      const refresh = getRefreshToken()
      if (!refresh) {
        clearTokens()
        return Promise.reject(error)
      }
      try {
        if (!isRefreshing) {
          isRefreshing = true
          const r = await axios.post(`${API_URL}/auth/refresh/`, { refresh })
          setAccessToken(r.data.access)
          isRefreshing = false
        }
        original.headers.Authorization = `Bearer ${getAccessToken()}`
        return api(original)
      } catch (e) {
        clearTokens()
        return Promise.reject(e)
      }
    }
    return Promise.reject(error)
  }
)

export default api
