import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:local_auth/local_auth.dart';

/// Thin, injectable wrapper over [LocalAuthentication] + [FlutterSecureStorage].
///
/// Every method is best-effort: it catches any platform-channel/plugin failure
/// (local_auth 3.x throws [LocalAuthException]; storage can throw platform
/// exceptions) and resolves to a safe default, so the UI never has to handle a
/// thrown error from biometric hardware or the keystore. Exposed through
/// [biometricServiceProvider] so the biometric screen, the splash unlock, and
/// tests all resolve the same instance — and tests can override it with a fake
/// that never touches a platform channel.
class BiometricService {
  BiometricService({
    LocalAuthentication? localAuth,
    FlutterSecureStorage? storage,
  })  : _localAuth = localAuth ?? LocalAuthentication(),
        _storage = storage ?? const FlutterSecureStorage();

  final LocalAuthentication _localAuth;
  final FlutterSecureStorage _storage;

  /// Secure-storage key recording the user's biometric opt-in.
  static const String _enabledKey = 'veriqoo_biometric_enabled';

  /// True when the device supports biometrics AND at least one is enrolled.
  Future<bool> isAvailable() async {
    try {
      if (!await _localAuth.isDeviceSupported()) {
        return false;
      }
      final enrolled = await _localAuth.getAvailableBiometrics();
      return enrolled.isNotEmpty;
    } catch (_) {
      // Any platform/plugin failure => treat as unavailable, never throw.
      return false;
    }
  }

  /// Prompts for a biometric check. Returns false (never throws) on failure.
  Future<bool> authenticate(String reason) async {
    try {
      return await _localAuth.authenticate(
        localizedReason: reason,
        biometricOnly: true,
        persistAcrossBackgrounding: true,
      );
    } catch (_) {
      return false;
    }
  }

  /// Persists (or clears) the biometric opt-in.
  Future<void> setEnabled(bool enabled) async {
    try {
      if (enabled) {
        await _storage.write(key: _enabledKey, value: 'true');
      } else {
        await _storage.delete(key: _enabledKey);
      }
    } catch (_) {
      // Best-effort persistence; never surface a storage error to the UI.
    }
  }

  /// Whether the user previously opted in to biometric unlock.
  Future<bool> isEnabled() async {
    try {
      return await _storage.read(key: _enabledKey) == 'true';
    } catch (_) {
      return false;
    }
  }
}

/// Resolves the shared [BiometricService]. Override in tests with a fake.
final biometricServiceProvider =
    Provider<BiometricService>((ref) => BiometricService());
