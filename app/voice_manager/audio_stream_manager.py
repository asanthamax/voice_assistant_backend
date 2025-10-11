import asyncio
from fastapi import WebSocket


class AudioStreamManager:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.audio_queue = asyncio.Queue()
        self.is_streaming = False

    async def audio_generator(self):
        while self.is_streaming:
            try:
                chunk = await asyncio.wait_for(self.audio_queue.get(), timeout=5.0)
                yield chunk
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Error in audio generator: {e}")
                break

    async def add_audio_chunk(self, chunk: bytes):
        await self.audio_queue.put(chunk)

    async def stop_streaming(self):
        self.is_streaming = False