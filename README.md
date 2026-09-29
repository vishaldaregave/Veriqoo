# VERIQOO

### Smart Inspection & Compliance Management Platform

> **Turning Inspections into Actionable Compliance Intelligence.**

Veriqoo is a digital inspection and compliance management platform designed to simplify inspection workflows and centralize compliance information.

It brings inspection records, findings, evidence, compliance status, corrective actions, dashboards, and reporting into a structured digital system.

---

## 🚀 Quick Start

### Prerequisites

Install the following before running Veriqoo:

- Flutter SDK
- Dart SDK
- Python 3.x
- Git
- Android Studio / VS Code
- Google Chrome (optional, for web)

You also need valid credentials for the external services used by the project, such as Supabase and Gemini.

---

## 1. Clone the Repository

```bash
git clone https://github.com/vishaldaregave/Veriqoo.git
cd Veriqoo
```

---

## 2. Set Up the Python Environment

From the project root:

```powershell
python -m venv .venv
```

Activate the virtual environment on Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install backend dependencies:

```powershell
pip install -r requirements.txt
```

---

## 3. Start the FastAPI Backend

With the virtual environment activated:

```powershell
python -m uvicorn app.main:app --reload --app-dir backend --port 8010
```

The backend runs at:

```text
http://127.0.0.1:8010
```

Keep this terminal running.

---

## 4. Start the Telegram Bot

Open a second terminal:

```powershell
cd D:\Development\flutter\LegalMetrologyAI
.\.venv\Scripts\Activate.ps1
python telegram_bot/telegram_bot.py
```

Keep this terminal running.

---

## 5. Set Up Flutter

Open another terminal in the project root:

```powershell
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

## 🔐 Runtime Configuration

Veriqoo uses external services such as Supabase and Gemini.

If the application expects Dart `--define` values, use your own local credentials:

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

**Never commit real credentials to GitHub.**

---

# 📌 About Veriqoo

## Problem Statement

Inspection and compliance workflows can become difficult to manage when records are maintained manually or distributed across different systems.

Common challenges include:

- Manual inspection documentation
- Scattered records and evidence
- Difficulty tracking violations
- Limited compliance visibility
- Delayed reporting and follow-up
- Difficulty maintaining inspection history

## Proposed Solution

Veriqoo provides a centralized digital platform for managing inspection and compliance workflows.

The platform is designed to support:

- Digital inspection management
- Inspection findings and evidence
- Compliance and non-compliance tracking
- Violation and corrective-action tracking
- Historical inspection records
- Centralized dashboards
- Reporting and monitoring

---

# ✨ Key Features

### Digital Inspection Management
Structured digital workflows for creating and managing inspections.

### Compliance Tracking
Track compliance status and identify non-compliant cases.

### Evidence Management
Maintain supporting evidence associated with inspection records.

### Violation & Corrective Action Tracking
Record issues and monitor their resolution.

### Centralized Dashboard
Provide a consolidated view of inspection and compliance information.

### Historical Records
Maintain previous inspection information for reference and comparison.

### Role-Based Access
Support appropriate access and permissions for different user roles.

### Reporting
Organize inspection information into structured reports.

---

# 🔄 Core Workflow

```text
INSPECT
   ↓
RECORD
   ↓
VERIFY
   ↓
TRACK
   ↓
ACT
```

---

# 🏗️ System Architecture

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

# 🛠️ Technology Stack

### Frontend
- Flutter
- Dart

### Backend
- Python
- FastAPI
- Uvicorn

### Database / Cloud
- Supabase
- PostgreSQL

### AI / Services
- Gemini API
- Telegram Bot integration

### Development
- Git
- GitHub
- VS Code / Android Studio

---

# 📂 Project Structure

```text
Veriqoo/
│
├── android/                 # Android configuration
├── ios/                     # iOS configuration
├── linux/                   # Linux configuration
├── macos/                   # macOS configuration
├── windows/                 # Windows configuration
├── web/                     # Web configuration
│
├── lib/                     # Flutter application source
├── assets/                  # Application assets
├── images/                  # Images and visual assets
│
├── backend/                 # FastAPI backend
├── supabase/                # Supabase-related files
├── telegram_bot/            # Telegram bot
├── scripts/                 # Supporting scripts
├── test/                    # Tests
│
├── pubspec.yaml             # Flutter dependencies
├── pubspec.lock             # Locked Flutter dependencies
├── requirements.txt         # Python dependencies
├── analysis_options.yaml    # Dart analysis configuration
├── README.md                # Project documentation
└── .gitignore               # Git exclusions
```

---

# ▶️ Complete Startup Order

Run the components in separate terminals.

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

# 🧪 Troubleshooting

### Check Flutter installation

```powershell
flutter doctor
```

### Check connected devices

```powershell
flutter devices
```

### Reinstall Flutter dependencies

```powershell
flutter pub get
```

### Reinstall Python dependencies

```powershell
pip install -r requirements.txt
```

### Restart the backend

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --app-dir backend --port 8010
```

---

# 🔒 Security

Never commit sensitive credentials to GitHub.

Do not upload:

```text
.env
API keys
Gemini API keys
Supabase secret/service keys
Database passwords
Telegram bot tokens
Access tokens
Private credentials
```

Use environment variables or local configuration for sensitive values.

---

# 🌍 Potential Applications

Veriqoo's inspection and compliance workflow can be adapted to areas such as:

- Product compliance
- Food safety
- Healthcare inspections
- Industrial inspections
- Regulatory inspections
- Institutional audits
- Municipal inspections
- Enterprise compliance

---

# 🔮 Future Enhancements

Potential extensions include:

- AI-based risk scoring
- Predictive compliance analytics
- AI anomaly detection
- OCR and document intelligence
- Computer vision-based verification
- Geo-spatial compliance mapping
- Offline inspection mode
- Automated escalation and follow-up
- Multilingual support
- Integration with external government and enterprise systems

---

# 🏆 Hackathon

### CraftVerse 2.0 – 2026

**Pimpri Chinchwad College of Engineering and Research, Pune**

**Domain:** Open Innovation

**Project:** Veriqoo — Smart Inspection & Compliance Management Platform

---

# 👥 Team

### Veriqoo Team

- **Vishal Daregave**
- **[Team Member 2]**
- **[Team Member 3]**
- **[Team Member 4]**

**Institution:** Pimpri Chinchwad College of Engineering and Research, Pune

---

# 🎯 Vision

> **To create a unified digital ecosystem where inspections are easier to conduct, compliance is easier to monitor, and corrective action is easier to track.**

---

# ⭐ Veriqoo

**Inspect. Verify. Comply.**

> **Turning Inspections into Actionable Compliance Intelligence.**
