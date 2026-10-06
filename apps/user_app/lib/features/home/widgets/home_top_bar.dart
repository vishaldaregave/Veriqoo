import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/app/routes.dart';
import 'package:flutter_application_1/core/providers/network_provider.dart';
import 'package:flutter_application_1/features/home/home_strings.dart';

/// The Home root header (NOT a back-bar): the VERIQOO wordmark with a subtle
/// connection indicator on the left, and notifications + profile actions on the
/// right. Being the shell root, it never shows a back affordance.
class HomeTopBar extends ConsumerWidget {
  const HomeTopBar({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    final status = ref.watch(networkStatusProvider);

    return Row(
      children: [
        Text(
          HomeStrings.wordmark,
          style: VeriqooType.h3.copyWith(
            color: tokens.textPrimary,
            fontWeight: FontWeight.w700,
            letterSpacing: 2,
          ),
        ),
        const SizedBox(width: VeriqooSpacing.s12),
        _ConnectionDot(status: status),
        const Spacer(),
        VeriqooIconButton(
          icon: VeriqooIcons.alert,
          semanticLabel: HomeStrings.notificationsLabel,
          onPressed: () => context.go(AppRoutes.notificationsPath),
        ),
        VeriqooIconButton(
          icon: VeriqooIcons.profile,
          semanticLabel: HomeStrings.profileLabel,
          onPressed: () => context.go(AppRoutes.profilePath),
        ),
      ],
    );
  }
}

/// A subtle connection indicator. Meaning is carried by SHAPE (filled dot vs
/// hairline ring) and the meta LABEL — never by color alone.
class _ConnectionDot extends StatelessWidget {
  const _ConnectionDot({required this.status});

  final NetworkStatus status;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    final (String label, bool filled) = switch (status) {
      NetworkStatus.online => (HomeStrings.statusOnline, true),
      NetworkStatus.offline => (HomeStrings.statusOffline, false),
      NetworkStatus.unknown => (HomeStrings.statusUnknown, false),
    };

    return Semantics(
      label: '${HomeStrings.connectionStatusLabel}: $label',
      container: true,
      child: ExcludeSemantics(
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 7,
              height: 7,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: filled ? tokens.textPrimary : Colors.transparent,
                border: Border.all(color: tokens.textSecondary, width: 1),
              ),
            ),
            const SizedBox(width: VeriqooSpacing.s8),
            Text(
              label,
              style: VeriqooType.meta.copyWith(color: tokens.textTertiary),
            ),
          ],
        ),
      ),
    );
  }
}
