import asyncio
import base64
import json
import os
import subprocess
import tempfile
import wave

try:
    import pyaudio
    _PYAUDIO_AVAILABLE = True
except ImportError:
    _PYAUDIO_AVAILABLE = False

import websockets
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GRADIUM_API_KEY")
TTS_WS_URL = "wss://api.gradium.ai/api/speech/tts"
STT_WS_URL = "wss://api.gradium.ai/api/speech/asr"

# STT expects PCM 24kHz, 16-bit mono, 1920 samples per frame (80ms)
STT_SAMPLE_RATE = 24000
STT_FRAME_SIZE = 1920


async def tts_stream(text: str, voice_id: str = "YTpq7expH9539ERJ"):  # Emma, US English
    """Connect to Gradium TTS and yield raw WAV audio bytes as they arrive."""
    headers = {"x-api-key": API_KEY}
    async with websockets.connect(TTS_WS_URL, additional_headers=headers) as ws:
        await ws.send(json.dumps({
            "type": "setup",
            "voice_id": voice_id,
            "model_name": "default",
            "output_format": "pcm",  # raw PCM so we can build a valid WAV ourselves
        }))

        msg = json.loads(await ws.recv())
        assert msg["type"] == "ready", f"Unexpected: {msg}"

        await ws.send(json.dumps({"type": "text", "text": text}))
        await ws.send(json.dumps({"type": "end_of_stream"}))

        chunk_count = 0
        while True:
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10.0))
                if msg["type"] == "end_of_stream":
                    print(f"  [tts] end_of_stream after {chunk_count} chunks")
                    break
                if msg["type"] == "audio":
                    chunk_count += 1
                    yield base64.b64decode(msg["audio"])
                else:
                    print(f"  [tts] unexpected msg: {msg}")
            except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
                print(f"  [tts] stream ended after {chunk_count} chunks")
                break


async def stt_stream(duration_seconds: int = 5):
    """Record from mic and stream to Gradium STT, yielding transcription strings."""
    headers = {"x-api-key": API_KEY}

    pa = pyaudio.PyAudio()
    mic = pa.open(
        rate=STT_SAMPLE_RATE,
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        frames_per_buffer=STT_FRAME_SIZE,
    )

    try:
        async with websockets.connect(STT_WS_URL, additional_headers=headers) as ws:
            await ws.send(json.dumps({
                "type": "setup",
                "model_name": "default",
                "input_format": "pcm",
            }))

            msg = json.loads(await ws.recv())
            assert msg["type"] == "ready", f"Unexpected: {msg}"

            num_frames = (duration_seconds * STT_SAMPLE_RATE) // STT_FRAME_SIZE

            async def send_audio():
                for _ in range(num_frames):
                    frame = mic.read(STT_FRAME_SIZE, exception_on_overflow=False)
                    await ws.send(json.dumps({
                        "type": "audio",
                        "audio": base64.b64encode(frame).decode(),
                    }))
                    await asyncio.sleep(0.08)  # pace to real-time (80ms frames)
                await ws.send(json.dumps({"type": "end_of_stream"}))

            send_task = asyncio.create_task(send_audio())

            while True:
                try:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2.0))
                    if msg["type"] == "text":
                        yield msg.get("text", "")
                    elif msg["type"] == "end_of_stream":
                        break
                except asyncio.TimeoutError:
                    break

            await send_task
    finally:
        mic.stop_stream()
        mic.close()
        pa.terminate()


if __name__ == "__main__":
    async def test_tts():
        print("--- TTS test ---")
        chunks = []
        async for chunk in tts_stream("Hello! I'd like to book a table for two at 7pm tonight."):
            chunks.append(chunk)
            print(f"  received {len(chunk)} bytes")

        # Write a proper WAV file from raw PCM chunks (48kHz, 16-bit, mono)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(48000)
            for chunk in chunks:
                wf.writeframes(chunk)

        total = sum(len(c) for c in chunks)
        print(f"Total audio: {total} bytes, playing...")
        subprocess.run(["afplay", path])

    async def test_stt():
        print("--- STT test — speak for 5 seconds ---")
        async for text in stt_stream(duration_seconds=5):
            print(f"  transcript: {text}")

    async def main():
        await test_tts()
        # await test_stt()

    asyncio.run(main())
