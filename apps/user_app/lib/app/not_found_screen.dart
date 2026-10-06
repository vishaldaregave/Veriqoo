import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'routes.dart';

/// Fallback shown by GoRouter's `errorBuilder` for unmatched locations.
class NotFoundScreen extends StatelessWidget {
  const NotFoundScreen({super.key, this.location});

  /// The location that failed to match (shown as supporting detail).
  final String? location;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return Scaffold(
      backgroundColor: tokens.bg,
      body: SafeArea(
        child: VeriqooErrorState(
          title: 'Page not found',
          message: location,
          onRetry: () => context.go(AppRoutes.homePath),
          retryLabel: 'Go home',
        ),
      ),
    );
  }
}
