import asyncio
import base64
import json
import os
import uuid
from fastapi import FastAPI, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from src.store import bookings
from src.pipeline import run_booking_pipeline
from tools.gemini import simulate_call_stream
from tools.tavily import get_business_phone_number
from tools.gradium import tts_stream
from dotenv import load_dotenv
import websockets
from src.roi.router import router as roi_router

# Load env vars on startup
load_dotenv()
app = FastAPI()
app.include_router(roi_router)

### Regular Fast API ###

# helper classes for test
class BookingRequest(BaseModel):
    request: str  # e.g. "Book a table for 2 at a sushi place in Munich tonight at 7pm"

# POST with JSON body — kicks off pipeline in background, returns call_id immediately
@app.post("/book")
async def book(body: BookingRequest, background_tasks: BackgroundTasks):
    call_id = str(uuid.uuid4())
    bookings[call_id] = {"status": "queued", "request": body.request}
    background_tasks.add_task(run_booking_pipeline, call_id, body.request)
    return {"call_id": call_id, "status": "queued"}


# GET with path param — check status of a booking
@app.get("/status/{call_id}")
async def status(call_id: str):
    if call_id not in bookings:
        return {"error": "not found"}
    return bookings[call_id]


# GET with query param — example: /search?query=sushi+Munich
@app.get("/search")
async def search(query: str):
    return {"query": query, "result": "TODO: hook up Tavily here"}

### Gemini API ###

class SimulateCallRequest(BaseModel):
    phone_number: str       # pretend number, not actually dialed
    booking_request: str    # e.g. "table for 2 at 8pm"
    caller_replies: list[str]  # simulated responses from the business


# POST /simulate-call — streams a full booking conversation with Gemini
# Pretends we already have the phone number and are mid-call
# caller_replies simulates what the business says, we stream Gemini's responses back
@app.post("/simulate-call")
async def simulate_call(body: SimulateCallRequest):
    return StreamingResponse(
        simulate_call_stream(body.booking_request, body.caller_replies),
        media_type="text/plain",
    )

### Gradium API ###

class TTSRequest(BaseModel):
    text: str

@app.post("/tts")
async def tts(body: TTSRequest):
    async def audio_generator():
        async for chunk in tts_stream(body.text):
            yield chunk
    return StreamingResponse(audio_generator(), media_type="audio/octet-stream")

@app.post("/tts-file")
async def tts_file(body: TTSRequest):
    import wave, io
    chunks = []
    async for chunk in tts_stream(body.text):
        chunks.append(chunk)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(48000)
        for chunk in chunks:
            wf.writeframes(chunk)
    return StreamingResponse(io.BytesIO(buf.getvalue()), media_type="audio/wav")

@app.websocket("/stt")
async def stt(websocket: WebSocket):
    await websocket.accept()
    headers = {"x-api-key": os.getenv("GRADIUM_API_KEY")}
    try:
        async with websockets.connect("wss://api.gradium.ai/api/speech/asr", additional_headers=headers) as gradium_ws:
            await gradium_ws.send(json.dumps({"type": "setup", "model_name": "default", "input_format": "pcm"}))
            await gradium_ws.recv()  # wait for ready

            async def forward_audio():
                try:
                    async for frame in websocket.iter_bytes():
                        await gradium_ws.send(json.dumps({
                            "type": "audio",
                            "audio": base64.b64encode(frame).decode(),
                        }))
                except WebSocketDisconnect:
                    pass
                finally:
                    try:
                        await gradium_ws.send(json.dumps({"type": "end_of_stream"}))
                    except Exception:
                        pass

            async def forward_transcripts():
                try:
                    while True:
                        msg = json.loads(await gradium_ws.recv())
                        if msg["type"] == "text":
                            await websocket.send_text(msg.get("text", ""))
                        elif msg["type"] == "end_of_stream":
                            break
                except (websockets.exceptions.ConnectionClosed, WebSocketDisconnect):
                    pass

            await asyncio.gather(forward_audio(), forward_transcripts())
    except WebSocketDisconnect:
        pass

