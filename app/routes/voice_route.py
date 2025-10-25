import asyncio
import base64
import json
import logging
import os
import tempfile
import time
from elevenlabs import TextToSpeechConvertRequestOutputFormat
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import ffmpeg
from langchain.schema import HumanMessage
import ulid
import websockets
import whisper
from app.agent_builder.agent import graph
from elevenlabs.client import ElevenLabs
import soundfile as sf
import numpy as np

from app.utils.speech_utils import speech_to_text_stream, text_to_speech
from app.voice_manager.audio_stream_manager import AudioStreamManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s :: %(levelname)s :: %(name)s :: %(message)s'
)
logger = logging.getLogger(__name__)
router = APIRouter()
model = whisper.load_model("turbo")
ELEVEN_API_KEY = os.environ['ELEVENLABS_API_KEY']
elevenlabs = ElevenLabs(api_key=ELEVEN_API_KEY)

MIN_BUFFER_SIZE = 16000 * 2 * 3 # 3 seconds of 16kHz, 16-bit, mono audio

# Define audio parameters for the incoming raw audio (assuming 16kHz, 16-bit, mono)
SAMPLE_RATE = 16000
SUBTYPE = 'PCM_16' # 16-bit PCM

@router.websocket("/ws/voice")
async def voice_streamer(websocket: WebSocket):
    await websocket.accept()
    audio_manager = AudioStreamManager(websocket)
    audio_manager.is_streaming = True
    chat_thread_id = None
    try:
        stt_task = None
        transcript_buffer = []
        audio_buffer = bytearray()
        while True:
            try:
                message = await websocket.receive()
                if "bytes" in message:
                    print('byte message recieved')
                    audio_data = message["bytes"]
                    with tempfile.NamedTemporaryFile(delete=True, suffix=".webm") as webm_file:
                        webm_path = webm_file.name
                        webm_file.write(audio_data)  
                        wav_path = webm_path.replace(".webm", ".wav")
                        ffmpeg.input(webm_path).output(wav_path, format="wav", acodec="pcm_s16le", ac=1, ar="16000").run(quiet=True)
                        with open(wav_path, "rb") as wav_file:
                            audio_data = wav_file.read()
                    await audio_manager.add_audio_chunk(audio_data)
                    audio_manager.is_streaming = True
                    stt_task = asyncio.create_task(speech_to_text_stream(audio_manager, transcript_buffer))
                    while not stt_task.done():
                        await asyncio.sleep(0.1)
                    await websocket.send_json({
                        "event_type": "audio_chunk_processed",
                        "text": "Audio chunk received and processed"
                    })

                elif "text" in message:
                    print('text message recieved')
                    data = json.loads(message["text"])
                    if data.get("event_type") == "start_listening":
                        await websocket.send_json({
                            "event_type": "listening",
                            "text": "Listening started"
                        })
                    elif data.get("event_type") == "existing_chat":
                        chat_thread_id = data.get("chatThreadId")
                        await websocket.send_json({
                            "event_type": "chat_thread_acknowledged",
                            "chatThreadId": chat_thread_id
                        })
                    elif data.get("event_type") == "stop_listening":
                        await audio_manager.stop_streaming()

                        # Process any remaining audio in the buffer before stopping
                        if transcript_buffer:
                            full_transcript = " ".join(filter(None, transcript_buffer))
                            await websocket.send_json({
                                "event_type": "final_transcript",
                                "text": full_transcript
                            })

                            if chat_thread_id is None:
                                chat_thread_id = ulid.new().str

                            agent_response = graph.invoke(
                                {
                                    "messages": [HumanMessage(content=full_transcript)]
                                },
                                config={"configurable": {"thread_id": chat_thread_id}}
                            )

                            response_text = agent_response['messages'][-1].content

                            await websocket.send_json({
                                "event_type": "agent_response",
                                "text": {"responseText": response_text, "chatThreadId": chat_thread_id}
                            })

                            audio = elevenlabs.text_to_speech.stream(
                                text=response_text,
                                voice_id="ZF6FPAbjXT4488VcRRnw",
                                model_id="eleven_multilingual_v2",
                                output_format="mp3_22050_32"
                            )

                            for chunk in audio:
                                if chunk:
                                    await websocket.send_json({
                                        "event_type": "audio_response",
                                        "audio_data": base64.b64encode(chunk).decode()
                                    })

                            await websocket.send_json({
                                "event_type": "final_audio_response",
                                "done": True
                            })


                            #audio_response = await text_to_speech(response_text)
                            #audio_base64 = base64.b64encode(audio_response).decode()
                            #await websocket.send_json({
                            #    "event_type": "audio_response",
                            #    "audio_data": audio_base64
                            #})

                            transcript_buffer.clear() # Clear buffer after full processing
            except Exception as e:
                logger.error(f"Error in voice streamer: {e}")
                await websocket.send_json({"event_type": "error", "reason": "Internal server error"})      

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in voice streamer: {e}")
        await websocket.send_json({"event_type": "error", "reason": "Internal server error"})