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
RECEIVE_SAMPLE_RATE = 24000  # Rate for API
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
        
    def get_audio_technica_device(self):
        for i in range(self.pya.get_device_count()):
            try:
                info = self.pya.get_device_info_by_index(i)
                if "ATR4697-USB" in info.get('name', ''):
                    print(f"\nFound microphone device:")
                    print(f"Name: {info['name']}")
                    print(f"Index: {info['index']}")
                    print(f"Sample Rate: {info['defaultSampleRate']}")
                    print(f"Max Input Channels: {info['maxInputChannels']}")
                    return info
            except Exception as e:
                continue
        return None

    def get_playback_device(self):
        # Try to get the headphone output device
        for i in range(self.pya.get_device_count()):
            try:
                info = self.pya.get_device_info_by_index(i)
                if "bcm2835 Headphones" in info.get('name', ''):
                    print(f"\nFound speaker device:")
                    print(f"Name: {info['name']}")
                    print(f"Index: {info['index']}")
                    print(f"Sample Rate: {info['defaultSampleRate']}")
                    print(f"Max Output Channels: {info['maxOutputChannels']}")
                    return info
            except Exception as e:
                continue
        return None

    async def listen_audio(self):
        device_info = self.get_audio_technica_device()
        if not device_info:
            raise RuntimeError("Audio Technica microphone not found")
        
        try:
            self.mic_stream = await asyncio.to_thread(
                self.pya.open,
                format=FORMAT,
                channels=1,  # Force mono
                rate=44100,  # Use native rate
                input=True,
                input_device_index=int(device_info['index']),
                frames_per_buffer=CHUNK_SIZE,
                stream_callback=None  # Ensure blocking mode
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
                        await self.audio_out_queue.put(data)
                    except OSError as e:
                        print(f"Microphone error: {e}")
                        await asyncio.sleep(1)
                await asyncio.sleep(0.01)
                        
        except Exception as e:
            print(f"Fatal microphone error: {e}")
            raise

    async def play_audio(self):
        device_info = self.get_playback_device()
        if not device_info:
            print("Warning: Using default output device")
            device_index = None
        else:
            device_index = int(device_info['index'])

        try:
            speaker_stream = await asyncio.to_thread(
                self.pya.open, 
                format=FORMAT, 
                channels=CHANNELS, 
                rate=RECEIVE_SAMPLE_RATE,
                output=True,
                output_device_index=device_index,
                frames_per_buffer=CHUNK_SIZE
            )
            
            print("Speaker stream opened successfully")
            
            while True:
                try:
                    bytestream = await self.audio_in_queue.get()
                    await asyncio.to_thread(speaker_stream.write, bytestream)
                    if self.audio_in_queue.empty():
                        await asyncio.sleep(0.1)
                        self.is_playing.clear()
                except Exception as e:
                    print(f"Error playing audio: {e}")
                    await asyncio.sleep(1)
        except Exception as e:
            print(f"Failed to open output stream: {e}")
                
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