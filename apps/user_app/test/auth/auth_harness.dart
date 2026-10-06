import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/features/auth/biometric_service.dart';

/// A [BiometricService] stand-in that never touches a platform channel.
///
/// Lets the auth tests pump the biometric screen (and the splash) with fully
/// controlled availability / opt-in / result values.
class FakeBiometricService implements BiometricService {
  FakeBiometricService({
    this.available = false,
    bool enabled = false,
    this.authenticateResult = true,
  }) : _enabled = enabled;

  final bool available;
  final bool authenticateResult;
  bool _enabled;

  @override
  Future<bool> isAvailable() async => available;

  @override
  Future<bool> authenticate(String reason) async => authenticateResult;

  @override
  Future<void> setEnabled(bool enabled) async => _enabled = enabled;

  @override
  Future<bool> isEnabled() async => _enabled;
}

/// Wraps a single auth [screen] in the minimum needed to pump it in isolation:
/// a [ProviderScope] (optionally overriding [biometricServiceProvider]) and a
/// [MaterialApp] carrying the VERIQOO dark theme + tokens.
///
/// Deliberately NOT a GoRouter: screens only call `context.go`/Supabase inside
/// user-triggered handlers, so a pump + field-entry test never needs routing
/// and never contacts `Supabase.instance`.
Widget wrapScreen(Widget screen, {FakeBiometricService? biometric}) {
  return ProviderScope(
    overrides: [
      if (biometric != null)
        biometricServiceProvider.overrideWithValue(biometric),
    ],
    child: MaterialApp(
      theme: VeriqooTheme.dark,
      home: screen,
    ),
  );
}
