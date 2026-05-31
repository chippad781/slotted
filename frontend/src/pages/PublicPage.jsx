import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import api from '../api'

export default function PublicPage() {
  const { username } = useParams()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    async function load() {
      try {
        const resp = await api.get(`/public/${username}/`)
        setData(resp.data)
      } catch (err) {
        if (err.response?.status === 404) {
          setError('This user does not exist.')
        } else {
          setError('Could not load page.')
        }
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [username])

  if (loading) return <p>Loading...</p>
  if (error) return <div className="card"><p className="error">{error}</p></div>

  return (
    <div className="public-page">
      <div className="profile-header">
        <h1>{data.host.display_name}</h1>
        <p className="muted">@{data.host.username}</p>
        {data.host.bio && <p>{data.host.bio}</p>}
      </div>

      <h2>Book a time</h2>
      {data.event_types.length === 0 ? (
        <p className="muted">No event types available yet.</p>
      ) : (
        <div className="list">
          {data.event_types.map((et) => (
            <Link
              to={`/${username}/${et.slug}`}
              key={et.id}
              className="card event-type-card"
            >
              <h3>{et.title}</h3>
              <p className="muted small">{et.duration_minutes} minutes</p>
              {et.description && <p>{et.description}</p>}
              <span className="arrow">→</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
