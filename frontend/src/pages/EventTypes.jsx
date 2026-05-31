import { useEffect, useState } from 'react'
import api from '../api'

const EMPTY = {
  title: '',
  slug: title.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, ''),
  description: '',
  duration_minutes: 30,
  buffer_before_minutes: 0,
  buffer_after_minutes: 0,
  advance_days: 14,
  is_active: true,
}

export default function EventTypes() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(null) // null | 'new' | id
  const [form, setForm] = useState(EMPTY)
  const [error, setError] = useState('')

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    try {
      const resp = await api.get('/event-types/')
      setItems(resp.data.results)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  function startNew() {
    setForm(EMPTY)
    setEditing('new')
    setError('')
  }

  function startEdit(item) {
    setForm({
      title: item.title,
      description: item.description,
      duration_minutes: item.duration_minutes,
      buffer_before_minutes: item.buffer_before_minutes,
      buffer_after_minutes: item.buffer_after_minutes,
      advance_days: item.advance_days,
      is_active: item.is_active,
    })
    setEditing(item.id)
    setError('')
  }

  async function handleSave(e) {
    e.preventDefault()
    setError('')
    try {
      if (editing === 'new') {
        const payload = { ...form, slug: form.title.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '') }
        await api.post('/event-types/', payload)
      } else {
        await api.patch(`/event-types/${editing}/`, form)
      }
      setEditing(null)
      load()
    } catch (err) {
      setError(JSON.stringify(err.response?.data || {}))
    }
  }

  async function handleDelete(id) {
    if (!confirm('Delete this event type? Bookings already made will be kept.')) return
    try {
      await api.delete(`/event-types/${id}/`)
      load()
    } catch (err) {
      alert('Could not delete — there may be active bookings.')
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Event Types</h1>
        <button onClick={startNew}>+ New event type</button>
      </div>

      {editing !== null && (
        <div className="card">
          <h3>{editing === 'new' ? 'New event type' : 'Edit event type'}</h3>
          <form onSubmit={handleSave}>
            <label>
              Title
              <input
                type="text"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                required
              />
            </label>
            <label>
              Description
              <textarea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                rows={3}
              />
            </label>
            <div className="form-row">
              <label>
                Duration (minutes)
                <input
                  type="number"
                  min={5}
                  max={480}
                  value={form.duration_minutes}
                  onChange={(e) => setForm({ ...form, duration_minutes: parseInt(e.target.value) })}
                />
              </label>
              <label>
                Buffer before
                <input
                  type="number"
                  min={0}
                  value={form.buffer_before_minutes}
                  onChange={(e) => setForm({ ...form, buffer_before_minutes: parseInt(e.target.value) })}
                />
              </label>
              <label>
                Buffer after
                <input
                  type="number"
                  min={0}
                  value={form.buffer_after_minutes}
                  onChange={(e) => setForm({ ...form, buffer_after_minutes: parseInt(e.target.value) })}
                />
              </label>
              <label>
                Advance days
                <input
                  type="number"
                  min={1}
                  max={60}
                  value={form.advance_days}
                  onChange={(e) => setForm({ ...form, advance_days: parseInt(e.target.value) })}
                />
              </label>
            </div>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              />
              Active (visible on your booking page)
            </label>
            {error && <div className="error">{error}</div>}
            <div className="form-actions">
              <button type="submit">Save</button>
              <button type="button" className="secondary" onClick={() => setEditing(null)}>
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {loading ? <p>Loading...</p> : items.length === 0 ? (
        <p className="muted">No event types yet. Create one to start taking bookings.</p>
      ) : (
        <div className="list">
          {items.map((item) => (
            <div key={item.id} className="card list-item">
              <div>
                <h3>{item.title} {!item.is_active && <span className="badge">inactive</span>}</h3>
                <p className="muted small">
                  {item.duration_minutes} min · /{item.slug}
                </p>
                {item.description && <p>{item.description}</p>}
              </div>
              <div className="item-actions">
                <button className="secondary" onClick={() => startEdit(item)}>Edit</button>
                <button className="danger" onClick={() => handleDelete(item.id)}>Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
