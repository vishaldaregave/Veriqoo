import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/features/home/home_user.dart';

/// The contextual greeting line, e.g. `GOOD MORNING, Ada`, in meta style.
///
/// Reads the guarded [currentUserProvider]; [greetingLine] falls back to the
/// bare time-of-day prefix when no name/email is available.
class HomeGreeting extends ConsumerWidget {
  const HomeGreeting({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    final user = ref.watch(currentUserProvider);
    final line = greetingLine(user, DateTime.now());

    return Text(
      line,
      style: VeriqooType.meta.copyWith(color: tokens.textSecondary),
    );
  }
}
