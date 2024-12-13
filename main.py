import asyncio
import sys
import os
import traceback
import pyaudio
from google import genai

# Audio parameters
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 512

MODEL = "models/gemini-2.0-flash-exp"

client = genai.Client(
    http_options={'api_version': 'v1alpha'})

speech_config = genai.types.SpeechConfig(
    voice_config = genai.types.VoiceConfig(
        prebuilt_voice_config = genai.types.PrebuiltVoiceConfig(voice_name="Aoede") # Puck, Charon, Kore, Fenrir, Aoede
    )
)

CONFIG = {
    "generation_config": {
        "response_modalities": ["AUDIO"],
    },
    "speech_config": speech_config,
}


class AudioLoop:
    def __init__(self):
        self.audio_in_queue = asyncio.Queue()
        self.audio_out_queue = asyncio.Queue()
        self.session = None
        self.is_playing = asyncio.Event()
        self.mic_stream = None
        self.pya = pyaudio.PyAudio()  # Create PyAudio instance once
        
        # if file exists, read the message from the file
        if os.path.exists('message.txt'):
            messages = []
            with open('message.txt', 'r') as file:
                message_text = file.read()
                message_text = message_text.strip()
                messages.append(message_text)
            self.messages = messages
        
    async def send_text(self):
        await asyncio.sleep(0.5)
        # First process all messages from the list
        if self.messages:
            while self.messages:
                line = self.messages.pop(0)
                await self.session.send(line or ".", end_of_turn=True)
                await asyncio.sleep(0.1)
            
        # Then switch to interactive console input
        while True:
            text = await asyncio.to_thread(input, "message > ")
            if text.lower() == "q":
                break
            await self.session.send(text or ".", end_of_turn=True)
        
    def get_audio_technica_device(self):
        # Look specifically for the Audio Technica device
        for i in range(self.pya.get_device_count()):
            try:
                device_info = self.pya.get_device_info_by_index(i)
                if "ATR4697-USB" in device_info['name']: # Audio Technica ATR4697-USB found with `cat /proc/asound/cards` & 'arecord -l'
                    print(f"Found Audio Technica device: {device_info['name']}")
                    return device_info
            except Exception as e:
                continue
        return None

    async def listen_audio(self):
        # Get the Audio Technica device specifically
        device_info = await asyncio.to_thread(self.get_audio_technica_device)
        if not device_info:
            raise RuntimeError("Audio Technica device not found")
        
        print(f"Opening microphone with settings:")
        print(f"Device index: {device_info['index']}")
        print(f"Sample rate: {SEND_SAMPLE_RATE}")
        print(f"Channels: {CHANNELS}")
        
        try:
            self.mic_stream = await asyncio.to_thread(
                self.pya.open,
                format=FORMAT,
                channels=CHANNELS,
                rate=SEND_SAMPLE_RATE,
                input=True,
                input_device_index=int(device_info['index']),
                frames_per_buffer=CHUNK_SIZE,
            )
            
            while True:
                if not self.is_playing.is_set():
                    try:
                        data = await asyncio.to_thread(
                            self.mic_stream.read, 
                            CHUNK_SIZE, 
                            exception_on_overflow=False
                        )
                        await self.audio_out_queue.put(data)
                    except OSError as e:
                        print(f"Microphone error: {e}")
                        # Attempt to reopen the stream
                        self.mic_stream = await asyncio.to_thread(
                            self.pya.open,
                            format=FORMAT,
                            channels=CHANNELS,
                            rate=SEND_SAMPLE_RATE,
                            input=True,
                            input_device_index=int(device_info['index']),
                            frames_per_buffer=CHUNK_SIZE,
                        )
                await asyncio.sleep(0.01)
                        
        except Exception as e:
            print(f"Fatal microphone error: {e}")
            raise

    async def send_audio(self):
        while True:
            chunk = await self.audio_out_queue.get()
            await self.session.send({"data": chunk, "mime_type": "audio/pcm"})

    async def receive_audio(self):
        while True:
            async for response in self.session.receive():
                server_content = response.server_content
                if server_content is not None:
                    model_turn = server_content.model_turn
                    if model_turn is not None:
                        parts = model_turn.parts

                        for part in parts:
                            if part.text is not None:
                                print(part.text, end="")
                            elif part.inline_data is not None:
                                self.is_playing.set()  # Set flag before playing
                                await self.audio_in_queue.put(part.inline_data.data)

                    server_content.model_turn = None
                    turn_complete = server_content.turn_complete
                    if turn_complete:
                        print("Turn complete")
                        # Clear the audio queue
                        while not self.audio_in_queue.empty():
                            self.audio_in_queue.get_nowait()
                        await asyncio.sleep(0.1)  # Small delay before clearing flag
                        self.is_playing.clear()

    async def play_audio(self):
        speaker_stream = await asyncio.to_thread(
            self.pya.open, 
            format=FORMAT, 
            channels=CHANNELS, 
            rate=RECEIVE_SAMPLE_RATE, 
            output=True
        )
        
        try:
            while True:
                bytestream = await self.audio_in_queue.get()
                await asyncio.to_thread(speaker_stream.write, bytestream)
                if self.audio_in_queue.empty():
                    await asyncio.sleep(0.1)  # Small delay before clearing flag
                    self.is_playing.clear()
        finally:
            speaker_stream.stop_stream()
            speaker_stream.close()

    async def run(self):
        async with (
            client.aio.live.connect(model=MODEL, config=CONFIG) as session,
            asyncio.TaskGroup() as tg,
        ):
            self.session = session

            send_text_task = tg.create_task(self.send_text())

            def cleanup(task):
                if self.mic_stream:
                    self.mic_stream.stop_stream()
                    self.mic_stream.close()
                self.pya.terminate()
                for t in tg._tasks:
                    t.cancel()

            send_text_task.add_done_callback(cleanup)

            tg.create_task(self.listen_audio())
            tg.create_task(self.send_audio())
            tg.create_task(self.receive_audio())
            tg.create_task(self.play_audio())

            def check_error(task):
                if task.cancelled():
                    return
                if task.exception() is not None:
                    e = task.exception()
                    traceback.print_exception(None, e, e.__traceback__)
                    sys.exit(1)

            for task in tg._tasks:
                task.add_done_callback(check_error)
                
    def print_device_info(self):
        device_info = self.get_audio_technica_device()
        if device_info:
            print("\nAudio Technica Device Information:")
            print(f"Name: {device_info['name']}")
            print(f"Index: {device_info['index']}")
            print(f"Default Sample Rate: {device_info['defaultSampleRate']}")
            print(f"Max Input Channels: {device_info['maxInputChannels']}")
            print(f"Max Output Channels: {device_info['maxOutputChannels']}")

if __name__ == "__main__":
    main = AudioLoop()
    main.print_device_info()
    asyncio.run(main.run())