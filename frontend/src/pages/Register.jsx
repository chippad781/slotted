import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import api from '../api'
import { setTokens, setUser } from '../auth'

// Sensible default — picks up the browser's tz so the user doesn't
// have to fill it in.
const browserTz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'

export default function Register() {
  const [form, setForm] = useState({
    email: '',
    username: '',
    password: '',
    display_name: '',
    timezone: browserTz,
  })
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  function update(key, value) {
    setForm({ ...form, [key]: value })
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setErrors({})
    setLoading(true)
    try {
      const resp = await api.post('/auth/register/', form)
      setTokens({ access: resp.data.access, refresh: resp.data.refresh })
      setUser(resp.data.user)
      navigate('/dashboard')
    } catch (err) {
      setErrors(err.response?.data || { _: 'Something went wrong.' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="form-card">
      <h1>Create your account</h1>
      <form onSubmit={handleSubmit}>
        <label>
          Email
          <input
            type="email"
            value={form.email}
            onChange={(e) => update('email', e.target.value)}
            required
          />
          {errors.email && <span className="error">{errors.email}</span>}
        </label>
        <label>
          Username
          <span className="hint">This shows up in your booking URL — /{form.username || 'username'}</span>
          <input
            type="text"
            value={form.username}
            onChange={(e) => update('username', e.target.value.toLowerCase())}
            required
            pattern="[a-z0-9_-]+"
          />
          {errors.username && <span className="error">{errors.username}</span>}
        </label>
        <label>
          Display name
          <input
            type="text"
            value={form.display_name}
            onChange={(e) => update('display_name', e.target.value)}
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={form.password}
            onChange={(e) => update('password', e.target.value)}
            required
            minLength={8}
          />
          {errors.password && <span className="error">{errors.password}</span>}
        </label>
        <label>
          Timezone
          <input
            type="text"
            value={form.timezone}
            onChange={(e) => update('timezone', e.target.value)}
          />
        </label>
        {errors._ && <div className="error">{errors._}</div>}
        <button type="submit" disabled={loading}>
          {loading ? 'Creating...' : 'Sign up'}
        </button>
      </form>
      <p className="muted">
        Already have an account? <Link to="/login">Log in</Link>
      </p>
    </div>
  )
}
