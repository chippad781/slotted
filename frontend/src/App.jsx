import { Routes, Route, Navigate } from 'react-router-dom'

import Navbar from './components/Navbar.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'

import Login from './pages/Login.jsx'
import Register from './pages/Register.jsx'
import Dashboard from './pages/Dashboard.jsx'
import EventTypes from './pages/EventTypes.jsx'
import Availability from './pages/Availability.jsx'
import Bookings from './pages/Bookings.jsx'
import PublicPage from './pages/PublicPage.jsx'
import BookingPage from './pages/BookingPage.jsx'

export default function App() {
  return (
    <div className="app">
      <Navbar />
      <main className="container">
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          <Route path="/dashboard" element={
            <ProtectedRoute><Dashboard /></ProtectedRoute>
          } />
          <Route path="/event-types" element={
            <ProtectedRoute><EventTypes /></ProtectedRoute>
          } />
          <Route path="/availability" element={
            <ProtectedRoute><Availability /></ProtectedRoute>
          } />
          <Route path="/bookings" element={
            <ProtectedRoute><Bookings /></ProtectedRoute>
          } />

          {/* public booking flow */}
          <Route path="/:username" element={<PublicPage />} />
          <Route path="/:username/:slug" element={<BookingPage />} />
        </Routes>
      </main>
    </div>
  )
}
