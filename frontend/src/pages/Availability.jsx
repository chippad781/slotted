import { useEffect, useState } from 'react'
import api from '../api'

const DAYS = [
  { value: 0, label: 'Mon' },
  { value: 1, label: 'Tue' },
  { value: 2, label: 'Wed' },
  { value: 3, label: 'Thu' },
  { value: 4, label: 'Fri' },
  { value: 5, label: 'Sat' },
  { value: 6, label: 'Sun' },
]

export default function Availability() {
  const [rules, setRules] = useState([])
  const [blocks, setBlocks] = useState([])
  const [loading, setLoading] = useState(true)
  const [newRule, setNewRule] = useState({ day_of_week: 0, start_time: '09:00', end_time: '17:00' })
  const [newBlock, setNewBlock] = useState({ start: '', end: '', reason: '' })

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    try {
      const [r, b] = await Promise.all([
        api.get('/availability-rules/'),
        api.get('/blocks/'),
      ])
      setRules(r.data.results)
      setBlocks(b.data.results)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  async function addRule(e) {
    e.preventDefault()
    try {
      await api.post('/availability-rules/', newRule)
      setNewRule({ day_of_week: 0, start_time: '09:00', end_time: '17:00' })
      load()
    } catch (err) {
      alert(JSON.stringify(err.response?.data))
    }
  }

  async function removeRule(id) {
    if (!confirm('Remove this rule?')) return
    await api.delete(`/availability-rules/${id}/`)
    load()
  }

  async function addBlock(e) {
    e.preventDefault()
    try {
      // The datetime-local input gives local time; the browser will treat
      // it as local and the backend stores UTC. JS converts when we
      // pass it as an ISO string.
      const payload = {
        start: new Date(newBlock.start).toISOString(),
        end: new Date(newBlock.end).toISOString(),
        reason: newBlock.reason,
      }
      await api.post('/blocks/', payload)
      setNewBlock({ start: '', end: '', reason: '' })
      load()
    } catch (err) {
      alert(JSON.stringify(err.response?.data))
    }
  }

  async function removeBlock(id) {
    if (!confirm('Remove this block?')) return
    await api.delete(`/blocks/${id}/`)
    load()
  }

  // group rules by day for nicer display
  const rulesByDay = {}
  rules.forEach((r) => {
    if (!rulesByDay[r.day_of_week]) rulesByDay[r.day_of_week] = []
    rulesByDay[r.day_of_week].push(r)
  })

  return (
    <div>
      <h1>Availability</h1>
      <p className="muted">All times shown in your local timezone.</p>

      <div className="card">
        <h3>Weekly availability</h3>
        {loading ? <p>Loading...</p> : (
          <div className="day-grid">
            {DAYS.map((d) => (
              <div key={d.value} className="day-cell">
                <div className="day-label">{d.label}</div>
                {(rulesByDay[d.value] || []).map((r) => (
                  <div key={r.id} className="rule-pill">
                    {r.start_time.slice(0, 5)}–{r.end_time.slice(0, 5)}
                    <button className="x-btn" onClick={() => removeRule(r.id)} title="Remove">×</button>
                  </div>
                ))}
                {(rulesByDay[d.value] || []).length === 0 && (
                  <div className="muted small">unavailable</div>
                )}
              </div>
            ))}
          </div>
        )}

        <form onSubmit={addRule} className="inline-form">
          <select
            value={newRule.day_of_week}
            onChange={(e) => setNewRule({ ...newRule, day_of_week: parseInt(e.target.value) })}
          >
            {DAYS.map((d) => (
              <option key={d.value} value={d.value}>{d.label}</option>
            ))}
          </select>
          <input
            type="time"
            value={newRule.start_time}
            onChange={(e) => setNewRule({ ...newRule, start_time: e.target.value })}
          />
          <span>to</span>
          <input
            type="time"
            value={newRule.end_time}
            onChange={(e) => setNewRule({ ...newRule, end_time: e.target.value })}
          />
          <button type="submit">Add rule</button>
        </form>
      </div>

      <div className="card">
        <h3>One-off blocks (vacations, conflicts)</h3>
        {blocks.length === 0 ? (
          <p className="muted">No blocks set.</p>
        ) : (
          <ul className="block-list">
            {blocks.map((b) => (
              <li key={b.id}>
                <strong>{new Date(b.start).toLocaleString()}</strong>
                {' → '}
                <strong>{new Date(b.end).toLocaleString()}</strong>
                {b.reason && <span className="muted"> · {b.reason}</span>}
                <button className="link-btn danger" onClick={() => removeBlock(b.id)}>
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}

        <form onSubmit={addBlock} className="inline-form">
          <label>
            From
            <input
              type="datetime-local"
              value={newBlock.start}
              onChange={(e) => setNewBlock({ ...newBlock, start: e.target.value })}
              required
            />
          </label>
          <label>
            To
            <input
              type="datetime-local"
              value={newBlock.end}
              onChange={(e) => setNewBlock({ ...newBlock, end: e.target.value })}
              required
            />
          </label>
          <input
            type="text"
            placeholder="Reason (optional)"
            value={newBlock.reason}
            onChange={(e) => setNewBlock({ ...newBlock, reason: e.target.value })}
          />
          <button type="submit">Add block</button>
        </form>
      </div>
    </div>
  )
}
