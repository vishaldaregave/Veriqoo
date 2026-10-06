import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'package:flutter_application_1/app/app.dart';

/// Thin bootstrap: load environment, initialize Supabase, run the app.
///
/// The product flow (scan -> OCR -> compliance analysis -> save) now lives in
/// the `/scan` branch of the shell (see `lib/app/router.dart`).
Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  try {
    await dotenv.load(fileName: '.env');
  } catch (e) {
    debugPrint('dotenv load notice: $e');
  }

  const defaultSupabaseUrl = 'https://yukeelocecdehonijqgr.supabase.co';
  const defaultSupabaseKey =
      'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl1a2VlbG9jZWNkZWhvbmlqcWdyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTExMTY3OTEsImV4cCI6MjEwNjY5Mjc5MX0.Pca1twaobFgdbVUlwbWuZ4IniyKylNgf4F4ewzshsD4';

  final fromEnvUrl = dotenv.env['SUPABASE_URL'] ?? const String.fromEnvironment('SUPABASE_URL');
  final supabaseUrl = fromEnvUrl.isNotEmpty ? fromEnvUrl : defaultSupabaseUrl;

  final fromEnvKey = dotenv.env['SUPABASE_ANON_KEY'] ??
      dotenv.env['SUPABASE_KEY'] ??
      const String.fromEnvironment('SUPABASE_KEY');
  final supabaseKey = fromEnvKey.isNotEmpty ? fromEnvKey : defaultSupabaseKey;

  await Supabase.initialize(url: supabaseUrl, publishableKey: supabaseKey);

  runApp(const ProviderScope(child: VeriqooApp()));
}
