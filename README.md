# Pen Relay

Use a phone or tablet as a wireless Windows pen-input surface. Pen Relay runs a small server on your PC, opens a full-screen drawing surface in the device browser, and converts its pointer input—including compatible stylus pressure and hover—into native Windows pen events.

It is designed for a phone and PC on the same trusted Wi-Fi network.

## Features

- Native Windows synthetic pen input, suitable for apps that support pen input.
- Pen pressure and hover forwarding when the mobile browser/device exposes them.
- Full-screen browser canvas to reduce accidental browser gestures.
- QR code and local address for quick phone connection.
- Adjustable phone-to-desktop drawing area, with optional aspect-ratio locking.
- Optional **Stylus only** mode to ignore touch events while retaining pen input.
- Persistent settings for the selected port, input area, aspect ratio, and filtering mode.

## Requirements

- Windows 10 version 1809 or later. The app uses the Windows Synthetic Pointer Input API.
- Python 3.9 or newer with Tkinter available (the standard Windows Python installer includes it).
- A phone/tablet and PC connected to the same network.
- A modern mobile browser with Pointer Events and Fullscreen API support.

## Quick start

From PowerShell in this folder:

```powershell
py -m pip install -r requirements.txt
py server.py
```

1. In the Pen Relay window, choose **Start server**.
2. On the phone, scan the displayed QR code or open the shown `http://…` address.
3. Tap **Set fullscreen and start drawing** in the phone browser.
4. Use the phone screen as the input surface. Leave full-screen mode to stop forwarding input.

The phone page shows its connection state before it enters full-screen mode. Keep the Pen Relay window open while using the surface.

## Configure the drawing area

By default, the complete phone surface maps to the complete primary display.

Choose **Set phone drawing area** to change that mapping:

- Drag the blue rectangle to choose where input lands on the desktop.
- Drag a corner to resize it.
- Enable **Lock phone aspect ratio** to preserve the phone display’s aspect ratio while resizing.
- Use **Fit** to center the largest aspect-correct area, or **Full screen** to map the entire desktop.

Open the phone page at least once before using aspect-ratio locking, so the app can detect the device dimensions.

## Settings

- **Port** — defaults to `8000`; set it before starting the server.
- **Stylus only (ignore touch)** — ignores events reported as touch, helping prevent finger contact from drawing. Mouse and pen hover/movement remain available.

Settings are saved to `tablet_config.json` beside the script (or beside the packaged executable), so they persist across launches.

## Network and security

The server listens on all network interfaces and does not require authentication or encryption. Only run it on a network you trust. Do not expose its port to the internet.

If the phone cannot connect:

1. Confirm both devices are on the same Wi-Fi/LAN and that the PC is not using a guest or isolated network.
2. Verify that the address shown by the app is reachable from the phone.
3. Allow Python (or the packaged app) through Windows Firewall for private networks, or permit the selected TCP port.
4. Try another unused port in the app, then restart the server.

## Build a Windows app

Install PyInstaller, then run:

```powershell
py -m pip install pyinstaller
py -m PyInstaller --noconfirm --onedir --windowed --name PenRelay --add-data "index.html;." server.py
```

The packaged app is created under `dist\PenRelay`. Keep the generated folder intact; it includes the web page the app serves to the phone.

## Project layout

| File | Purpose |
| --- | --- |
| `server.py` | Tkinter control panel, local HTTP/WebSocket server, settings, and Windows pen injection. |
| `index.html` | Full-screen mobile input surface and WebSocket client. |
| `tablet_config.json` | Saved mapping and app preferences; created/updated by the app. |
| `requirements.txt` | Python runtime dependencies. |

## Limitations

- Input maps to the primary Windows display; multi-monitor selection is not currently available.
- Pressure and hover depend on the phone, stylus, and browser reporting Pointer Event data.
- The connection is local-network only; there is no remote-access, authentication, or TLS support.
