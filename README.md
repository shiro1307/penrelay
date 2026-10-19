# Phone Tablet

```powershell
py -m pip install -r requirements.txt
py server.py
```

Click **Start server**. Open shown address on phone using same Wi-Fi.

Build Windows app:

```powershell
py -m pip install pyinstaller
py -m PyInstaller --noconfirm --onedir --windowed --name PhoneTablet --add-data "index.html;." server.py
```

Requires Windows 10 version 1809 or later.
