#!/bin/bash

# Copy all py files from current directory to smolberry
scp *.py artis@smolberry:~/robot/.
scp templates/*.html artis@smolberry:~/robot/templates/.
