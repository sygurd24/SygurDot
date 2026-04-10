#!/usr/bin/env python3
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
import subprocess
import os

# Bluetooth Privacy Guard
# Pauses all media (using playerctl) when any Bluetooth device disconnects.
# Prevents audio blasting from speakers.

def property_changed(interface, changed, invalidated, path):
    # Filter for Bluetooth Device Interface
    if interface != "org.bluez.Device1":
        return

    # Check if "Connected" property changed
    if "Connected" in changed:
        is_connected = changed["Connected"]
        
        if not is_connected:
            # Device Disconnected!
            print(f"Bluetooth device disconnected: {path}")
            print("Pausing all media...")
            
            # Execute playerctl pause -a
            # Ensure playerctl is installed
            try:
                subprocess.run(["playerctl", "pause", "-a"], check=False)
                subprocess.run(["notify-send", "Bluetooth Privacy", "Dispositivo desconectado. Audio pausado.", "-i", "audio-speakers"], check=False)
            except FileNotFoundError:
                print("Error: playerctl not found. Please install it.")

def main():
    # Setup DBus Loop
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    
    # Listen for Property Changes on Bluez
    bus.add_signal_receiver(
        property_changed,
        bus_name="org.bluez",
        dbus_interface="org.freedesktop.DBus.Properties",
        signal_name="PropertiesChanged",
        path_keyword="path"
    )
    
    print("Bluetooth Privacy Guard running...")
    print("Waiting for disconnection events...")
    
    # Run Main Loop
    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        print("Exiting...")

if __name__ == "__main__":
    main()
