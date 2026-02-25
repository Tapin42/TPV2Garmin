# TPV2Garmin Design Document

**Date:** 2026-02-25
**Status:** Approved

## Problem

TrainingPeaks Virtual (TPV) records indoor cycling activities as FIT files. When uploaded to Garmin Connect manually, these files lack key training load metrics (Training Effect, Training Load) because Garmin only calculates them for activities recorded on recognized Garmin devices.

## Solution

A lightweight Windows desktop app that watches the TPV FIT files folder, fixes new files by spoofing the device type to a Garmin Edge, and uploads them to Garmin Connect automatically.

## Architecture Overview

**TPV2Garmin** is a Python desktop app built as a thin wrapper around Fit-File-Faker, packaged as a single `.exe` via PyInstaller.

### Core Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| GUI Window | tkinter | Main window with status log, buttons, settings |
| System Tray | pystray + Pillow | Minimize-to-tray, right-click menu |
| FIT Fixer | Fit-File-Faker (wraps fit-tool) | Modify device fields in FIT files |
| Uploader | garth (via Fit-File-Faker) | OAuth login + upload to Garmin Connect |
| Folder Watcher | watchdog | Monitor TPV folder for new .fit files |
| Process Monitor | psutil | Detect TPVirtual.exe for TPV-linked mode |
| Notifications | win10toast-click | Windows toast notifications |
| Config | json + appdirs | Settings in %APPDATA%/TPV2Garmin/ |

## Tech Stack & Dependencies

- **Python 3.11+** — packaged as standalone `.exe` via PyInstaller
- **Fit-File-Faker** — core FIT modification + Garmin upload (brings fit-tool and garth transitively)
- **tkinter** — GUI (built into Python)
- **pystray + Pillow** — system tray icon
- **watchdog** — folder monitoring
- **psutil** — process detection for TPV-linked mode
- **win10toast-click** — Windows toast notifications
- **appdirs** — cross-platform %APPDATA% resolution

### Config Directory: `%APPDATA%/TPV2Garmin/`

| File | Purpose |
|------|---------|
| `config.json` | Folder path, device selection, run mode, auto-start preference |
| `garth_tokens/` | Garmin OAuth tokens (persisted, login only once) |
| `processed.log` | List of already-processed filenames to avoid duplicates |
| `processed/` | Copies of fixed FIT files |
| `app.log` | Rolling log file |

## FIT File Modification

### What Gets Changed

All modifications are performed by Fit-File-Faker on the `file_id` and `device_info` FIT messages:

| Field | Original (TPV) | Modified |
|-------|----------------|----------|
| `manufacturer` | 255 (Development) | 1 (Garmin) |
| `product` | varies | 4440 (Edge 1050, default) |
| `serial_number` | varies | Consistent random value (generated once at setup) |

### Device Selection

- **Default:** Garmin Edge 1050 (product 4440) — proven to trigger Training Effect calculation
- **Configurable:** User can pick from Fit-File-Faker's device list via dropdown in Settings
- **Tacx devices available as experimental option** — manufacturer=89 is unproven for manual uploads; Fit-File-Faker itself hardcodes manufacturer=1 even for Tacx selections

### Why Not Tacx?

While Tacx (manufacturer=89) would be the most "honest" spoof for indoor trainer activities, and the Tacx Training App is on Garmin's whitelist:
- That whitelist works through the official Tacx-to-Garmin API sync, not manual FIT uploads
- No community confirmation that manufacturer=89 triggers Training Status for uploaded files
- Training Effect is calculated on the Garmin wearable via Physio TrueUp — only manufacturer=1 has been confirmed to work for this pathway

### Why a Consistent Serial Number?

Garmin Connect uses the serial number to group activities by device. A random-per-file serial would create a new "device" each time in the user's Garmin profile. The serial is generated once during setup and reused for all files.

## Run Modes

| Mode | Behavior |
|------|----------|
| **Watch** | Continuously watches the folder for new files |
| **Process Now** | One-shot scan: processes any unprocessed files, then idles |
| **Auto-start with Windows** | Launches at login, sits in tray |
| **TPV-linked** | Only activates when TPVirtual.exe is running (+5 min grace period) |

### TPV-linked Mode (Detail)

1. Poll every 5 seconds for `TPVirtual.exe` process (negligible CPU via psutil)
2. Once detected, start the folder watcher
3. When `TPVirtual.exe` exits, detect via `psutil.Process.wait()` (zero CPU — blocks until exit)
4. Keep watching for 5 minutes after exit (FIT file may be written after app closes)
5. Return to idle polling

