# deckfs

[![Tests](https://github.com/spinogrizz/deckfs/workflows/Tests/badge.svg)](https://github.com/spinogrizz/deckfs/actions)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Linux daemon for controlling Stream Deck devices without GUI through filesystem interface.

## Overview

deckfs provides a simple, filesystem-based interface for configuring and controlling Elgato Stream Deck devices on Linux. Instead of requiring a GUI application, it monitors a directory structure where each numbered folder corresponds to a Stream Deck button.

## Features

- **Filesystem-based configuration** - No GUI required
- **Hot reload** - Changes take effect immediately without restart
- **Multi-format support** - PNG, JPEG images and shell/Python/Node.js scripts
- **Symbolic link support** - Dynamic image switching
- **Automatic script detection** - Supports .sh, .py, .js action scripts
- **Live monitoring** - Real-time file system change detection

## Installation

### From PyPI (when available)
```bash
pip install deckfs
```

### From source
```bash
git clone https://github.com/spinogrizz/deckfs.git
cd deckfs
pip install .
```

## Quick Start

1. Initialize configuration structure:
```bash
deckfs setup
```

2. Add images and scripts to button folders:
```bash
# Button 1
cp my-icon.png ~/.local/streamdeck/01/image.png
echo '#!/bin/bash\necho "Button 1 pressed!"' > ~/.local/streamdeck/01/action.sh
chmod +x ~/.local/streamdeck/01/action.sh

# Button 2  
cp another-icon.jpg ~/.local/streamdeck/02/image.png
echo 'print("Button 2 pressed!")' > ~/.local/streamdeck/02/action.py
```

3. Start the daemon:
```bash
deckfs start
```

## Development


## Configuration Structure

```
~/.local/streamdeck/
├── 01/
│   ├── image.png    # Button image (PNG/JPEG)
│   └── action.sh    # Action script (optional)
├── 02/
│   ├── image.jpg
│   └── action.py
├── 03/
│   ├── image.png
│   └── action.js
└── ...
```

### Folder Naming
- Folders must be named with zero-padded numbers: `01`, `02`, `03`, etc.
- Each folder corresponds to a Stream Deck button position

### Images
- Supported formats: PNG, JPEG
- Filename must start with "image" (e.g., `image.png`, `image.jpg`)
- Images are automatically scaled to fit button size
- Symbolic links supported for dynamic switching

### Action Scripts
- Optional executable scripts triggered on button press
- Supported types:
  - `.sh` - Shell scripts (executed with bash)
  - `.py` - Python scripts (executed with python3)
  - `.js` - JavaScript scripts (executed with node)
- Must be named `action.{extension}`
- Must be executable for shell scripts

## CLI Usage

```bash
# Initialize configuration structure
deckfs setup

# Start daemon in foreground
deckfs start

# Start daemon in background
deckfs start --daemon

# Stop running daemon
deckfs stop

# Check daemon status
deckfs status

# Use custom config directory
deckfs start --config-dir /path/to/config

# Show version
deckfs --version
```

## Requirements

- Linux operating system
- Python 3.8+
- Connected Elgato Stream Deck device
- Appropriate udev rules for device access

### Device Permissions

You may need to set up udev rules for device access:

```bash
# Create udev rule file
sudo tee /etc/udev/rules.d/50-streamdeck.rules << EOF
SUBSYSTEM=="usb", ATTRS{idVendor}=="0fd9", TAG+="uaccess"
EOF

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

## Examples

See the `examples/` directory for comprehensive examples in different programming languages:

- **01_toggle_mute** (Bash) - Toggle system audio mute with visual feedback
- **02_launch_firefox** (Python) - Smart Firefox launcher with profile support  
- **03_next_track** (JavaScript) - Advanced media player control via D-Bus

Each example includes detailed setup instructions, documentation, and demonstrates different integration approaches.

### Quick Dynamic Image Switching
```bash
# Create images
cp status-online.png ~/.local/streamdeck/01/online.png
cp status-offline.png ~/.local/streamdeck/01/offline.png

# Switch between them using symlinks
ln -sf online.png ~/.local/streamdeck/01/image.png   # Shows online
ln -sf offline.png ~/.local/streamdeck/01/image.png  # Shows offline
```

## Troubleshooting

### Device Not Found
- Ensure Stream Deck is connected and powered
- Check udev rules are properly configured
- Verify user permissions for USB device access

### Images Not Updating
- Check file permissions and ownership
- Ensure filename starts with "image"
- Verify image format is PNG or JPEG

### Scripts Not Executing
- Verify script has executable permissions (`chmod +x`)
- Check script interpreter is installed (bash/python3/node)
- Review daemon output for error messages

## Development

### Project Structure
```
src/
├── cli.py              # Main CLI entry point
├── core/
│   └── daemon.py       # Daemon implementation
├── handlers/
│   └── file_handler.py # File system event handling
└── utils/
    ├── config.py       # Configuration constants
    └── device.py       # Stream Deck device management
```

### Dependencies
- `streamdeck` - Stream Deck SDK
- `Pillow` - Image processing
- `watchdog` - File system monitoring

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable  
5. Submit a pull request

## Support

- Report issues: https://github.com/spinogrizz/deckfs/issues
- Source code: https://github.com/spinogrizz/deckfs