# Veriqoo — Quick Run Guide

This guide explains how to run the complete Veriqoo project locally.

## Prerequisites

Install:

- Flutter SDK
- Dart SDK
- Python 3.x
- Git
- Android Studio / VS Code
- Google Chrome (optional, for web)

You will also need valid credentials for the services used by the project, such as Supabase and Gemini.

---

## 1. Clone the Repository

```bash
git clone https://github.com/vishaldaregave/Veriqoo.git
cd Veriqoo
```

---

## 2. Set Up the Python Backend

Open PowerShell in the project root:

```powershell
cd D:\Development\flutter\LegalMetrologyAI
```

Create a virtual environment if one does not already exist:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the Python dependencies:

```powershell
pip install -r requirements.txt
```

---

## 3. Start the FastAPI Backend

With the virtual environment activated:

```powershell
python -m uvicorn app.main:app --reload --app-dir backend --port 8010
```

The backend will be available at:

```text
http://127.0.0.1:8010
```

Keep this terminal running.

---

## 4. Start the Telegram Bot

Open a **new terminal**.

```powershell
cd D:\Development\flutter\LegalMetrologyAI
.\.venv\Scripts\Activate.ps1
python telegram_bot/telegram_bot.py
```

Keep this terminal running.

---

## 5. Set Up the Flutter Application

Open another terminal:

```powershell
cd D:\Development\flutter\LegalMetrologyAI
flutter pub get
```

Check available devices:

```powershell
flutter devices
```

---

## 6. Run the Flutter Application

### Android / Connected Device

```powershell
flutter run
```

### Chrome

```powershell
flutter run -d chrome
```

---

## 7. Flutter Runtime Configuration

The application uses runtime configuration for services such as Supabase and Gemini.

**Never put real API keys or credentials in the README or public GitHub repository.**

If the application is configured to use Dart defines, provide your own local values:

```powershell
flutter run `
  --dart-define=SUPABASE_URL="<YOUR_SUPABASE_URL>" `
  --dart-define=SUPABASE_KEY="<YOUR_SUPABASE_KEY>" `
  --dart-define=GEMINI_API_KEY="<YOUR_GEMINI_API_KEY>"
```

For Chrome:

```powershell
flutter run -d chrome `
  --dart-define=SUPABASE_URL="<YOUR_SUPABASE_URL>" `
  --dart-define=SUPABASE_KEY="<YOUR_SUPABASE_KEY>" `
  --dart-define=GEMINI_API_KEY="<YOUR_GEMINI_API_KEY>"
```

---

## 8. Recommended Startup Order

Run the components in this order:

### Terminal 1 — Backend

```powershell
cd D:\Development\flutter\LegalMetrologyAI
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --app-dir backend --port 8010
```

### Terminal 2 — Telegram Bot

```powershell
cd D:\Development\flutter\LegalMetrologyAI
.\.venv\Scripts\Activate.ps1
python telegram_bot/telegram_bot.py
```

### Terminal 3 — Flutter

```powershell
cd D:\Development\flutter\LegalMetrologyAI
flutter pub get
flutter run
```

Or:

```powershell
flutter run -d chrome
```

---

## 9. System Overview

```text
                 ┌──────────────────┐
                 │  Flutter Client  │
                 └────────┬─────────┘
                          │
                          ▼
                 ┌──────────────────┐
                 │ FastAPI Backend  │
                 └────────┬─────────┘
                          │
             ┌────────────┼────────────┐
             ▼            ▼            ▼
       ┌──────────┐ ┌──────────┐ ┌──────────┐
       │ Supabase │ │ Gemini AI│ │ Telegram │
       │ Database │ │ Services │ │   Bot    │
       └──────────┘ └──────────┘ └──────────┘
```

---

## 10. Troubleshooting

### Flutter dependencies

```powershell
flutter pub get
```

### Python dependencies

```powershell
pip install -r requirements.txt
```

### Check Flutter setup

```powershell
flutter doctor
```

### Check available devices

```powershell
flutter devices
```

### Restart the backend

Make sure the virtual environment is active:

```powershell
.\.venv\Scripts\Activate.ps1
```

Then:

```powershell
python -m uvicorn app.main:app --reload --app-dir backend --port 8010
```

---

## Security

Never commit the following to GitHub:

```text
.env
API keys
Gemini API keys
Supabase secret keys
Database passwords
Telegram bot tokens
Access tokens
Private credentials
```

Use local environment variables or configuration files for sensitive information.

---

## Quick Command Summary

```text
Clone
  ↓
Create / Activate Python venv
  ↓
Install Python dependencies
  ↓
Start FastAPI backend
  ↓
Start Telegram bot
  ↓
Install Flutter dependencies
  ↓
Run Flutter application
```
