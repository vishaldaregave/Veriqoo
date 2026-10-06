import 'package:flutter_riverpod/legacy.dart';

/// Offline-sync lifecycle. Skeleton for later phases — the queue/flush logic
/// lands when offline support is built. Business logic stays in `shared_core`.
enum OfflineSyncStatus { idle, syncing, error }

/// Current [OfflineSyncStatus]. Defaults to [OfflineSyncStatus.idle].
final offlineSyncProvider =
    StateProvider<OfflineSyncStatus>((ref) => OfflineSyncStatus.idle);
