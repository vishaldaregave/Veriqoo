import 'package:flutter/material.dart';
import 'package:shared_core/design_system/design_system.dart';

/// Clean, static backdrop for authentication and login screens.
///
/// Keeps the auth screens static (no moving scan lines or ticker animations)
/// while maintaining a premium dark palette with subtle static depth.
class AuthBackground extends StatelessWidget {
  const AuthBackground({super.key});

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>();
    final baseColor = tokens?.bgTrue ?? const Color(0xFF0F172A);

    return Stack(
      fit: StackFit.expand,
      children: [
        // 1. Solid dark base
        ColoredBox(color: baseColor),

        // 2. Subtle static radial aura in top-center
        Positioned.fill(
          child: IgnorePointer(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: RadialGradient(
                  center: const Alignment(0, -0.4),
                  radius: 1.2,
                  colors: [
                    const Color(0xFF133E30).withValues(alpha: 0.22),
                    Colors.transparent,
                  ],
                ),
              ),
            ),
          ),
        ),

        // 3. Static subtle grid (no moving scanning lines or animated tickers)
        Positioned.fill(
          child: IgnorePointer(
            child: InspectionGrid(enabled: false),
          ),
        ),
      ],
    );
  }
}
