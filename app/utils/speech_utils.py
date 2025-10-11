from app.voice_manager.audio_stream_manager import AudioStreamManager
from google.cloud import speech
from google.cloud import texttospeech

speech_client = speech.SpeechClient()
tts_client = texttospeech.TextToSpeechClient()

async def speech_to_text_stream(audio_manager: AudioStreamManager):
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
        yield speech.StreamingRecognizeRequest(streaming_config=streaming_config)
        async for chunk in audio_manager.audio_generator():
            yield speech.StreamingRecognizeRequest(audio_content=chunk)

    responses = speech_client.streaming_recognize(
        config=streaming_config,
        requests=request_generator()
    )

    return responses

async def text_to_speech(text: str):
    syntesis_input = texttospeech.SynthesisInput(text=text)

    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
    )

    audio_config = texttospeech.AudioConfig(
        audio_config=texttospeech.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000
    )

    response = tts_client.synthesize_speech(
        input=syntesis_input,
        voice=voice,
        audio_config=audio_config
    )

    return response.audio_content