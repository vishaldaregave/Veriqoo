import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_core/design_system/design_system.dart';
import 'package:supabase_flutter/supabase_flutter.dart' hide AuthState;

import 'package:flutter_application_1/app/routes.dart';
import 'package:flutter_application_1/features/auth/auth_strings.dart';
import 'package:flutter_application_1/features/auth/auth_validators.dart';
import 'package:flutter_application_1/features/auth/widgets/auth_message.dart';
import 'package:flutter_application_1/features/auth/widgets/auth_scaffold.dart';

/// Sets a new password via Supabase `updateUser`, reachable at `/auth/reset`.
///
/// ## Deep-link note (intentionally minimal in Phase 3)
/// A real recovery email opens the app with a recovery token, which
/// supabase_flutter exchanges for a session and emits
/// `AuthChangeEvent.passwordRecovery`. With a session present, the router guard
/// would currently route the user to `/home`; this screen is nonetheless fully
/// functional and route-reachable at `/auth/reset`, and `updateUser` works
/// whenever a (recovery) session exists.
// TODO(phase3+): on AuthChangeEvent.passwordRecovery, route to /auth/reset
// instead of letting the guard fall through to /home.
class ResetPasswordScreen extends StatefulWidget {
  const ResetPasswordScreen({super.key});

  @override
  State<ResetPasswordScreen> createState() => _ResetPasswordScreenState();
}

class _ResetPasswordScreenState extends State<ResetPasswordScreen> {
  final _passwordController = TextEditingController();
  final _confirmController = TextEditingController();
  bool _loading = false;
  bool _success = false;
  String? _passwordError;
  String? _confirmError;
  String? _submitError;

  @override
  void dispose() {
    _passwordController.dispose();
    _confirmController.dispose();
    super.dispose();
  }

  bool _validate() {
    final password = _passwordController.text;
    final confirm = _confirmController.text;
    final passwordError = AuthValidators.isStrongEnough(password)
        ? null
        : AuthStrings.errPasswordTooShort;
    final confirmError =
        confirm == password ? null : AuthStrings.errPasswordMismatch;
    setState(() {
      _passwordError = passwordError;
      _confirmError = confirmError;
    });
    return passwordError == null && confirmError == null;
  }

  Future<void> _submit() async {
    if (!_validate()) return;

    setState(() {
      _loading = true;
      _submitError = null;
    });

    try {
      await Supabase.instance.client.auth.updateUser(
        UserAttributes(password: _passwordController.text),
      );
      if (!mounted) return;
      setState(() => _success = true);
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

  void _continue() {
    final hasSession =
        Supabase.instance.client.auth.currentSession != null;
    context.go(hasSession ? AppRoutes.homePath : AppRoutes.loginPath);
  }

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;

    return AuthScaffold(
      showBack: true,
      onBack: () => context.go(AppRoutes.loginPath),
      child: _success
          ? _SuccessState(onContinue: _continue)
          : Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  AuthStrings.resetTitle,
                  textAlign: TextAlign.center,
                  style: VeriqooType.h3.copyWith(color: tokens.textPrimary),
                ),
                const SizedBox(height: VeriqooSpacing.s12),
                Text(
                  AuthStrings.resetSubtitle,
                  textAlign: TextAlign.center,
                  style: VeriqooType.body.copyWith(color: tokens.textSecondary),
                ),
                const SizedBox(height: VeriqooSpacing.s32),
                VeriqooTextField(
                  controller: _passwordController,
                  label: AuthStrings.resetNewPasswordLabel,
                  hintText: AuthStrings.resetNewPasswordHint,
                  obscureText: true,
                  textInputAction: TextInputAction.next,
                  enabled: !_loading,
                  errorText: _passwordError,
                ),
                const SizedBox(height: VeriqooSpacing.s24),
                VeriqooTextField(
                  controller: _confirmController,
                  label: AuthStrings.resetConfirmLabel,
                  hintText: AuthStrings.resetConfirmHint,
                  obscureText: true,
                  textInputAction: TextInputAction.done,
                  enabled: !_loading,
                  errorText: _confirmError,
                  onSubmitted: (_) => _submit(),
                ),
                AuthMessage(_submitError),
                const SizedBox(height: VeriqooSpacing.s32),
                VeriqooButton(
                  label: AuthStrings.resetUpdateCta,
                  expand: true,
                  loading: _loading,
                  onPressed: _submit,
                ),
              ],
            ),
    );
  }
}

/// Confirmation shown after the password is updated.
class _SuccessState extends StatelessWidget {
  const _SuccessState({required this.onContinue});

  final VoidCallback onContinue;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(VeriqooIcons.verified, size: 40, color: tokens.textPrimary),
        const SizedBox(height: VeriqooSpacing.s16),
        Text(
          AuthStrings.resetSuccessTitle,
          textAlign: TextAlign.center,
          style: VeriqooType.h3.copyWith(color: tokens.textPrimary),
        ),
        const SizedBox(height: VeriqooSpacing.s8),
        Text(
          AuthStrings.resetSuccessBody,
          textAlign: TextAlign.center,
          style: VeriqooType.body.copyWith(color: tokens.textSecondary),
        ),
        const SizedBox(height: VeriqooSpacing.s24),
        VeriqooButton(
          label: AuthStrings.resetContinueCta,
          expand: true,
          onPressed: onContinue,
        ),
      ],
    );
  }
}
