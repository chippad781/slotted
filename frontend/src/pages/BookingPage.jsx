import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import api from '../api'

// Generate a UUID-ish string for idempotency. Doesn't need to be cryptographic.
function makeIdempotencyKey() {
  return 'book-' + Math.random().toString(36).slice(2) + Date.now().toString(36)
}

// Same-day comparison in the *user's* local timezone.
function isSameDay(d1, d2) {
  return d1.getFullYear() === d2.getFullYear() &&
         d1.getMonth() === d2.getMonth() &&
         d1.getDate() === d2.getDate()
}

function formatDate(d) {
  return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
}

function isoDate(d) {
  // YYYY-MM-DD in *local* time so we don't shift days
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export default function BookingPage() {
  const { username, slug } = useParams()
  const [eventType, setEventType] = useState(null)
  const [slots, setSlots] = useState([])         // Date objects (UTC parsed)
  const [selectedDate, setSelectedDate] = useState(new Date())
  const [selectedSlot, setSelectedSlot] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // form state
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState(null)
  const [idempotencyKey] = useState(makeIdempotencyKey())

  const userTz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'

  useEffect(() => {
    async function load() {
      setLoading(true)
      try {
        const today = new Date()
        const future = new Date()
        future.setDate(today.getDate() + 14)
        const resp = await api.get(
          `/public/${username}/${slug}/slots/`,
          { params: { from: isoDate(today), to: isoDate(future) } }
        )
        setEventType(resp.data.event_type)
        setSlots(resp.data.slots.map((s) => new Date(s)))
      } catch (err) {
        setError(err.response?.status === 404 ? 'Event type not found.' : 'Could not load slots.')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [username, slug])

  if (loading) return <p>Loading...</p>
  if (error) return <div className="card"><p className="error">{error}</p></div>
  if (!eventType) return null

  if (success) {
    return (
      <div className="card">
        <h1>You're booked!</h1>
        <p>
          <strong>{eventType.title}</strong> with {eventType.host.display_name || eventType.host.username}
        </p>
        <p>
          <strong>{new Date(success.start).toLocaleString()}</strong>
        </p>
        <p className="muted">Confirmation email sent to {success.invitee_email}.</p>
      </div>
    )
  }

  // Slots for the currently selected day, in the user's local tz
  const todaysSlots = slots.filter((s) => isSameDay(s, selectedDate))

  // The next 14 days as date pickers
  const dayPicker = []
  for (let i = 0; i < 14; i++) {
    const d = new Date()
    d.setDate(d.getDate() + i)
    const hasSlots = slots.some((s) => isSameDay(s, d))
    dayPicker.push({ date: d, hasSlots })
  }

  async function handleBook(e) {
    e.preventDefault()
    if (!selectedSlot) return
    setSubmitting(true)
    setError('')
    try {
      const resp = await api.post('/public/bookings/', {
        event_type_id: eventType.id,
        start: selectedSlot.toISOString(),
        invitee_name: name,
        invitee_email: email,
        invitee_notes: notes,
        idempotency_key: idempotencyKey,
      })
      setSuccess(resp.data)
    } catch (err) {
      if (err.response?.status === 409) {
        setError('That time was just taken. Please pick another slot.')
        // refresh the slot list
        const today = new Date()
        const future = new Date()
        future.setDate(today.getDate() + 14)
        const r = await api.get(
          `/public/${username}/${slug}/slots/`,
          { params: { from: isoDate(today), to: isoDate(future) } }
        )
        setSlots(r.data.slots.map((s) => new Date(s)))
        setSelectedSlot(null)
      } else {
        setError(err.response?.data?.detail || 'Could not book. Try again.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="booking-page">
      <div className="event-info card">
        <h1>{eventType.title}</h1>
        <p className="muted">
          with {eventType.host.display_name || eventType.host.username}
          {' · '} {eventType.duration_minutes} min
        </p>
        {eventType.description && <p>{eventType.description}</p>}
        <p className="muted small">Times shown in {userTz}</p>
      </div>

      <div className="card">
        <h3>Pick a day</h3>
        <div className="day-picker">
          {dayPicker.map((d) => (
            <button
              key={d.date.toISOString()}
              className={
                'day-btn' +
                (isSameDay(d.date, selectedDate) ? ' active' : '') +
                (!d.hasSlots ? ' disabled' : '')
              }
              disabled={!d.hasSlots}
              onClick={() => { setSelectedDate(d.date); setSelectedSlot(null) }}
            >
              <div className="day-name">{d.date.toLocaleDateString(undefined, { weekday: 'short' })}</div>
              <div className="day-num">{d.date.getDate()}</div>
            </button>
          ))}
        </div>

        <h3>Pick a time — {formatDate(selectedDate)}</h3>
        {todaysSlots.length === 0 ? (
          <p className="muted">No times available this day.</p>
        ) : (
          <div className="slot-grid">
            {todaysSlots.map((s) => (
              <button
                key={s.toISOString()}
                className={'slot-btn' + (selectedSlot?.getTime() === s.getTime() ? ' active' : '')}
                onClick={() => setSelectedSlot(s)}
              >
                {s.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </button>
            ))}
          </div>
        )}
      </div>

      {selectedSlot && (
        <div className="card">
          <h3>Your details</h3>
          <p className="muted">
            Booking <strong>{selectedSlot.toLocaleString()}</strong>
          </p>
          <form onSubmit={handleBook}>
            <label>
              Name
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </label>
            <label>
              Email
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </label>
            <label>
              Notes (optional)
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                placeholder="Anything you'd like the host to know?"
              />
            </label>
            {error && <div className="error">{error}</div>}
            <button type="submit" disabled={submitting}>
              {submitting ? 'Booking...' : 'Confirm booking'}
            </button>
          </form>
        </div>
      )}
    </div>
  )
}
