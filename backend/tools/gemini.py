import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

MODEL = "gemini-3-flash-preview"

def _client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


# 1. Regular call — single prompt, single response
def simple_call(prompt: str) -> str:
    response = _client().models.generate_content(model=MODEL, contents=prompt)
    return response.text


# 2. System instruction — set role/persona before the user message
def call_with_system(system: str, prompt: str) -> str:
    response = _client().models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=system),
    )
    return response.text


# 3. Streaming — yield tokens as they arrive (useful for real-time voice output)
def stream_call(prompt: str):
    for chunk in _client().models.generate_content_stream(model=MODEL, contents=prompt):
        print(chunk.text, end="", flush=True)


# 4. Multi-turn chat — maintains conversation history across exchanges
def chat_example():
    chat = _client().chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(
            system_instruction="You are a booking assistant. Help the user reserve tables, appointments, and time slots."
        ),
    )
    response = chat.send_message("I want to book a table for 2 in Munich tonight.")
    print(response.text)
    response = chat.send_message("Make it for 8pm.")
    print(response.text)
    return chat  # keep the chat object to continue the session


# 5. Function calling — Gemini decides when to call your tools and with what args
def function_calling_example(user_message: str):
    search_tool = types.FunctionDeclaration(
        name="search_business",
        description="Search for a business by type and city, returns phone number",
        parameters_json_schema={
            "type": "object",
            "properties": {
                "business_type": {"type": "string", "description": "e.g. sushi restaurant"},
                "city": {"type": "string", "description": "e.g. Munich"},
            },
            "required": ["business_type", "city"],
        },
    )

    response = _client().models.generate_content(
        model=MODEL,
        contents=user_message,
        config=types.GenerateContentConfig(
            tools=[types.Tool(function_declarations=[search_tool])]
        ),
    )

    if response.function_calls:
        call = response.function_calls[0]
        print(f"Gemini wants to call: {call.name} with args {call.args}")
        # TODO: execute the actual function and send result back to Gemini
    else:
        print(response.text)


# 6. Simulate call — streaming multi-turn chat that mimics a real phone call
# booking_request: what we want to book
# caller_replies: list of things the business says (simulated STT output from Gradium)
# yields streamed text chunks — in production these go to Gradium TTS
async def simulate_call_stream(booking_request: str, caller_replies: list[str]):
    chat = _client().chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(
            system_instruction=(
                "You are an AI booking assistant making a phone call on behalf of a customer. "
                "Be polite and concise. Your goal is to complete the booking as efficiently as possible."
            )
        ),
    )

    # Opening line — we initiate the call
    opening = f"Hello, I'd like to {booking_request}."
    yield f"[WE SAY]: {opening}\n"

    for caller_reply in caller_replies:
        yield f"[CALLER]: {caller_reply}\n[WE SAY]: "
        for chunk in chat.send_message_stream(caller_reply):
            if chunk.text:
                yield chunk.text
        yield "\n"


if __name__ == "__main__":
    print("=== Simple call ===")
    print(simple_call("Say hello in one sentence."))

    print("\n=== System instruction ===")
    print(call_with_system("You speak like a pirate.", "What time is it?"))

    print("\n=== Streaming ===")
    stream_call("Count to 5 slowly.")
    print()

    print("\n=== Multi-turn chat ===")
    chat_example()

    print("\n=== Function calling ===")
    function_calling_example("I want to book a sushi restaurant in Munich tonight.")
