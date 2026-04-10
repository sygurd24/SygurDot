#!/usr/bin/env python3
import subprocess
import os
import time
import re

# Cava Dynamic Input Switcher
# Monitors PulseAudio events. When default sink changes, updates Cava config to listen to that sink's monitor.
# Prevents fallback to Microphone.

CONFIG_PATH = os.path.expanduser("~/.config/cava/config")

def get_default_sink_monitor():
    try:
        # Get default sink name (works for both PulseAudio and PipeWire via pactl)
        sink_name = subprocess.check_output(["pactl", "get-default-sink"], text=True, stderr=subprocess.DEVNULL).strip()
        
        if not sink_name:
            # Fallback for older PulseAudio
            info = subprocess.check_output(["pactl", "info"], text=True)
            for line in info.splitlines():
                if "Default Sink:" in line:
                    sink_name = line.split(":")[1].strip()
                    break

        if not sink_name: return None

        # Standard PulseAudio/PipeWire monitor naming convention
        monitor_name = f"{sink_name}.monitor"
        
        # Verify the monitor exists as a source
        sources = subprocess.check_output(["pactl", "list", "short", "sources"], text=True)
        if monitor_name in sources:
            return monitor_name
        
        # Some PipeWire setups or older PA might use a different name for monitor
        # Let's find a source that matches the sink name and is a monitor
        for line in sources.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                src = parts[1]
                if sink_name in src and ".monitor" in src:
                    return src
        
        return monitor_name # Fallback to convention
    except Exception as e:
        return None

def update_cava_config(monitor_name):
    if not monitor_name: return
    
    try:
        if not os.path.exists(CONFIG_PATH): return

        with open(CONFIG_PATH, 'r') as f:
            lines = f.readlines()
            
        new_lines = []
        changed = False
        source_found = False
        
        for line in lines:
            if line.strip().startswith("source ="):
                source_found = True
                current_source = line.split("=")[1].strip().strip("'").strip('"')
                if current_source != monitor_name:
                    new_lines.append(f"source = {monitor_name}\n")
                    changed = True
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        
        # If source line was missing, add it under [input]
        if not source_found:
            final_lines = []
            in_input = False
            for line in new_lines:
                final_lines.append(line)
                if line.strip() == "[input]":
                    in_input = True
                    final_lines.append(f"source = {monitor_name}\n")
                    changed = True
            new_lines = final_lines

        if changed:
            with open(CONFIG_PATH, 'w') as f:
                f.writelines(new_lines)
            # Reload Cava (it won't crash if it's not running)
            subprocess.run(["pkill", "-USR1", "cava"], stderr=subprocess.DEVNULL)
    except Exception as e:
        pass

def main():
    # Initial setup
    current_monitor = get_default_sink_monitor()
    if current_monitor:
        update_cava_config(current_monitor)
    
    # Listen loop
    try:
        with subprocess.Popen(
            ["pactl", "subscribe"],
            stdout=subprocess.PIPE,
            text=True,
            stderr=subprocess.DEVNULL
        ) as process:
            # We know stdout is a pipe because we requested it
            assert process.stdout is not None
            for line in process.stdout:
                # Event 'change' on 'server' or 'sink'
                if "sink" in line or "server" in line:
                    # Wait a split second for PA to stabilize
                    time.sleep(0.5)
                    new_monitor = get_default_sink_monitor()
                    if new_monitor and new_monitor != current_monitor:
                        update_cava_config(new_monitor)
                        current_monitor = new_monitor

    except Exception:
        pass


if __name__ == "__main__":
    main()

