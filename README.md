# flutter_application_1

A new Flutter project.

## Getting Started

This project is a starting point for a Flutter application.

A few resources to get you started if this is your first Flutter project:

- [Lab: Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Cookbook: Useful Flutter samples](https://docs.flutter.dev/cookbook)

For help getting started with Flutter development, view the
[online documentation](https://docs.flutter.dev/), which offers tutorials,
samples, guidance on mobile development, and a full API reference.

## Gemini API key

The app uses the official Google Gemini API through `GeminiAIAnalysisService`.
Keep the API key out of the source code and pass it at build or run time:

```powershell
flutter run `
	--dart-define=GEMINI_API_KEY=your_gemini_api_key `
	--dart-define=SUPABASE_URL=https://your-project.supabase.co `
	--dart-define=SUPABASE_KEY=your_anon_key
```

`SUPABASE_KEY` must be the public anon/publishable key. Never use a Supabase
service_role or secret key in the Flutter client. The save action writes to an
`inspection_reports` table with product details, OCR text, compliance status,
detected violations, the AI report, an inspection timestamp, and an image URL.

The service sends OCR text to Gemini and parses structured JSON containing the
product name, MRP, net quantity, manufacturer, address, packing/manufacturing
date, customer care details, missing information, and possible issues.
