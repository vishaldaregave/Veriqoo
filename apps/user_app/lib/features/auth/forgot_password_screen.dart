import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_core/design_system/design_system.dart';
import 'package:supabase_flutter/supabase_flutter.dart' hide AuthState;

import 'package:flutter_application_1/app/routes.dart';
import 'package:flutter_application_1/features/auth/auth_config.dart';
import 'package:flutter_application_1/features/auth/auth_strings.dart';
import 'package:flutter_application_1/features/auth/auth_validators.dart';
import 'package:flutter_application_1/features/auth/widgets/auth_message.dart';
import 'package:flutter_application_1/features/auth/widgets/auth_scaffold.dart';

/// Requests a password-reset email via Supabase `resetPasswordForEmail`.
///
/// On a successful request the screen always shows the same neutral
/// confirmation (it never reveals whether an account exists for the address),
/// so the flow does not enable account enumeration.
class ForgotPasswordScreen extends StatefulWidget {
  const ForgotPasswordScreen({super.key});

  @override
  State<ForgotPasswordScreen> createState() => _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends State<ForgotPasswordScreen> {
  final _emailController = TextEditingController();
  bool _loading = false;
  bool _sent = false;
  String? _emailError;
  String? _submitError;

  @override
  void dispose() {
    _emailController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final email = _emailController.text.trim();
    if (!AuthValidators.isValidEmail(email)) {
      setState(() => _emailError = AuthStrings.errInvalidEmail);
      return;
    }

    setState(() {
      _loading = true;
      _emailError = null;
      _submitError = null;
    });

    try {
      await Supabase.instance.client.auth.resetPasswordForEmail(
        email,
        redirectTo: AuthConfig.passwordResetRedirectUrl,
      );
      if (!mounted) return;
      setState(() => _sent = true);
    } on AuthException catch (error) {
      if (!mounted) return;
      setState(() => _submitError = error.message);
    } catch (_) {
      if (!mounted) return;
      setState(() => _submitError = AuthStrings.errGeneric);
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;

    return AuthScaffold(
      showBack: true,
      onBack: () => context.go(AppRoutes.loginPath),
      child: _sent
          ? _SentState(onBack: () => context.go(AppRoutes.loginPath))
          : Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  AuthStrings.forgotTitle,
                  textAlign: TextAlign.center,
                  style: VeriqooType.h3.copyWith(color: tokens.textPrimary),
                ),
                const SizedBox(height: VeriqooSpacing.s12),
                Text(
                  AuthStrings.forgotSubtitle,
                  textAlign: TextAlign.center,
                  style: VeriqooType.body.copyWith(color: tokens.textSecondary),
                ),
                const SizedBox(height: VeriqooSpacing.s32),
                VeriqooTextField(
                  controller: _emailController,
                  label: AuthStrings.forgotEmailLabel,
                  hintText: AuthStrings.forgotEmailHint,
                  keyboardType: TextInputType.emailAddress,
                  textInputAction: TextInputAction.done,
                  enabled: !_loading,
                  errorText: _emailError,
                  onSubmitted: (_) => _submit(),
                ),
                AuthMessage(_submitError),
                const SizedBox(height: VeriqooSpacing.s32),
                VeriqooButton(
                  label: AuthStrings.forgotSendCta,
                  expand: true,
                  loading: _loading,
                  onPressed: _submit,
                ),
              ],
            ),
    );
  }
}

/// Neutral "we sent it (if the account exists)" confirmation.
class _SentState extends StatelessWidget {
  const _SentState({required this.onBack});

  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(VeriqooIcons.verified, size: 40, color: tokens.textPrimary),
        const SizedBox(height: VeriqooSpacing.s16),
        Text(
          AuthStrings.forgotSentTitle,
          textAlign: TextAlign.center,
          style: VeriqooType.h3.copyWith(color: tokens.textPrimary),
        ),
        const SizedBox(height: VeriqooSpacing.s8),
        Text(
          AuthStrings.forgotSentBody,
          textAlign: TextAlign.center,
          style: VeriqooType.body.copyWith(color: tokens.textSecondary),
        ),
        const SizedBox(height: VeriqooSpacing.s24),
        VeriqooButton(
          label: AuthStrings.forgotBackToSignInCta,
          expand: true,
          onPressed: onBack,
        ),
      ],
    );
  }
}
