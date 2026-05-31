import { Link, useNavigate } from 'react-router-dom'
import { isLoggedIn, getUser, clearTokens } from '../auth'

export default function Navbar() {
  const navigate = useNavigate()
  const loggedIn = isLoggedIn()
  const user = getUser()

  function handleLogout() {
    clearTokens()
    navigate('/login')
  }

  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <Link to="/" className="brand">Slotted</Link>
        <div className="nav-links">
          {loggedIn ? (
            <>
              <Link to="/dashboard">Dashboard</Link>
              <Link to="/event-types">Event Types</Link>
              <Link to="/availability">Availability</Link>
              <Link to="/bookings">Bookings</Link>
              {user && (
                <Link to={`/${user.username}`} className="muted">
                  /{user.username}
                </Link>
              )}
              <button className="link-btn" onClick={handleLogout}>Logout</button>
            </>
          ) : (
            <>
              <Link to="/login">Login</Link>
              <Link to="/register">Sign up</Link>
            </>
          )}
        </div>
      </div>
    </nav>
  )
}