Pairs naturally with Auto-start: app starts at login, sits silently in tray, springs into action when TPV launches.

## GUI Design

### First Launch — Setup Wizard (3 steps)

1. **Garmin Login** — "Connect your Garmin account" button. Browser-based OAuth via garth. Shows "Connected as user@..." when done.
2. **Folder Selection** — Auto-detects TPV default path (`Documents/TPVirtual/*/FITFiles`). Browse button to override. Dropdown if multiple user folders found.
3. **Device Selection** — Dropdown defaulting to "Garmin Edge 1050 (Recommended)". Grouped: Recommended > Garmin bike computers > Garmin watches > Tacx (experimental).

### Main Window

```
+-- TPV2Garmin ------------------------------------+
|                                                   |
|  Watching: C:\...\FITFiles              [Browse]  |
|  Device:   Edge 1050                    [Change]  |
|  Status:   * Watching for new files               |
|                                                   |
|  [Start/Stop Watching]        [Process Now]       |
|                                                   |
|  +- Activity Log -------------------------------+ |
|  | 14:32 - Uploaded ride_0225.fit               | |
|  | 14:32 - Fixed ride_0225.fit                  | |
|  | 14:30 - New file detected                    | |
|  +----------------------------------------------+ |
|                                                   |
|  [Settings]                          [Minimize]   |
+---------------------------------------------------+
```

### Settings Panel

- Run mode selection (Watch / TPV-linked)
- Auto-start with Windows toggle
- Notification preferences
- Re-authenticate Garmin
- Device selection
- About / version

### System Tray

- Minimize closes window to tray icon
- Right-click menu: Open, Process Now, Start/Stop Watching, Quit

### Notifications

- Toast notification on successful upload: "Ride uploaded to Garmin Connect"
- Toast notification on failure: "Upload failed — click to open TPV2Garmin"
- Toast on auth expiry: "Please re-authenticate with Garmin"
- All events also logged in the Activity Log panel and app.log

## File Processing Pipeline

```
New .fit file detected in watched folder
         |
         v
Wait for file write to complete (poll file size stability for 2s)
         |
         v
Check processed.log -- already handled? --> Skip
         |
         v
Copy original to %APPDATA%/TPV2Garmin/processed/
         |
         v
Call Fit-File-Faker to fix the copy:
  - manufacturer --> 1 (Garmin)
  - product --> 4440 (Edge 1050) or user's choice
  - serial_number --> consistent value from config
  - Updates file_id + all device_info messages
         |
         v
Upload fixed file to Garmin Connect via garth
         |
         v
Log filename to processed.log
         |
         v
Toast notification: "Ride uploaded to Garmin Connect"
```

### Error Handling

| Scenario | Behavior |
|----------|----------|
| Garmin auth expired | Toast "Please re-authenticate", open main window to Settings |
| Upload fails (network) | Retry 3 times with 30s backoff, then toast failure |
| FIT file corrupt/unreadable | Toast error, skip file, log it |
| File still being written | 2-second file size stability check prevents partial reads |

## Project Structure

```
TPV2Garmin/
  src/
    tpv2garmin/
      __init__.py
      app.py              # Entry point, tkinter main window
      tray.py             # System tray icon via pystray
      wizard.py           # First-launch setup wizard
      watcher.py          # watchdog folder monitor
      process_monitor.py  # psutil TPVirtual.exe detection
      fixer.py            # Wrapper around Fit-File-Faker
      uploader.py         # garth upload to Garmin Connect
      config.py           # Config read/write from %APPDATA%
      notifications.py    # Toast + log notifications
      assets/
        icon.ico          # App/tray icon
  build/
    tpv2garmin.spec       # PyInstaller spec for .exe build
  requirements.txt
  pyproject.toml
  .gitignore
  docs/
    plans/
      2026-02-25-tpv2garmin-design.md
```

## Packaging & Distribution

- **Build:** PyInstaller `--onefile --windowed --icon=icon.ico` produces single `TPV2Garmin.exe`
- **Distribution:** Single `.exe` file. Download, double-click, setup wizard runs on first launch.
- **Auto-start:** Registry entry in `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` (same approach as Spotify, Discord)
- **Updates (v1):** "Check for updates" button in Settings opens GitHub releases page. No auto-updater initially.

## Future Considerations (Not in v1)

- Auto-updater
- macOS support
- Multiple Garmin account support
- Activity type detection (ride vs run)
- Strava parallel upload
