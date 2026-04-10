#!/bin/bash
while true; do
    sleep 2
    polybar-msg action temperature hook 0 >/dev/null 2>&1
done
