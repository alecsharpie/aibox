echo 'pcm.!default {
    type asym
    playback.pcm {
        type plug
        slave.pcm "hw:3,0"
    }
    capture.pcm {
        type plug
        slave.pcm "hw:3,0"
    }
}

ctl.!default {
    type hw
    card 3
}' > ~/.asoundrc

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

ctl.!default {
    type hw
    card 2  # bcm2835 Headphones
}' > /etc/asound.conf