import 'dart:ui' show ImageFilter;

import 'package:flutter/material.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/features/auth/auth_strings.dart';
import 'package:flutter_application_1/features/auth/widgets/auth_background.dart';

/// The shared hero shell every auth screen renders inside.
///
/// Composes three things so the six screens share one visual language:
/// 1. the cinematic [AuthBackground] (near-black motion backdrop);
/// 2. the VERIQOO wordmark + optional [subtitle]; and
/// 3. a restrained translucent glass panel (radius `lg`) wrapping [child].
///
/// On entrance a single [AnimationController] drives a staggered fade + rise:
/// the wordmark settles first, then the panel. When the platform reduce-motion
/// flag is set the controller jumps straight to its end state, so the screen
/// appears fully composed with no animation. The per-input focus line is
/// provided by [VeriqooTextField], so screens get that for free.
class AuthScaffold extends StatefulWidget {
  const AuthScaffold({
    super.key,
    required this.child,
    this.title = AuthStrings.wordmark,
    this.subtitle,
    this.showBack = false,
    this.onBack,
    this.footer,
  });

  /// Screen body, rendered inside the glass panel.
  final Widget child;

  /// Hero wordmark. Defaults to the VERIQOO brand mark.
  final String title;

  /// Optional supporting line beneath the wordmark.
  final String? subtitle;

  /// When true a back affordance is overlaid in the top-left.
  final bool showBack;

  /// Custom back handler; defaults to [Navigator.maybePop].
  final VoidCallback? onBack;

  /// Optional content rendered beneath the panel (e.g. secondary links).
  final Widget? footer;

  @override
  State<AuthScaffold> createState() => _AuthScaffoldState();
}

class _AuthScaffoldState extends State<AuthScaffold>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _headerFade;
  late final Animation<Offset> _headerSlide;
  late final Animation<double> _panelFade;
  late final Animation<Offset> _panelSlide;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: VeriqooMotion.cinematic,
    );
    final enter = VeriqooMotion.enter;
    // Wordmark settles over the first ~60% of the pass; the panel reveals from
    // ~30% so the two overlap into one continuous entrance.
    _headerFade = CurvedAnimation(
      parent: _controller,
      curve: Interval(0.0, 0.6, curve: enter),
    );
    _panelFade = CurvedAnimation(
      parent: _controller,
      curve: Interval(0.3, 1.0, curve: enter),
    );
    _headerSlide = Tween<Offset>(
      begin: const Offset(0, 0.12),
      end: Offset.zero,
    ).animate(_headerFade);
    _panelSlide = Tween<Offset>(
      begin: const Offset(0, 0.08),
      end: Offset.zero,
    ).animate(_panelFade);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Reduced motion resolves to the static end state; otherwise play once.
    if (VeriqooMotion.reduceMotion(context)) {
      _controller.value = 1;
    } else if (_controller.status == AnimationStatus.dismissed) {
      _controller.forward();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;

    return Scaffold(
      backgroundColor: tokens.bgTrue,
      body: Stack(
        fit: StackFit.expand,
        children: [
          const Positioned.fill(child: AuthBackground()),
          SafeArea(
            child: Stack(
              children: [
                Positioned.fill(child: _buildContent(context, tokens)),
                if (widget.showBack)
                  Positioned(
                    top: VeriqooSpacing.s8,
                    left: VeriqooSpacing.s8,
                    child: VeriqooIconButton(
                      icon: VeriqooIcons.back,
                      semanticLabel: 'Back',
                      onPressed:
                          widget.onBack ?? () => Navigator.maybePop(context),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildContent(BuildContext context, VeriqooTokens tokens) {
    return LayoutBuilder(
      builder: (context, constraints) {
        return SingleChildScrollView(
          child: ConstrainedBox(
            constraints: BoxConstraints(minHeight: constraints.maxHeight),
            child: Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: VeriqooSpacing.s24,
                vertical: VeriqooSpacing.s32,
              ),
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 440),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      _header(tokens),
                      const SizedBox(height: VeriqooSpacing.s32),
                      FadeTransition(
                        opacity: _panelFade,
                        child: SlideTransition(
                          position: _panelSlide,
                          child: _glassPanel(tokens, widget.child),
                        ),
                      ),
                      if (widget.footer != null) ...[
                        const SizedBox(height: VeriqooSpacing.s24),
                        FadeTransition(
                          opacity: _panelFade,
                          child: widget.footer!,
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _header(VeriqooTokens tokens) {
    return FadeTransition(
      opacity: _headerFade,
      child: SlideTransition(
        position: _headerSlide,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.center,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              widget.title,
              textAlign: TextAlign.center,
              style: VeriqooType.h1.copyWith(
                color: tokens.textPrimary,
                letterSpacing: 4,
              ),
            ),
            if (widget.subtitle != null) ...[
              const SizedBox(height: VeriqooSpacing.s12),
              Text(
                widget.subtitle!,
                textAlign: TextAlign.center,
                style: VeriqooType.body.copyWith(color: tokens.textSecondary),
              ),
            ],
          ],
        ),
      ),
    );
  }

  /// A restrained translucent panel — a soft blur over the translucent-surface
  /// token with a hairline edge at radius `lg`. Tasteful, not glassmorphism.
  Widget _glassPanel(VeriqooTokens tokens, Widget child) {
    return ClipRRect(
      borderRadius: VeriqooRadius.lgAll,
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: VeriqooElevation.translucentSurface,
            borderRadius: VeriqooRadius.lgAll,
            border: Border.all(color: tokens.borderHairline),
          ),
          child: Padding(
            padding: const EdgeInsets.all(VeriqooSpacing.s24),
            child: child,
          ),
        ),
      ),
    );
  }
}
