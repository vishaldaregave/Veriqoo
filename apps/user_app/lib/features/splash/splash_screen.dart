import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_application_1/features/auth/auth_controller.dart';
import 'package:flutter_application_1/features/auth/auth_strings.dart';
import 'package:flutter_application_1/features/auth/biometric_service.dart';
import 'package:flutter_application_1/core/theme/pro_palette.dart';

/// Screen 1: Cinematic Splash & Onboarding Screen.
///
/// Features rich dark forest aesthetic with elegant golden-emerald flowing
/// silk waves, branded typography, and seamless Supabase session resolution.
class SplashScreen extends ConsumerStatefulWidget {
  const SplashScreen({super.key});

  @override
  ConsumerState<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends ConsumerState<SplashScreen>
    with SingleTickerProviderStateMixin {
  Timer? _timer;
  late final AnimationController _waveController;

  @override
  void initState() {
    super.initState();
    _waveController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 4),
    )..repeat();

    _timer = Timer(const Duration(milliseconds: 1400), _onMinimumElapsed);
  }

  Future<void> _onMinimumElapsed() async {
    if (!mounted) return;
    final service = ref.read(biometricServiceProvider);

    // Resolve restored Supabase session
    ref.read(authControllerProvider.notifier).resolve();
    if (!mounted) return;

    final authenticated =
        ref.read(authControllerProvider) == AuthState.authenticated;
    if (!authenticated) {
      return;
    }

    if (await service.isEnabled()) {
      if (!mounted) return;
      await service.authenticate(AuthStrings.biometricReason);
    }
  }

  @override
  void dispose() {
    _waveController.dispose();
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: ProPalette.forestDeepDark,
      body: Stack(
        children: [
          // Elegant flowing silk curves
          Positioned.fill(
            child: AnimatedBuilder(
              animation: _waveController,
              builder: (context, child) {
                return CustomPaint(
                  painter: _SplashRibbonPainter(progress: _waveController.value),
                );
              },
            ),
          ),

          // Central Branding Content
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  const Spacer(flex: 3),

                  // Brand Logo / Title
                  const Text(
                    'VERIQOO',
                    style: TextStyle(
                      fontFamily: 'Inter',
                      fontSize: 34,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 4.0,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 10),

                  // Subtitle
                  Text(
                    "Know What's on Your Pack",
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w400,
                      letterSpacing: 0.5,
                      color: const Color(0xFFD4AF37).withValues(alpha: 0.9), // Elegant Gold
                    ),
                  ),

                  const Spacer(flex: 2),

                  // Tagline
                  const Text(
                    'AI-powered\nProduct Compliance\nfor a Safer India',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 15,
                      height: 1.4,
                      fontWeight: FontWeight.w400,
                      color: Color(0xFF94A3B8),
                    ),
                  ),

                  const Spacer(flex: 3),

                  // Footer
                  Text(
                    'Powered by Regulations | Vision | Trust',
                    style: TextStyle(
                      fontSize: 12,
                      letterSpacing: 0.8,
                      color: Colors.white.withValues(alpha: 0.4),
                    ),
                  ),
                  const SizedBox(height: 12),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Custom painter rendering organic flowing silk ribbons in emerald & gold
class _SplashRibbonPainter extends CustomPainter {
  _SplashRibbonPainter({required this.progress});

  final double progress;

  @override
  void paint(Canvas canvas, Size size) {
    final shift = progress * 2 * math.pi;

    // Emerald silk curve 1
    final paint1 = Paint()
      ..shader = LinearGradient(
        colors: [
          const Color(0xFF10B981).withValues(alpha: 0.18),
          const Color(0xFF0E3326).withValues(alpha: 0.05),
        ],
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
      ).createShader(Rect.fromLTWH(0, 0, size.width, size.height))
      ..style = PaintingStyle.fill;

    final path1 = Path();
    path1.moveTo(0, size.height * 0.2);
    path1.cubicTo(
      size.width * 0.4 + math.sin(shift) * 30,
      size.height * 0.15,
      size.width * 0.6,
      size.height * 0.6 + math.cos(shift) * 40,
      size.width,
      size.height * 0.5,
    );
    path1.lineTo(size.width, size.height);
    path1.lineTo(0, size.height);
    path1.close();
    canvas.drawPath(path1, paint1);

    // Golden silk ribbon 2
    final paint2 = Paint()
      ..shader = LinearGradient(
        colors: [
          const Color(0xFFD4AF37).withValues(alpha: 0.14),
          const Color(0xFF10B981).withValues(alpha: 0.08),
          Colors.transparent,
        ],
        begin: Alignment.bottomLeft,
        end: Alignment.topRight,
      ).createShader(Rect.fromLTWH(0, 0, size.width, size.height))
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.0;

    final path2 = Path();
    path2.moveTo(0, size.height * 0.35);
    path2.cubicTo(
      size.width * 0.3,
      size.height * 0.55 + math.cos(shift) * 35,
      size.width * 0.7,
      size.height * 0.3 + math.sin(shift) * 35,
      size.width,
      size.height * 0.65,
    );
    canvas.drawPath(path2, paint2);

    // Subtle bottom glow
    final glowPaint = Paint()
      ..shader = RadialGradient(
        center: const Alignment(0, 0.4),
        radius: 0.8,
        colors: [
          const Color(0xFF10B981).withValues(alpha: 0.08),
          Colors.transparent,
        ],
      ).createShader(Rect.fromLTWH(0, 0, size.width, size.height));
    canvas.drawRect(Rect.fromLTWH(0, 0, size.width, size.height), glowPaint);
  }

  @override
  bool shouldRepaint(covariant _SplashRibbonPainter oldDelegate) =>
      oldDelegate.progress != progress;
}
