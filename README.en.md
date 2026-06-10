# SygurDot

🌍 Languages: [English](README.en.md) | [Español](README.md)

![Desktop Showcase](preview/showcase.png)

A casual and optimized BSPWM setup for Debian. Designed for fresh installs: You just gotta run the `install.sh` and enjoy (in theory).

## Installation

### 1. Clone the repository
```bash
git clone https://github.com/sygurd24/SygurDot.git ~/dotfiles
```

### 2. Run Installer
```bash
cd ~/dotfiles
chmod +x install.sh
./install.sh
```

## Disclaimer

I'm not a Pro at this stuff. In fact, this is my first "ricing" on Linux. I did 95% of the code and configuration with the help of Artificial Intelligence. Speaking in creative terms, I am the 100% creator of the aesthetics and structure, but obviously, this setup wouldn't be possible without the AI doing the heavy lifting. I literally used Windows my whole life and one day I just decided to switch to Linux... but doing it right, ricing my entire environment from scratch, and honestly I couldn't be more pleased with the result. This whole thing even encouraged me to create a YouTube channel... who knows how long that'll last.

If you find any bugs, please let me know! I am completely open to future commits, PRs, issues, and collaborating here on GitHub.

## Why BSPWM?

Basically, because it was the first window manager I found out about. I paired it with `sxhkd` for handling all keyboard shortcuts, and `picom` for the visual effects. I also chose it because it is one of the most famous window managers out there and I wanted something highly stable to build upon.

## Requirements

This environment is heavily focused on users starting from a "net install" or a super basic installation. By simply executing `install.sh`, the script will take care of downloading everything the environment needs. You don't have to worry about manually installing anything beforehand (in theory). You just need the base OS, clone the repository, and run the installer.

