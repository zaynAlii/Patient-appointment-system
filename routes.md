# API Routes

Use this file to track the route implementation one endpoint at a time. Route paths below are router-level paths; the application-wide prefix is TBD when FastAPI/router registration is added.

## Status Key

- `Present`: route decorator and handler exist in source; runtime registration/behavior not yet verified.
- `Implemented (registration pending)`: route, validation, and CRUD logic are implemented; app/router registration and database integration are still pending.
- `In progress`: currently being implemented.
- `Not started`: planned, no handler yet.
- `Replaced`: temporary route was replaced by its canonical route.

## Existing Routes

| Status | Method | Path | Audience | Functionality |
| --- | --- | --- | --- | --- |
| Present | POST | `/user/sign-up` | Public | Register a doctor account and return authentication tokens. |
| Present | POST | `/user/login` | Public | Authenticate a doctor and return tokens. |
| Present | POST | `/user/profile/info` | Authenticated doctor | Create the authenticated doctor's profile. |
| Replaced | POST | `/user/docter-availability` | Authenticated doctor | Replaced by the bulk weekly schedule update below. |

## Planned Routes

Implement these individually and update each status as work progresses.

| Status | Method | Path | Audience | Functionality |
| --- | --- | --- | --- | --- |
| Implemented (registration pending) | PUT | `/doctors/me/availability` | Authenticated doctor | Replace the doctor's recurring weekly schedule in one request. Body contains configured weekdays and one or more non-overlapping start/end intervals per day. Preserve any existing bookings that conflict with schedule edits; reject unsafe changes. |
| Implemented (registration pending) | GET | `/doctors/me/availability` | Authenticated doctor | Return the doctor's saved recurring weekly intervals in the same grouped shape accepted by the PUT route, for pre-filling the schedule editor. |
| Implemented (registration pending) | PATCH | `/doctors/me/profile` | Authenticated doctor | Partially update only submitted profile fields. Nullable fields such as qualification and bio may be cleared; reject null for required fields and prevent slot-duration changes that would invalidate future booked appointments. |
| Implemented (registration pending) | GET | `/doctors/{doctor_id}/profile` | Public | Return allow-listed public profile information and doctor's display name. Do not return account email, role, password hash, or other private user fields. |
| Implemented (registration pending) | GET | `/doctors/{doctor_id}/schedule?from_date=YYYY-MM-DD` | Public | Return a rolling seven-calendar-day schedule starting on `from_date` (defaults to today in the doctor's clinic timezone). Include only configured workdays, today's elapsed slots with status, and slot status only (`available`, `booked`, `completed`). Never return appointment IDs or patient information. |
| Implemented (registration pending) | POST | `/doctors/{doctor_id}/appointments` | Public | Book an available slot. Accept date, start time, consultation type, and patient contact details (full name, phone, address; optional date of birth and visit reason). Re-check availability atomically; return conflict if already booked or in the past. Return a one-time patient access token in the successful confirmation. |
| Implemented (registration pending) | GET | `/patient/appointments/me` | Public with appointment token | Return the appointment and clinic details for the appointment identified by the `X-Appointment-Token` header. The appointment ID alone is not accepted as proof. |
| Implemented (registration pending) | PATCH | `/patient/appointments/me/cancel` | Public with appointment token | Cancel the token owner's booked appointment if the request reaches the backend at least 30 minutes before its start, using the doctor's clinic timezone. Keep the appointment as cancelled history and release its slot. |
| Implemented (registration pending) | GET | `/doctors/me/appointments?from_date=YYYY-MM-DD&to_date=YYYY-MM-DD&status=booked&offset=0&limit=50` | Authenticated doctor | Return the doctor's appointments and patient details. Optional inclusive date bounds, repeatable status filter, and bounded pagination; omitted filters do not restrict the matching set. Enforce ownership on the server. |
| Implemented (registration pending) | PATCH | `/doctors/me/appointments/{appointment_id}` | Authenticated doctor | Update an owned appointment's lifecycle status, such as marking it completed or cancelled. Cancellation releases the slot but preserves appointment history. |

## Implementation Order

1. `PUT /doctors/me/availability`
2. `GET /doctors/me/availability` (implemented; registration pending)
3. `PATCH /doctors/me/profile` (implemented; registration pending)
4. `GET /doctors/{doctor_id}/profile` (implemented; registration pending)
5. `GET /doctors/{doctor_id}/schedule` (implemented; registration pending)
6. `POST /doctors/{doctor_id}/appointments` (implemented; registration pending)
7. `GET /patient/appointments/me` (implemented; registration pending)
8. `PATCH /patient/appointments/me/cancel` (implemented; registration pending)
9. `GET /doctors/me/appointments` (implemented; registration pending)
10. `PATCH /doctors/me/appointments/{appointment_id}` (implemented; registration pending)

## Contract Notes

- Weekly availability is recurring configuration. Appointment rows represent real bookings; `available` is computed and is not stored as an appointment status.
- All schedule dates and times use the doctor's clinic timezone, which must be included in the schedule response.
- The rolling window is today plus the following six calendar days, ordered by date. Dates before today are excluded. Past slots on today remain visible with their status but cannot be booked.
- Public responses contain status only. Patient identity/contact fields and appointment IDs are doctor-only.
- The booking confirmation returns the patient's high-entropy access token once. Store only its SHA-256 hash; accept the raw token through `X-Appointment-Token` for patient self-service lookup. Never log or return the stored hash.
- Patient cancellation uses that same token and is allowed when at least 30 minutes remain before the appointment, evaluated by the backend after locking the appointment row and using clinic-local time.
- Doctor controls must be authorized by the backend; hiding controls in the frontend is not authorization.
- Doctor profile PATCH updates only explicitly provided fields; changing slot duration must not invalidate future booked appointments.
- The doctor appointments GET applies date and status filters plus pagination server-side and returns `total_count`, `offset`, and `limit` metadata.
- Cancellation is a status update rather than a hard delete, preserving history and allowing the slot to become available again.
- Real-time push updates are deferred; phase one uses normal HTTP request/response behavior.
