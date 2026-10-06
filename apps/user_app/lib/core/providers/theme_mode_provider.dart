import 'package:flutter/material.dart';
import 'package:flutter_riverpod/legacy.dart';

/// App-wide theme mode. Defaults to light (matching the clean Veriqoo design spec);
/// [ThemeMode.system] honors the OS because the root supplies both the light
/// and dark [VeriqooTheme] schemes.
final themeModeProvider = StateProvider<ThemeMode>((ref) => ThemeMode.light);

