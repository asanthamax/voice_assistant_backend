import asyncio
from fastapi import WebSocket
import logging


class AudioStreamManager:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.audio_queue = asyncio.Queue()
        self.is_streaming = False
        self.logger = logging.getLogger(__name__)

    async def audio_generator(self):
        while self.is_streaming:
            try:
                chunk = await asyncio.wait_for(self.audio_queue.get(), timeout=5.0)
                self.logger.debug("Yielding audio chunk from generator")
                yield chunk
            except asyncio.TimeoutError:
                self.logger.debug("Audio generator timed out, but continuing.")
                continue
            except Exception as e:
                self.logger.error(f"Error in audio generator: {e}")
                break

    async def add_audio_chunk(self, chunk: bytes):
        await self.audio_queue.put(chunk)

    async def stop_streaming(self):
        self.is_streaming = False
        await self.audio_queue.put(None) # Sentinel value to unblock the generator