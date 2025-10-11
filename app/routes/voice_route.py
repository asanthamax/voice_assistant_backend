import asyncio
import base64
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.agent_builder.agent import graph

from app.utils.speech_utils import text_to_speech
from app.voice_manager.audio_stream_manager import AudioStreamManager


logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/ws/voice")
async def voice_streamer(websocket: WebSocket):
    await websocket.accept()
    audio_manager = AudioStreamManager(websocket)

    try:
        transcript_buffer = []
        while True:
            message = await websocket.receive()

            if "bytes" in message:
                audio_data = message["bytes"]
                await audio_manager.add_audio_chunk(audio_data)
            elif "text" in message:
                data = json.loads(message["text"])
                if data.get("event_type") == "start_listening":
                    await websocket.send_json({
                        "event_type": "listening",
                        "message": "Listening started"
                    })
                elif data.get("event_type") == "stop_listening":
                    if transcript_buffer:
                        full_transcript = " ".join(transcript_buffer)
                        await websocket.send_json({
                            "event_type": "final_transcript",
                            "message": full_transcript
                        })

                        agent_response = graph.invoke(
                            {
                                "messages": [{"role": "user", "content": full_transcript}]
                            }
                        )

                        response_text = agent_response['agent_node']['messages'][-1].content

                        await websocket.send_json({
                            "event_type": "agent_response",
                            "text": response_text
                        })

                        audio_response = await text_to_speech(response_text)
                        audio_base64 = base64.b64encode(audio_response).decode()
                        await websocket.send_json({
                            "event_type": "audio_response",
                            "audio_data": audio_base64
                        })

                        transcript_buffer.clear()
                    await audio_manager.stop_streaming()
                elif data.get("event_type") == "transcript":
                    if data.get("is_final"):
                        transcript_buffer.append(data.get("text", ""))

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in voice streamer: {e}")
        await websocket.close(code=1011, reason="Internal server error")