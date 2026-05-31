import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../api'
import { getUser } from '../auth'

export default function Dashboard() {
  const [stats, setStats] = useState({ upcoming: 0, total: 0, eventTypes: 0 })
  const [upcoming, setUpcoming] = useState([])
  const [loading, setLoading] = useState(true)
  const user = getUser()

  useEffect(() => {
    async function load() {
      try {
        const [upcomingResp, allResp, etResp] = await Promise.all([
          api.get('/bookings/?upcoming=true'),
          api.get('/bookings/'),
          api.get('/event-types/'),
        ])
        setStats({
          upcoming: upcomingResp.data.count,
          total: allResp.data.count,
          eventTypes: etResp.data.count,
        })
        setUpcoming(upcomingResp.data.results.slice(0, 5))
      } catch (err) {
        console.error(err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const publicUrl = `${window.location.origin}/${user?.username || ''}`

  return (
    <div>
      <h1>Hi, {user?.display_name || user?.username}</h1>

      <div className="card">
        <h3>Your booking page</h3>
        <p className="muted">Share this link so people can book time with you:</p>
        <div className="link-box">
          <code>{publicUrl}</code>
          <button onClick={() => navigator.clipboard.writeText(publicUrl)}>
            Copy
          </button>
        </div>
      </div>

      {loading ? <p>Loading...</p> : (
        <>
          <div className="stats-row">
            <div className="stat">
              <div className="stat-num">{stats.upcoming}</div>
              <div className="stat-label">Upcoming</div>
            </div>
            <div className="stat">
              <div className="stat-num">{stats.total}</div>
              <div className="stat-label">Total bookings</div>
            </div>
            <div className="stat">
              <div className="stat-num">{stats.eventTypes}</div>
              <div className="stat-label">Event types</div>
            </div>
          </div>

          <div className="card">
            <h3>Next 5 bookings</h3>
            {upcoming.length === 0 ? (
              <p className="muted">Nothing scheduled. <Link to="/event-types">Set up an event type</Link> to start taking bookings.</p>
            ) : (
              <ul className="booking-list">
                {upcoming.map((b) => (
                  <li key={b.id}>
                    <strong>{b.invitee_name}</strong> — {b.event_type_title}
                    <div className="muted small">
                      {new Date(b.start).toLocaleString()}
                    </div>
                  </li>
                ))}
              </ul>
            )}
            <Link to="/bookings">See all →</Link>
          </div>
        </>
      )}
    </div>
  )
}
