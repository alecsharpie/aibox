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