@app.get("/test", response_class=None)
async def test_page():
    from fastapi.responses import HTMLResponse
    html = """<!DOCTYPE html>
<html>
<head><title>Gradium Test</title>
<style>
  body { font-family: sans-serif; max-width: 600px; margin: 60px auto; padding: 0 20px; }
  h2 { margin-top: 40px; }
  textarea, input { width: 100%; padding: 8px; margin: 8px 0; box-sizing: border-box; }
  button { padding: 10px 20px; margin: 4px 0; cursor: pointer; }
  #transcript { min-height: 60px; padding: 10px; border: 1px solid #ccc; margin-top: 8px; white-space: pre-wrap; }
  .recording { background: #fee; border-color: red; }
</style>
</head>
<body>

<h1>Gradium Test</h1>

<h2>TTS</h2>
<textarea id="tts-text" rows="3" placeholder="Enter text to speak...">Hello! I'd like to book a table for two at 7pm tonight.</textarea>
<button onclick="runTTS()">Speak</button>
<audio id="tts-audio" controls style="width:100%;margin-top:8px;display:none"></audio>

<h2>STT</h2>
<button id="stt-btn" onclick="toggleSTT()">Start recording</button>
<div id="transcript">Transcript will appear here...</div>

<script>
async function runTTS() {
  const text = document.getElementById('tts-text').value;
  const audio = document.getElementById('tts-audio');
  audio.style.display = 'none';

  const res = await fetch('/tts-file', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({text})
  });

  const blob = await res.blob();
  audio.src = URL.createObjectURL(blob);
  audio.style.display = 'block';
  audio.play();
}

let ws, audioCtx, mediaStream, sourceNode, processorNode;
let recording = false;

async function toggleSTT() {
  if (!recording) {
    recording = true;
    document.getElementById('stt-btn').textContent = 'Stop recording';
    document.getElementById('transcript').textContent = '';
    document.getElementById('transcript').classList.add('recording');
    await startSTT();
  } else {
    stopSTT();
  }
}

async function startSTT() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/stt`);
  ws.onmessage = (e) => {
    document.getElementById('transcript').textContent += e.data + ' ';
  };

  mediaStream = await navigator.mediaDevices.getUserMedia({audio: true});
  // Force 24kHz so frames match what Gradium expects (1920 samples = 80ms)
  audioCtx = new AudioContext({sampleRate: 24000});
  sourceNode = audioCtx.createMediaStreamSource(mediaStream);
  processorNode = audioCtx.createScriptProcessor(2048, 1, 1);

  processorNode.onaudioprocess = (e) => {
    if (ws.readyState !== WebSocket.OPEN) return;
    const float32 = e.inputBuffer.getChannelData(0);
    const int16 = new Int16Array(float32.length);
    for (let i = 0; i < float32.length; i++) {
      int16[i] = Math.max(-32768, Math.min(32767, float32[i] * 32768));
    }
    ws.send(int16.buffer);
  };

  sourceNode.connect(processorNode);
  processorNode.connect(audioCtx.destination);
}

function stopSTT() {
  recording = false;
  document.getElementById('stt-btn').textContent = 'Start recording';
  document.getElementById('transcript').classList.remove('recording');
  if (processorNode) { processorNode.disconnect(); sourceNode.disconnect(); }
  if (audioCtx) audioCtx.close();
  if (mediaStream) mediaStream.getTracks().forEach(t => t.stop());
  if (ws) ws.close();
}
</script>
</body>
</html>"""
    return HTMLResponse(html)

### Tavily API ###

class PhoneNumberRequest(BaseModel):
    business_name: str
    city: str

@app.post("/api/phone-number")
async def fetch_phone_number(request: PhoneNumberRequest):
    """
    Endpoint to fetch a business phone number using Tavily.
    Accepts JSON: {"business_name": "Name", "city": "City"}
    """
    try:
        details = await get_business_phone_number(
            business_name=request.business_name,
            city=request.city
        )
        return {"status": "success", "data": details}
    
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")