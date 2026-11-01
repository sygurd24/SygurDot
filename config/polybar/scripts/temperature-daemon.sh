#!/bin/bash
while true; do
    sleep 2
    timeout 1 polybar-msg action temperature hook 0 >/dev/null 2>&1
done
