import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Thin, injectable store for the user's recent search queries, persisted in
/// [FlutterSecureStorage] (already a direct dependency — D1).
///
/// Every method is best-effort: it catches any platform-channel/storage failure
/// and resolves to a safe default (an empty or unchanged list), so the search
/// UI never has to handle a thrown error from the keystore. Mirrors the
/// [BiometricService] pattern and is exposed through [recentSearchesStoreProvider]
/// so the search screen and tests resolve the same instance — and tests can
/// override it with a fake that never touches a platform channel.
class RecentSearchesStore {
  RecentSearchesStore({FlutterSecureStorage? storage})
    : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  /// Secure-storage key holding the JSON-encoded recent-search list.
  static const String _key = 'veriqoo_recent_searches';

  /// Maximum number of queries retained (newest first).
  static const int maxEntries = 8;

  /// Loads the persisted queries, newest first. Returns an empty list on any
  /// read/decoding failure.
  Future<List<String>> load() async {
    try {
      return _decode(await _storage.read(key: _key));
    } catch (_) {
      // Any storage/plugin failure => treat as no history, never throw.
      return const <String>[];
    }
  }

  /// Records [query] at the front (trimmed; blanks ignored; case-insensitive
  /// de-dupe; capped at [maxEntries]) and returns the updated list.
  Future<List<String>> add(String query) async {
    final trimmed = query.trim();
    if (trimmed.isEmpty) {
      return load();
    }
    final current = await load();
    final next = <String>[
      trimmed,
      for (final entry in current)
        if (entry.toLowerCase() != trimmed.toLowerCase()) entry,
    ].take(maxEntries).toList(growable: false);

    try {
      await _storage.write(key: _key, value: jsonEncode(next));
    } catch (_) {
      // Best-effort persistence; never surface a storage error to the UI.
    }
    return next;
  }

  /// Clears the persisted queries and returns an empty list.
  Future<List<String>> clear() async {
    try {
      await _storage.delete(key: _key);
    } catch (_) {
      // Best-effort; never surface a storage error to the UI.
    }
    return const <String>[];
  }

  List<String> _decode(String? raw) {
    if (raw == null || raw.trim().isEmpty) {
      return const <String>[];
    }
    try {
      final decoded = jsonDecode(raw);
      if (decoded is List) {
        return decoded
            .where((dynamic e) => e != null)
            .map((dynamic e) => e.toString().trim())
            .where((e) => e.isNotEmpty)
            .toList(growable: false);
      }
    } catch (_) {
      // Corrupt payload => treat as no history.
    }
    return const <String>[];
  }
}

/// Resolves the shared [RecentSearchesStore]. Override in tests with a fake.
final recentSearchesStoreProvider = Provider<RecentSearchesStore>(
  (ref) => RecentSearchesStore(),
);

/// Exposes the recent-search list as async state and persists mutations through
/// the [RecentSearchesStore].
class RecentSearchesController extends AsyncNotifier<List<String>> {
  @override
  Future<List<String>> build() {
    return ref.read(recentSearchesStoreProvider).load();
  }

  /// Adds [query] to the front and refreshes the state.
  Future<void> add(String query) async {
    final updated = await ref.read(recentSearchesStoreProvider).add(query);
    state = AsyncData<List<String>>(updated);
  }

  /// Clears all recent searches.
  Future<void> clear() async {
    final updated = await ref.read(recentSearchesStoreProvider).clear();
    state = AsyncData<List<String>>(updated);
  }
}

/// The recent-search list source for the search screen.
final recentSearchesControllerProvider =
    AsyncNotifierProvider<RecentSearchesController, List<String>>(
      RecentSearchesController.new,
    );
