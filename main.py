import asyncio
import sys
import os
import traceback
import pyaudio
from google import genai

# Audio parameters
FORMAT = pyaudio.paInt16
CHANNELS = 1 # Mono
INPUT_RATE = 44100  # Native rate for ATR4697
RECEIVE_SAMPLE_RATE = 44100 # 24000  # Rate for API
CHUNK_SIZE = 1024  # Smaller chunk size CHUNK_SIZE = 512

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
            
    async def test_audio_device(self):
        device_info = self.get_audio_technica_device()
        if not device_info:
            print("Device not found!")
            return
            
        try:
            # Open input stream
            input_stream = self.pya.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=INPUT_RATE,
                input=True,
                input_device_index=int(device_info['index']),
                frames_per_buffer=CHUNK_SIZE
            )
            
            # Open output stream
            output_stream = self.pya.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=INPUT_RATE,
                output=True,
                output_device_index=int(device_info['index']),
                frames_per_buffer=CHUNK_SIZE
            )
            
            print("Recording for 5 seconds...")
            frames = []
            for _ in range(0, int(INPUT_RATE / CHUNK_SIZE * 5)):
                data = input_stream.read(CHUNK_SIZE, exception_on_overflow=False)
                frames.append(data)
            
            print("Playing back...")
            for frame in frames:
                output_stream.write(frame)
                
            input_stream.stop_stream()
            input_stream.close()
            output_stream.stop_stream()
            output_stream.close()
            
        except Exception as e:
            print(f"Test failed: {e}")
            traceback.print_exc()
        
    def get_audio_technica_device(self):
        for i in range(self.pya.get_device_count()):
            try:
                info = self.pya.get_device_info_by_index(i)
                if "ATR4697-USB" in info.get('name', ''):
                    print(f"\nFound ATR4697-USB device:")
                    print(f"Name: {info['name']}")
                    print(f"Index: {info['index']}")
                    print(f"Sample Rate: {info['defaultSampleRate']}")
                    print(f"Max Input Channels: {info['maxInputChannels']}")
                    print(f"Max Output Channels: {info['maxOutputChannels']}")
                    return info
            except Exception as e:
                print(f"Error getting device info: {e}")
                continue
        return None

    # Remove or modify get_playback_device to use ATR4697-USB instead of bcm2835 Headphones
    def get_playback_device(self):
        return self.get_audio_technica_device()

    
    async def listen_audio(self):
        device_info = self.get_audio_technica_device()
        if not device_info:
            raise RuntimeError("Audio Technica device not found")
        
        try:
            print(f"Opening microphone stream with settings:")
            print(f"Format: {FORMAT}")
            print(f"Channels: {CHANNELS}")
            print(f"Rate: {INPUT_RATE}")
            print(f"Device Index: {device_info['index']}")
            
            self.mic_stream = await asyncio.to_thread(
                self.pya.open,
                format=FORMAT,
                channels=CHANNELS,
                rate=INPUT_RATE,
                input=True,
                input_device_index=int(device_info['index']),
                frames_per_buffer=CHUNK_SIZE,
                stream_callback=None
            )
            
            print("Microphone stream opened successfully")
            
            while True:
                if not self.is_playing.is_set():
                    try:
                        data = await asyncio.to_thread(
                            self.mic_stream.read, 
                            CHUNK_SIZE,
                            exception_on_overflow=False
                        )
                        print("Read audio chunk of size:", len(data))
                        await self.audio_out_queue.put(data)
                    except OSError as e:
                        print(f"Microphone error: {e}")
                        await asyncio.sleep(1)
                await asyncio.sleep(0.01)
                        
        except Exception as e:
            print(f"Fatal microphone error: {e}")
            traceback.print_exc()
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
        device_info = self.get_audio_technica_device()
        if not device_info:
            raise RuntimeError("Audio Technica device not found")

        try:
            print(f"Opening speaker stream with settings:")
            print(f"Format: {FORMAT}")
            print(f"Channels: {CHANNELS}")
            print(f"Rate: {RECEIVE_SAMPLE_RATE}")
            print(f"Device Index: {device_info['index']}")
            
            speaker_stream = await asyncio.to_thread(
                self.pya.open, 
                format=FORMAT, 
                channels=CHANNELS, 
                rate=RECEIVE_SAMPLE_RATE,
                output=True,
                output_device_index=int(device_info['index']),
                frames_per_buffer=CHUNK_SIZE,
                stream_callback=None
            )
            
            print("Speaker stream opened successfully")
            
            while True:
                try:
                    bytestream = await self.audio_in_queue.get()
                    print("Playing audio chunk of size:", len(bytestream))
                    await asyncio.to_thread(speaker_stream.write, bytestream)
                    if self.audio_in_queue.empty():
                        await asyncio.sleep(0.1)
                        self.is_playing.clear()
                except Exception as e:
                    print(f"Error playing audio: {e}")
                    traceback.print_exc()
                    await asyncio.sleep(1)
        except Exception as e:
            print(f"Failed to open output stream: {e}")
            traceback.print_exc()

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
    
    # Run test first
    print("\nTesting audio device...")
    asyncio.run(main.test_audio_device())
    
    # If test passes, run main application
    print("\nStarting main application...")
    asyncio.run(main.run())