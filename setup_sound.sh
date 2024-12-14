# Create user-specific config
echo 'pcm.!default {
    type asym
    playback.pcm {
        type plug
        slave.pcm "hw:2,0"  # bcm2835 Headphones
    }
    capture.pcm {
        type plug
        slave.pcm "hw:3,0"  # ATR4697-USB
    }
}

defaults.pcm.rate_converter "samplerate_best"

pcm.microphone {
    type plug
    slave {
        pcm "hw:3,0"  # ATR4697-USB
        format S16_LE
        rate 44100
        channels 1
    }
}

pcm.speaker {
    type plug
    slave {
        pcm "hw:2,0"  # bcm2835 Headphones
        format S16_LE
        rate 48000
        channels 2
    }
}

ctl.!default {
    type hw
    card 2  # bcm2835 Headphones
}' > ~/.asoundrc

# Create system-wide config
echo 'pcm.!default {
    type asym
    playback.pcm {
        type plug
        slave.pcm "hw:2,0"  # bcm2835 Headphones
    }
    capture.pcm {
        type plug
        slave.pcm "hw:3,0"  # ATR4697-USB
    }
}

defaults.pcm.rate_converter "samplerate_best"

pcm.microphone {
    type plug
    slave {
        pcm "hw:3,0"  # ATR4697-USB
        format S16_LE
        rate 44100
        channels 1
    }
}

pcm.speaker {
    type plug
    slave {
        pcm "hw:2,0"  # bcm2835 Headphones
        format S16_LE
        rate 48000
        channels 2
    }
}

ctl.!default {
    type hw
    card 2  # bcm2835 Headphones
}' > /etc/asound.conf