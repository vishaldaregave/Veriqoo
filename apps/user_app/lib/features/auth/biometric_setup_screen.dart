import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/app/routes.dart';
import 'package:flutter_application_1/features/auth/auth_strings.dart';
import 'package:flutter_application_1/features/auth/biometric_service.dart';
import 'package:flutter_application_1/features/auth/widgets/auth_message.dart';
import 'package:flutter_application_1/features/auth/widgets/auth_scaffold.dart';

/// Opt-in screen for biometric unlock.
///
/// Reached POST-login (a session ties the opt-in to the account), so it lives
/// OUTSIDE the `/auth` group — the guard bounces authenticated users off any
/// `/auth/*` path to `/home`. It still renders on [AuthScaffold] for one visual
/// language across the auth family. Availability, authentication, and the
/// persisted opt-in all go through the injectable [biometricServiceProvider],
/// so tests override it with a fake and never touch a platform channel.
class BiometricSetupScreen extends ConsumerStatefulWidget {
  const BiometricSetupScreen({super.key});

  @override
  ConsumerState<BiometricSetupScreen> createState() =>
      _BiometricSetupScreenState();
}

class _BiometricSetupScreenState extends ConsumerState<BiometricSetupScreen> {
  late final BiometricService _service;
  bool _checking = true;
  bool _available = false;
  bool _enabling = false;
  bool _enabled = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _service = ref.read(biometricServiceProvider);
    _loadAvailability();
  }

  Future<void> _loadAvailability() async {
    final available = await _service.isAvailable();
    if (!mounted) return;
    setState(() {
      _available = available;
      _checking = false;
    });
  }

  Future<void> _enable() async {
    setState(() {
      _enabling = true;
      _error = null;
    });
    final ok = await _service.authenticate(AuthStrings.biometricReason);
    if (!mounted) return;
    if (ok) {
      await _service.setEnabled(true);
      if (!mounted) return;
      setState(() {
        _enabled = true;
        _enabling = false;
      });
    } else {
      setState(() {
        _error = AuthStrings.errBiometricFailed;
        _enabling = false;
      });
    }
  }

  void _leave() {
    if (context.canPop()) {
      context.pop();
    } else {
      context.go(AppRoutes.settingsPath);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AuthScaffold(
      showBack: true,
      onBack: _leave,
      child: _buildBody(context),
    );
  }

  Widget _buildBody(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;

    if (_checking) {
      return _StatusPanel(
        heading: AuthStrings.biometricTitle,
        children: [
          const SizedBox(height: VeriqooSpacing.s24),
          Center(
            child: SizedBox(
              width: 28,
              height: 28,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                valueColor: AlwaysStoppedAnimation<Color>(tokens.textPrimary),
              ),
            ),
          ),
          const SizedBox(height: VeriqooSpacing.s24),
        ],
      );
    }

    if (!_available) {
      return _StatusPanel(
        icon: VeriqooIcons.alert,
        heading: AuthStrings.biometricUnavailableTitle,
        body: AuthStrings.biometricUnavailableBody,
        children: [
          const SizedBox(height: VeriqooSpacing.s24),
          VeriqooButton(
            label: AuthStrings.biometricSkipCta,
            variant: VeriqooButtonVariant.secondary,
            expand: true,
            onPressed: _leave,
          ),
        ],
      );
    }

    if (_enabled) {
      return _StatusPanel(
        icon: VeriqooIcons.verified,
        heading: AuthStrings.biometricEnabledTitle,
        body: AuthStrings.biometricEnabledBody,
        children: [
          const SizedBox(height: VeriqooSpacing.s24),
          VeriqooButton(
            label: AuthStrings.biometricDoneCta,
            expand: true,
            onPressed: _leave,
          ),
        ],
      );
    }

    return _StatusPanel(
      icon: VeriqooIcons.verified,
      heading: AuthStrings.biometricTitle,
      body: AuthStrings.biometricEnableBody,
      children: [
        AuthMessage(_error),
        const SizedBox(height: VeriqooSpacing.s32),
        VeriqooButton(
          label: AuthStrings.biometricEnableCta,
          expand: true,
          loading: _enabling,
          onPressed: _enable,
        ),
        const SizedBox(height: VeriqooSpacing.s8),
        VeriqooButton(
          label: AuthStrings.biometricSkipCta,
          variant: VeriqooButtonVariant.ghost,
          expand: true,
          onPressed: _enabling ? null : _leave,
        ),
      ],
    );
  }
}

/// Shared layout for the biometric screen's four states: an optional [icon], a
/// [heading], optional [body] copy, then arbitrary [children] (actions).
class _StatusPanel extends StatelessWidget {
  const _StatusPanel({
    required this.heading,
    this.icon,
    this.body,
    this.children = const [],
  });

  final String heading;
  final IconData? icon;
  final String? body;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: [
        if (icon != null) ...[
          Icon(icon, size: 40, color: tokens.textPrimary),
          const SizedBox(height: VeriqooSpacing.s16),
        ],
        Text(
          heading,
          textAlign: TextAlign.center,
          style: VeriqooType.h3.copyWith(color: tokens.textPrimary),
        ),
        if (body != null) ...[
          const SizedBox(height: VeriqooSpacing.s8),
          Text(
            body!,
            textAlign: TextAlign.center,
            style: VeriqooType.body.copyWith(color: tokens.textSecondary),
          ),
        ],
        ...children,
      ],
    );
  }
}
