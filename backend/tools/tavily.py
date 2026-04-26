import os
import asyncio
from dotenv import load_dotenv
from tavily import AsyncTavilyClient

load_dotenv()

async def get_business_phone_number(business_name: str, city: str) -> dict:
    """
    Searches Tavily specifically for the phone number of a business.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEY is missing. Check your .env file.")

    client = AsyncTavilyClient(api_key=api_key)
    
    # Hyper-specific query to discourage Tavily from returning history or reviews
    query = f"What is the official phone number for the establishment '{business_name}' located in {city}? Return only the phone number if possible."

    response = await client.search(
        query=query,
        search_depth="advanced",
        include_answer=True, 
        max_results=2 # We don't need a ton of results just to find a phone number
    )

    return {
        "business": business_name,
        "city": city,
        "phone_number_context": response.get("answer", "No phone number found."),
        "top_source_url": response["results"][0]["url"] if response.get("results") else None
    }

# Smoke Test
if __name__ == "__main__":
    async def test():
        print("🔍 Testing Tavily phone number extraction...")
        try:
            result = await get_business_phone_number("Katz's Delicatessen", "New York City")
            print("\n--- RESULTS ---")
            print(f"Business: {result['business']}")
            print(f"Phone Info: {result['phone_number_context']}")
            print(f"Source: {result['top_source_url']}")
        except Exception as e:
            print(f"❌ Error: {e}")

    asyncio.run(test())