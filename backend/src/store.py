# In-memory store — shared across all requests, resets on server restart
bookings: dict[str, dict] = {}
