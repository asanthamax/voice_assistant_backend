import asyncio
from typing import List
import pyaudio
import wave
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
import soundfile as sf
import numpy as np
import io
from app.voice_manager.audio_stream_manager import AudioStreamManager
from google.cloud import speech
from google.cloud import texttospeech


speech_client = speech.SpeechClient()
tts_client = texttospeech.TextToSpeechClient()


async def speech_to_text_stream(audio_manager: AudioStreamManager, transcript_buffer: List[str]):
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="en-US",
        enable_automatic_punctuation=True,
    )

    streaming_config = speech.StreamingRecognitionConfig(
        config=config, interim_results=True
    )

    async def request_generator():
        print("Starting request generator...")
        async for chunk in audio_manager.audio_generator():
            print("Recieved audio chunk")
            #chunk = await convert_webm_to_linear16(chunk)
            print("Converted audio chunk")
            if chunk is None:
                print("Chunk is None, skipping...")
                continue
            yield speech.StreamingRecognizeRequest(audio_content=chunk)
            audio_manager.is_streaming = False  # Stop the audio generator after streaming

    # Convert AsyncGenerator to sync Iterator
    def sync_generator() -> Iterator[speech.StreamingRecognizeRequest]:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            agen = request_generator()
            while True:
                try:
                    request = loop.run_until_complete(agen.__anext__())
                    yield request
                except StopAsyncIteration:
                    break
        finally:
            loop.close()

    responses = speech_client.streaming_recognize(streaming_config, sync_generator())
    print("streaming recieved: ", responses)

    # Iterate over the responses
    try:
        for response in responses:
            if not response.results:
                continue
            
            result = response.results[0]
            if not result.alternatives:
                continue
                
            transcript = result.alternatives[0].transcript
            
            if result.is_final:
                print(f"Final transcript: {transcript}")
                transcript_buffer.append(transcript)
            else:
                print(f"Interim transcript: {transcript}")
                
    except Exception as e:
        print(f"Error processing responses: {e}")
        return None

    return None

async def text_to_speech(text: str):
    syntesis_input = texttospeech.SynthesisInput(text=text)

    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
    )

    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000
    )

    response = tts_client.synthesize_speech(
        input=syntesis_input,
        voice=voice,
        audio_config=audio_config
    )

    return response.audio_content