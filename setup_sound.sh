#!/bin/bash

# Create user-specific config
cat << 'EOF' > ~/.asoundrc
pcm.!default {
    type plug
    slave.pcm "dmix"
}

pcm.mic {
    type plug
    slave {
        pcm "hw:3,0"  # ATR4697-USB
        format S16_LE
        rate 44100
        channels 1
    }
}

ctl.mic {
    type hw
    card 3
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

ctl.speaker {
    type hw
    card 2
}
EOF

# Create system-wide config
sudo tee /etc/asound.conf << 'EOF'
defaults.pcm.rate_converter "samplerate_medium"

pcm.!default {
    type plug
    slave.pcm "dmix"
}

pcm.mic {
    type plug
    slave {
        pcm "hw:3,0"  # ATR4697-USB
        format S16_LE
        rate 44100
        channels 1
    }
}

ctl.mic {
    type hw
    card 3
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

ctl.speaker {
    type hw
    card 2
}
EOF

# Set permissions
sudo chmod 666 /dev/snd/*