Other essential requirements:
- Willingness to learn and not give up easily (the first week of configuring you'll need a lot of this).
- A good cup of coffee (I don't drink coffee, but if you do, prepare a few).
- Great background music (very important).
- An AI assistant (this is key).

## Preview

![Clean](preview/sinnada.png?v=2)
**Clean**, without any opened app. Only polybar is visible.

![Rofi](preview/rofi.png)
**Rofi**, for app launching - (super + space).

![Multiscreen](preview/multiscreen.png)
**Multiwindows** a view of the bspwm mosaics.  

![Lock Screen](preview/bloqueo.png)
**Lock Screen**, custom design for when you lock your session (i3lock-color).

![Other Wallpapers](preview/otrosfondos.png)
**Other Wallpapers**, showcase of the variety of included wallpapers.

## Main Components & Explanations

- **Window Manager (`bspwm`)**: The core tiling window manager handling your windows.
- **Shortcut Daemon (`sxhkd`)**: Handles all the keybindings efficiently (bspwm doesn't handle them directly).
- **Status Bar (`polybar`)**: Dynamic modules showing workspaces, time, network, etc.
- **Terminal (`kitty`)**: GPU-accelerated terminal paired with `zsh` + `powerlevel10k` + auto-suggestion and highlighting plugins.
- **Launcher (`rofi`)**: Configured for instant response and application launching.
- **Compositor (`picom`)**: Handles window transparency, animations, and blur.
- **Wallpaper Handler (`feh`)**: Manages the desktop background.
- **Screenshot Tool (`flameshot`)**: A powerful and interactive GUI screenshot tool.

## Inspect and Edit The Configuration Files

Once installed, you'll probably want to tweak the environment to match your workflow. Everything is modular and well-commented. Here is where you should look:

### `~/.config/bspwm/bspwmrc`
This is the "brain" of the window manager. It contains autostart applications, window gaps, borders, and **Window Rules**. 
For example, if you want a specific application to always open on a specific desktop or in floating mode, you use `bspc rule`. My current rules look something like this:
```bash
bspc rule -a Gimp desktop='^8' state=floating follow=on
bspc rule -a Chromium desktop='^2' state=tiled
bspc rule -a Pavucontrol state=floating center=true
```
*Tip: You can find an application's class name by running `xprop` in the terminal and clicking on the target window.*

### `~/.config/sxhkd/sxhkdrc`
This is the "muscle" of the environment. `bspwm` doesn't handle keyboard shortcuts by itself; `sxhkd` does it.
Here you will find all the keybindings. If you want to change the shortcut for closing a window or opening the browser, this is the place.
It also handles media keys (volume and brightness). If my volume or brightness scripts don't work on your specific hardware, you can easily replace the commands under the multimedia keys section.

### `~/.config/polybar/config.ini` (Status Bar)
If you notice that your battery or network modules are not showing up properly on your panel, it's because Linux assigns different hardware IDs to every computer.
- **Network Interface**: Find yours by running `ip a` (e.g., `wlan0` or `wlp2s0`), and update the variable in the Polybar config.
- **Battery ID**: Find yours by running `ls /sys/class/power_supply/` (e.g., `BAT0` or `BAT1`), and update it as well.

## Useful Shortcuts (General)

| Shortcut | Action |
|---|---|
| `Super + Space` | Open Launcher (Rofi) |
| `Super + Return` | Open Terminal (Kitty) |
| `Super + E` | File Explorer (Thunar) |
| `Super + F` | Web Browser (Firefox) |
| `Super + V` | Clipboard History (Greenclip) |
| `Super + Shift + S` | Selected Screenshot |
| `Print` / `Super + Shift + F` | Flameshot (Full GUI) |
| `Super + Escape` | Reload Shortcuts (sxhkd) |
| `Super + Alt + R` | Restart bspwm |
| `Super + BackSpace` | Lock Screen (Custom) |

## Menus & Control Shortcuts

| Shortcut | Action |
|---|---|
| `Super + Shift + D` | Date & Time Menu |
| `Super + Shift + N` | Wi-Fi Networks Menu |
| `Super + Shift + B` | Bluetooth Menu |
| `Super + Shift + M` | Microphone Menu (Active Apps) |
| `Super + Shift + P` | Power Profile / Battery Menu |
| `Super + Shift + BackSpace` | Power Menu (Logout/Reboot/Shutdown) |
| `Super + Alt + Space` | Configuration (Language) |
| `Alt + Space` | Play/Pause Media (Browser) |
| `Alt + {Left, Right}` | Previous / Next Track |

## bspwm Shortcuts (Navigation & Layout)

| Shortcut | Action |
|---|---|
| `Super + Arrows / hjkl` | Change Focus (West, South, North, East) |
| `Super + M` | Toggle between Tiled and Monocle Layout |
| `Super + Alt + S` | Toggle Fullscreen |
| `Super + Alt + O` | Toggle Transparency (85% / 100%) |
| `Super + Alt + Shift + Arrows` | Resize Window (Smart Resize) |
| `Super + {1-9, 0}` | Switch to Desktop |
| `Super + Shift + {1-9, 0}` | Move Window to Desktop |
| `Super + {F1-F12}` | Switch to Hidden Desktop |
| `Super + Shift + {F1-F12}` | Move Window to Hidden Desktop |
| `Super + W` | Close Focused Window |
| `Super + Shift + W` | Kill Window |

## Special Features (Custom Scripts)

- **Bluetooth Privacy Guard**: Automatically pauses all audio when a Bluetooth device is disconnected.
- **Cava Dynamic Input**: Synchronizes Cava input with the default audio output.
- **Force Time Sync**: Synchronizes system time on startup.
- **Optimized Responsiveness**: Increased keyboard repeat rate and instant shortcuts.


## Utility Scripts
These tools are located in the `scripts/` directory and can be run manually:
- `scripts/setup_hibernate.sh`: Configure swap and hibernation settings.
- `scripts/setup_lightdm.sh`: Configure the login screen theme and layout.

## Errors
Trying to make the `install.sh` take care of installing and configuring everything automatically, there was one specific thing that got really complicated for me... the graphics drivers. I know that at least for the computer I am currently using this environment on (HPVICTUS15) it gave me some errors at the beginning but I managed to fix it for this specific computer... it might give you problems, or maybe it won't... anyway, I have a file [Error log](TROUBLESHOOTING.md) where I properly documented this error, and other major errors I had while configuring all this. There you have it in case you need it.

For now, that's all.
