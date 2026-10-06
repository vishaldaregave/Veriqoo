import 'package:flutter_riverpod/legacy.dart';

/// Connectivity state for the app. Skeleton for later phases — real detection
/// (connectivity_plus, reachability checks) lands when offline support is
/// built. Business logic stays in `shared_core`.
enum NetworkStatus { unknown, online, offline }

/// Current [NetworkStatus]. Defaults to [NetworkStatus.unknown] until a later
/// phase wires real connectivity.
final networkStatusProvider =
    StateProvider<NetworkStatus>((ref) => NetworkStatus.unknown);
