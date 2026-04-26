from src.store import bookings


async def run_booking_pipeline(call_id: str, request: str):
    bookings[call_id]["status"] = "running"
    try:
        # intent = await gemini.parse(request)
        # business = await tavily.find(intent)
        # call = await telli.call(business["phone"], script=intent["script"])
        bookings[call_id]["status"] = "done"
        bookings[call_id]["result"] = f"Booked: {request}"
    except Exception as e:
        bookings[call_id]["status"] = "error"
        bookings[call_id]["error"] = str(e)
