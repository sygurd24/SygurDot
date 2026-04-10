#!/usr/bin/env python3
import dbus
import sys

# Bluetooth Status for Polybar (DBus Version)
# Checks if ANY Bluetooth device is connected (Mouse, Keyboard, Audio).
# Colors:
# - Off: Gray
# - On (Disconnected): Default
# - Connected: Bright Cyan (#00E6CC)

def get_bluetooth_status():
    bus = dbus.SystemBus()
    
    # Get Object Manager to find all objects
    try:
        manager = dbus.Interface(bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager")
        objects = manager.GetManagedObjects()
    except dbus.exceptions.DBusException:
        # Bluez not running usually means powered off or no service
        print("%{F#707880}%{F-}")
        return

    # Check Power State (Adapter)
    powered = False
    any_connected = False
    
    for path, interfaces in objects.items():
        if "org.bluez.Adapter1" in interfaces:
            adapter = interfaces["org.bluez.Adapter1"]
            if adapter.get("Powered", False):
                powered = True
                
        if "org.bluez.Device1" in interfaces:
            device = interfaces["org.bluez.Device1"]
            if device.get("Connected", False):
                any_connected = True

    if not powered:
        # Gray
        print("%{F#707880}%{F-}")
    elif any_connected:
        # Bright Cyan-Green (More distinct from standard #00BCD4)
        print("%{F#00FFB3}%{F-}")
    else:
        # Default
        print("")

if __name__ == "__main__":
    try:
        get_bluetooth_status()
    except Exception:
        # Fallback to default if DBus fails completely
        print("")
