import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_core/design_system/design_system.dart';

/// GoRouter page builders driven by [VeriqooMotion] tokens. Both honor the
/// platform reduce-motion flag by falling back to [NoTransitionPage].

/// An immersive fade — used for the Home and Scan branch roots.
Page<void> fadePage({
  required BuildContext context,
  required LocalKey key,
  required Widget child,
}) {
  if (VeriqooMotion.reduceMotion(context)) {
    return NoTransitionPage<void>(key: key, child: child);
  }
  return CustomTransitionPage<void>(
    key: key,
    transitionDuration: VeriqooMotion.base,
    reverseTransitionDuration: VeriqooMotion.base,
    child: child,
    transitionsBuilder: (context, animation, secondaryAnimation, child) {
      return FadeTransition(
        opacity: CurvedAnimation(parent: animation, curve: VeriqooMotion.enter),
        child: child,
      );
    },
  );
}

/// A shared-axis (slide + fade) transition — used for list -> detail routes.
Page<void> sharedAxisPage({
  required BuildContext context,
  required LocalKey key,
  required Widget child,
}) {
  if (VeriqooMotion.reduceMotion(context)) {
    return NoTransitionPage<void>(key: key, child: child);
  }
  return CustomTransitionPage<void>(
    key: key,
    transitionDuration: VeriqooMotion.slow,
    reverseTransitionDuration: VeriqooMotion.slow,
    child: child,
    transitionsBuilder: (context, animation, secondaryAnimation, child) {
      final curved =
          CurvedAnimation(parent: animation, curve: VeriqooMotion.move);
      return FadeTransition(
        opacity: curved,
        child: SlideTransition(
          position: Tween<Offset>(
            begin: const Offset(0.06, 0),
            end: Offset.zero,
          ).animate(curved),
          child: child,
        ),
      );
    },
  );
}
