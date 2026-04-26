import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.telli.com/v1"


def _headers() -> dict:
    api_key = os.getenv("TELLI_API_KEY")
    if not api_key:
        raise ValueError("TELLI_API_KEY is missing. Check your .env file.")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


async def create_contact(
    phone_number: str,
    first_name: str,
    last_name: str,
    external_contact_id: str,
    contact_details: dict | None = None,
) -> str:
    """
    Registers a contact in Telli and returns the contact_id (UUID).
    contact_details: custom variables the AI agent can reference during the call
                     e.g. {"party_size": "2", "booking_time": "7pm", "booking_date": "2026-04-24"}
    """
    payload = {
        "external_contact_id": external_contact_id,
        "first_name": first_name,
        "last_name": last_name,
        "phone_number": phone_number,  # must be E.164, e.g. +4989123456
    }
    if contact_details:
        payload["contact_details"] = contact_details

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/add-contact",
            headers=_headers(),
            json=payload,
        )
        response.raise_for_status()
        return response.json()["contact_id"]


async def initiate_call(contact_id: str, agent_id: str) -> str:
    """
    Fires an immediate outbound call (no business-hours restriction).
    Returns the call_id for later status polling.
    """
    payload = {
        "contact_id": contact_id,
        "agent_id": agent_id,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/initiate-call",
            headers=_headers(),
            json=payload,
        )
        response.raise_for_status()
        return response.json()["call_id"]


async def get_call_result(call_id: str) -> dict:
    """
    Retrieves call data including transcript and outcome.
    Poll this after initiate_call — call may still be in progress.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/get-call/{call_id}",
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json()


async def book_via_telli(
    phone_number: str,
    business_name: str,
    agent_id: str,
    booking_details: dict,
) -> dict:
    """
    Full booking flow: create contact → initiate call → return call_id.
    booking_details: e.g. {"party_size": "2", "booking_time": "7pm", "booking_date": "2026-04-24"}
    """
    contact_id = await create_contact(
        phone_number=phone_number,
        first_name=business_name,
        last_name="",
        external_contact_id=f"{business_name.lower().replace(' ', '-')}-{phone_number}",
        contact_details=booking_details,
    )
    call_id = await initiate_call(contact_id=contact_id, agent_id=agent_id)
    return {"contact_id": contact_id, "call_id": call_id}


# Smoke test — requires TELLI_API_KEY and a valid AGENT_ID in your dashboard
if __name__ == "__main__":
    async def test():
        print("Testing Telli integration...")

        # Replace these with real values from your Telli dashboard
        TEST_PHONE = "+4989123456"
        TEST_AGENT_ID = "your-agent-id-here"

        try:
            result = await book_via_telli(
                phone_number=TEST_PHONE,
                business_name="Test Restaurant",
                agent_id=TEST_AGENT_ID,
                booking_details={
                    "party_size": "2",
                    "booking_time": "7pm",
                    "booking_date": "2026-04-24",
                },
            )
            print(f"Call initiated: {result}")

            print("Fetching call result (may still be in progress)...")
            call_data = await get_call_result(result["call_id"])
            print(f"Call data: {call_data}")

        except Exception as e:
            print(f"Error: {e}")

    asyncio.run(test())
