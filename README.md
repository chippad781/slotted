# Slotted

A self-hosted Cal.com-style scheduling platform. Pick a username, set your
weekly availability, and share `slotted.app/<your-username>` for people to
book time with you.

Built with Django + DRF + Postgres + Redis + Celery on the backend and
React (Vite) on the frontend.

## Demo

- Backend: `https://slotted-api.onrender.com`
- Frontend: [https://slotted-sooty.vercel.app/dashboard](https://slotted-sooty.vercel.app/dashboard)
- ### Dashboard

![Slotted dashboard](docs/dashboard.png)

## Features

- Email + password auth with JWT
- Multiple event types per user (e.g. "15min intro", "30min interview")
- Weekly recurring availability rules (per weekday, in host's timezone)
- One-off blocks for vacations and conflicts
- Public booking page with day picker, time grid, and timezone-aware display
- **Double-booking protection** via row-level locking + a partial unique
  constraint (see [Decisions](#decisions))
- Email confirmations and 24-hour reminders sent asynchronously via Celery
- Redis caching for availability lookups, invalidated on writes
- Rate limiting on the public booking endpoint
- Idempotency keys so a double-clicked submit doesn't create two bookings

## Tech stack

| Layer | What |
|---|---|
| Backend | Django 5, Django REST Framework, simplejwt |
| Database | PostgreSQL 16 |
| Cache / queue broker | Redis 7 |
| Async work | Celery |
| Frontend | React 18, Vite, react-router-dom, axios |
| Container | Docker + docker-compose |
| Testing | pytest, pytest-django |
| Deploy | Render (backend + Postgres + Redis), Vercel (frontend) |

## Architecture

```
                     ┌──────────────┐
   Browser ───────►  │  React/Vite  │
                     └──────┬───────┘
                            │ HTTPS
                            ▼
                     ┌──────────────┐
                     │ Django + DRF │ ◄────── JWT auth
                     │  (gunicorn)  │
                     └─┬──────┬─────┘
                       │      │
            ┌──────────┘      └────────┐
            ▼                          ▼
      ┌──────────┐                ┌─────────┐
      │ Postgres │                │  Redis  │
      └──────────┘                └────┬────┘
                                       │
                                       │ broker
                                       ▼
                                  ┌──────────┐
                                  │  Celery  │ ──► SMTP
                                  │  worker  │
                                  └──────────┘
```

## Local setup

The fast path is Docker Compose, which boots the database, Redis, Django,
the Celery worker, and the frontend in one command.

```bash
git clone <this-repo>
cd slotted
cp backend/.env.example backend/.env
docker compose up --build
```

Then visit `http://localhost:5173`.

The Django admin is at `http://localhost:8000/admin/` (create a superuser
with `docker compose exec backend python manage.py createsuperuser`).

### Without Docker

```bash
# Postgres + Redis must already be running locally.

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # edit POSTGRES_HOST=localhost, REDIS_URL=redis://localhost:6379/0
python manage.py migrate
python manage.py runserver

# Celery worker (in another terminal)
celery -A slotted worker -l info

# Frontend (in another terminal)
cd frontend
npm install
npm run dev
```

## Running tests

```bash
cd backend
pytest
```

Of particular interest:

- `scheduling/tests/test_availability.py` — slot generation, buffers, blocks
- `scheduling/tests/test_booking.py` — booking endpoint, idempotency, DB
  constraints
- `scheduling/tests/test_concurrency.py` — two threads racing for the same
  slot; exactly one wins

## API endpoints

### Auth
- `POST /api/auth/register/` → register + receive tokens
- `POST /api/auth/login/` → email + password → access + refresh tokens
- `POST /api/auth/refresh/` → refresh access token
- `GET /api/auth/me/` → current user
- `PATCH /api/auth/me/` → update profile

### Host (authenticated)
- `GET/POST /api/event-types/`
- `GET/PATCH/DELETE /api/event-types/{id}/`
- `GET/POST /api/availability-rules/`
- `DELETE /api/availability-rules/{id}/`
- `GET/POST /api/blocks/`
- `DELETE /api/blocks/{id}/`
- `GET /api/bookings/?upcoming=true&status=confirmed`
- `POST /api/bookings/{id}/cancel/`

### Public (no auth)
- `GET /api/public/{username}/` → host profile + event types
- `GET /api/public/{username}/{slug}/slots/?from=YYYY-MM-DD&to=YYYY-MM-DD`
- `POST /api/public/bookings/` → create a booking

## Decisions

A few things worth calling out for anyone reading the code.

### How we prevent double-booking

This is the central correctness problem in any scheduling app. Two people
clicking "Book 3pm Tuesday" at the same time should not both succeed.

The solution has three layers:

1. **A pessimistic lock at booking time.** Inside the booking transaction
   we do `User.objects.select_for_update().get(pk=host_id)` — this locks
   the host's user row for the duration of the transaction. Any other
   booking attempt for the same host has to wait until we commit (or
   abort). See `scheduling/views.py::CreateBookingView`.

2. **A re-check inside the lock.** Just because the slot was free when we
   checked at the start of the request doesn't mean it's still free now
   that we hold the lock — somebody else may have just committed. So we
   call `is_slot_available()` again *inside* the transaction.

3. **A partial unique constraint as the safety net.** On the `Booking`
   model:
   ```python
   models.UniqueConstraint(
       fields=['host', 'start'],
       condition=models.Q(status='confirmed'),
       name='unique_host_start_when_confirmed',
   )
   ```
   If the application logic ever has a bug, the database will refuse the
   second insert. We catch `IntegrityError` and return 409.

The concurrency test (`test_concurrency.py`) fires two threads at the
same slot and asserts that exactly one gets 201 and the other gets 409.

### Time zones

Times are always stored as UTC in the database. The host's timezone is a
property of the user (set at signup, defaulted from the browser). The
availability calculator does its work in the host's local timezone (so
DST works correctly) and converts to UTC before returning slots. The
frontend then converts back to the *invitee's* local timezone for
display. This is the standard pattern; the most common mistake is doing
arithmetic in UTC and ending up with slots that drift one hour every six
months when DST kicks in.

### Caching

Computing available slots is the expensive operation — for a 14-day
window with 30-minute slots and 8h workdays, we generate ~225 candidate
slots and check each against blocks and bookings. We cache the result in
Redis with a 60s TTL, keyed by `(host_id, event_type_id, date_range)`.

The cache is invalidated whenever something that affects availability
changes: a new booking, a cancellation, a new availability rule, a new
block. We use `cache.delete_pattern("avail:{host_id}:*")` for this. The
short TTL means even if invalidation ever missed, staleness is bounded.

### Celery for emails

Sending email is a network call that can be slow or fail. We don't want
the booking POST to hang on an SMTP round trip — so confirmations,
reminders, and cancellation notices are all fired off as Celery tasks.

For the 24-hour reminder we use `apply_async(eta=booking.start - 24h)`
rather than running a separate cron. Celery's scheduler handles the
timing; the worker just sees a task that runs at a specific moment.

### Idempotency

The booking endpoint accepts an optional `idempotency_key`. The frontend
generates one when the user opens the booking form. If the same key
shows up twice (e.g. user double-clicked "Confirm"), the second request
returns the existing booking instead of creating a new one.

### Why ViewSets here, APIView there

The host's CRUD endpoints (event types, blocks, etc.) are
`ModelViewSet` — they're vanilla CRUD and the routers make them concise.
The public booking creation endpoint is a plain `APIView` because the
input shape (just a slot start) doesn't match the model shape (which
needs both start and end), and there's enough custom logic (locking,
idempotency, cache invalidation) that ViewSet's hooks would just get in
the way.

### What's missing / what I'd add next

- Google Calendar / Outlook two-way sync
- `.ics` file attachment in confirmation emails
- Team round-robin scheduling
- Payment-gated bookings (Stripe)
- Booking cancellation/reschedule links for invitees (token-based, no
  account needed)
- A proper SMS reminder channel
- Frontend testing with React Testing Library

## Deploying

### Backend (Render)

1. New Web Service from this repo, root directory `backend/`.
2. Build command: `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
3. Start command: `gunicorn slotted.wsgi:application --bind 0.0.0.0:$PORT`
4. Add a Postgres add-on and a Redis add-on.
5. Set env vars: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`,
   `DJANGO_ALLOWED_HOSTS=slotted-api.onrender.com`, plus the DB and
   Redis connection strings Render provides.
6. Add a second Worker service with the same env and start command
   `celery -A slotted worker -l info`.

### Frontend (Vercel)

1. Import the repo into Vercel, set root directory `frontend/`.
2. Set `VITE_API_URL=https://slotted-api.onrender.com/api`.
3. Deploy.

Don't forget to set `CORS_ALLOWED_ORIGINS` on the backend to your
Vercel URL.

## License

MIT.
