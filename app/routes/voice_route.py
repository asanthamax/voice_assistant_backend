import asyncio
import base64
import json
import logging
import tempfile
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langchain.schema import HumanMessage
import ulid
import ffmpeg
from app.agent_builder.agent import graph

from app.utils.speech_utils import speech_to_text_stream, text_to_speech
from app.voice_manager.audio_stream_manager import AudioStreamManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s :: %(levelname)s :: %(name)s :: %(message)s'
)
logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/ws/voice")
async def voice_streamer(websocket: WebSocket):
    await websocket.accept()
    audio_manager = AudioStreamManager(websocket)
    audio_manager.is_streaming = True
    chat_thread_id = None
    try:
        stt_task = None
        transcript_buffer = []
        while True:
            message = await websocket.receive()
            if "bytes" in message:
                audio_data = message["bytes"]
                with tempfile.NamedTemporaryFile(delete=True, suffix=".webm") as webm_file:
                    webm_path = webm_file.name
                    webm_file.write(audio_data)  
                    wav_path = webm_path.replace(".webm", ".wav")
                    ffmpeg.input(webm_path).output(wav_path, format="wav", acodec="pcm_s16le", ac=1, ar="16000").run(quiet=True)
                    with open(wav_path, "rb") as wav_file:
                        audio_data = wav_file.read()
                await audio_manager.add_audio_chunk(audio_data)
                stt_task = asyncio.create_task(speech_to_text_stream(audio_manager, transcript_buffer))
                while not stt_task.done():
                    await asyncio.sleep(0.1)
                await websocket.send_json({
                    "event_type": "audio_recieved",
                    "text": "Audio chunk received and processed"
                })

            elif "text" in message:
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

                        audio_response = await text_to_speech(response_text)
                        audio_base64 = base64.b64encode(audio_response).decode()
                        await websocket.send_json({
                            "event_type": "audio_response",
                            "audio_data": audio_base64
                        })

                        transcript_buffer.clear()
                elif data.get("event_type") == "transcript":
                    if data.get("is_final"):
                        transcript_buffer.append(data.get("text", ""))

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in voice streamer: {e}")
        await websocket.close(code=1011, reason="Internal server error")