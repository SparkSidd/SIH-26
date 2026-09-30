#!/bin/bash
WIN_ID=$(DISPLAY=:0 xdotool search --onlyvisible --class Webots | head -n 1)
DISPLAY=:0 import -window "$WIN_ID" /tmp/snap.png
cp /tmp/snap.png simulation/webots/webots_live_moving.png
