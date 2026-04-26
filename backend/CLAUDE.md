# Hackathon Booking Bot — Claude Context

## What This Project Is

Voice-activated booking system for a one-day hackathon. The user says what they want to book, the system figures out where, calls the business, and handles the reservation conversation autonomously.

## Goal for the Hackathon

Build a working demo of the full pipeline. The priority is end-to-end flow, not polish.

## Project Structure

```
main.py           # FastAPI app entry point
tools/
  gemini.py       # Google Gemini integration
  tavily.py       # Tavily search integration
  telli.py        # Telli calling integration
  gradium.py      # Gradium voice integration
.env              # API keys (never commit this)
.env.example      # Template for required keys
```

## Tool Integrations

Each tool lives in its own file under `tools/`. Keep implementations simple — the goal is to learn the API, not build production-grade wrappers.

### Google Gemini (`tools/gemini.py`)
- Use `google-genai` SDK
- Model: `gemini-1.5-flash` or `gemini-2.0-flash`
- Tasks: parse user intent, extract booking details, generate a call script

### Tavily (`tools/tavily.py`)
- Use `tavily-python` SDK
- Task: search for business name + city → return phone number and address

### Telli (`tools/telli.py`)
- REST API with `httpx`
- Task: initiate outbound call to a phone number with a script or agent config

### Gradium (`tools/gradium.py`)
- REST API or SDK with `httpx`
- Task: handle the voice layer (text-to-speech, speech-to-text) during the call

## Environment Variables

```
GEMINI_API_KEY=
TAVILY_API_KEY=
TELLI_API_KEY=
GRADIUM_API_KEY=
```

## Coding Conventions

- Python 3.14, FastAPI, async where possible
- Simple functions, no over-engineering
- One file per external tool
- Load secrets via `python-dotenv`, never hardcode keys
- Keep each tool file independently testable (include a `if __name__ == "__main__"` block for quick smoke tests)
