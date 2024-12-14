import pyaudio
import time

p = pyaudio.PyAudio()

# List all audio devices
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    print(f"\nDevice {i}:")
    print(f"  Name: {info['name']}")
    print(f"  Max Input Channels: {info['maxInputChannels']}")
    print(f"  Max Output Channels: {info['maxOutputChannels']}")
    print(f"  Default Sample Rate: {info['defaultSampleRate']}")

# Try to open the ATR4697-USB microphone
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if "ATR4697-USB" in info['name']:
        try:
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=44100,
                input=True,
                input_device_index=i,
                frames_per_buffer=1024
            )
            print("\nSuccessfully opened microphone stream")
            stream.close()
            break
        except Exception as e:
            print(f"\nFailed to open microphone: {e}")

p.terminate()