import { useEffect, useState } from 'react'
import api from '../api'

export default function Bookings() {
  const [bookings, setBookings] = useState([])
  const [filter, setFilter] = useState('upcoming') // upcoming | all | cancelled
  const [loading, setLoading] = useState(true)

  useEffect(() => { load() }, [filter])

  async function load() {
    setLoading(true)
    try {
      let url = '/bookings/'
      if (filter === 'upcoming') url += '?upcoming=true&status=confirmed'
      else if (filter === 'cancelled') url += '?status=cancelled'
      const resp = await api.get(url)
      setBookings(resp.data.results)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  async function cancel(id) {
    const reason = prompt('Reason (optional):') || ''
    try {
      await api.post(`/bookings/${id}/cancel/`, { reason })
      load()
    } catch (err) {
      alert('Could not cancel.')
    }
  }

  return (
    <div>
      <h1>Bookings</h1>

      <div className="tabs">
        <button
          className={filter === 'upcoming' ? 'tab active' : 'tab'}
          onClick={() => setFilter('upcoming')}
        >Upcoming</button>
        <button
          className={filter === 'all' ? 'tab active' : 'tab'}
          onClick={() => setFilter('all')}
        >All</button>
        <button
          className={filter === 'cancelled' ? 'tab active' : 'tab'}
          onClick={() => setFilter('cancelled')}
        >Cancelled</button>
      </div>

      {loading ? <p>Loading...</p> : bookings.length === 0 ? (
        <p className="muted">No bookings to show.</p>
      ) : (
        <div className="list">
          {bookings.map((b) => (
            <div key={b.id} className="card list-item">
              <div>
                <h3>
                  {b.invitee_name}
                  {b.status === 'cancelled' && <span className="badge danger">cancelled</span>}
                </h3>
                <p className="muted small">
                  {b.event_type_title} ({b.duration_minutes} min)
                </p>
                <p>
                  <strong>{new Date(b.start).toLocaleString()}</strong>
                </p>
                <p className="muted small">{b.invitee_email}</p>
                {b.invitee_notes && (
                  <p className="notes">"{b.invitee_notes}"</p>
                )}
              </div>
              <div className="item-actions">
                {b.status === 'confirmed' && new Date(b.start) > new Date() && (
                  <button className="danger" onClick={() => cancel(b.id)}>Cancel</button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
