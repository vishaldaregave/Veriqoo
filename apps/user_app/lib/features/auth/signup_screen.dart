import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_core/design_system/design_system.dart';
import 'package:supabase_flutter/supabase_flutter.dart' hide AuthState;

import 'package:flutter_application_1/app/routes.dart';
import 'package:flutter_application_1/features/auth/auth_strings.dart';
import 'package:flutter_application_1/features/auth/auth_validators.dart';
import 'package:flutter_application_1/features/auth/widgets/auth_message.dart';
import 'package:flutter_application_1/features/auth/widgets/auth_scaffold.dart';

/// Account creation: name, email, password, confirm-password with per-field
/// validation, backed by Supabase `signUp`.
///
/// On success the next step depends on the project's Supabase config:
/// * a session is returned -> the guard advances to `/home`;
/// * a user but no session -> route to OTP verification (email code);
/// * neither -> show the "check your email" magic-link fallback state.
class SignupScreen extends StatefulWidget {
  const SignupScreen({super.key});

  @override
  State<SignupScreen> createState() => _SignupScreenState();
}

class _SignupScreenState extends State<SignupScreen> {
  final _nameController = TextEditingController();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmController = TextEditingController();

  bool _loading = false;
  bool _checkEmail = false;
  String? _nameError;
  String? _emailError;
  String? _passwordError;
  String? _confirmError;
  String? _submitError;

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
    _passwordController.dispose();
    _confirmController.dispose();
    super.dispose();
  }

  bool _validate() {
    final name = _nameController.text.trim();
    final email = _emailController.text.trim();
    final password = _passwordController.text;
    final confirm = _confirmController.text;

    final nameError = name.isEmpty ? AuthStrings.errNameRequired : null;
    final emailError =
        AuthValidators.isValidEmail(email) ? null : AuthStrings.errInvalidEmail;
    final passwordError = AuthValidators.isStrongEnough(password)
        ? null
        : AuthStrings.errPasswordTooShort;
    final confirmError =
        confirm == password ? null : AuthStrings.errPasswordMismatch;

    setState(() {
      _nameError = nameError;
      _emailError = emailError;
      _passwordError = passwordError;
      _confirmError = confirmError;
    });

    return nameError == null &&
        emailError == null &&
        passwordError == null &&
        confirmError == null;
  }

  Future<void> _signUp() async {
    if (!_validate()) return;

    final email = _emailController.text.trim();
    setState(() {
      _loading = true;
      _submitError = null;
    });

    try {
      final res = await Supabase.instance.client.auth.signUp(
        email: email,
        password: _passwordController.text,
        data: {'display_name': _nameController.text.trim()},
      );
      if (!mounted) return;
      if (res.session != null) {
        // Auto-confirm projects return a session; the guard moves to /home.
        return;
      }
      if (res.user != null) {
        // Email code confirmation: verify via the OTP screen.
        context.go(
          '${AppRoutes.otpPath}?email=${Uri.encodeComponent(email)}',
        );
        return;
      }
      // Magic-link projects return neither: show the check-email fallback.
      setState(() => _checkEmail = true);
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
    if (_checkEmail) {
      return AuthScaffold(
        title: AuthStrings.wordmark,
        subtitle: AuthStrings.signupSubtitle,
        showBack: true,
        onBack: () => context.go(AppRoutes.loginPath),
        child: _CheckEmailState(onContinue: () => context.go(AppRoutes.loginPath)),
      );
    }

    return AuthScaffold(
      title: AuthStrings.wordmark,
      subtitle: AuthStrings.signupSubtitle,
      showBack: true,
      onBack: () => context.go(AppRoutes.loginPath),
      footer: VeriqooButton(
        label: AuthStrings.signupHaveAccountCta,
        variant: VeriqooButtonVariant.ghost,
        expand: true,
        onPressed: _loading ? null : () => context.go(AppRoutes.loginPath),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          VeriqooTextField(
            controller: _nameController,
            label: AuthStrings.signupNameLabel,
            hintText: AuthStrings.signupNameHint,
            textInputAction: TextInputAction.next,
            prefixIcon: VeriqooIcons.profile,
            enabled: !_loading,
            errorText: _nameError,
          ),
          const SizedBox(height: VeriqooSpacing.s24),
          VeriqooTextField(
            controller: _emailController,
            label: AuthStrings.signupEmailLabel,
            hintText: AuthStrings.signupEmailHint,
            keyboardType: TextInputType.emailAddress,
            textInputAction: TextInputAction.next,
            enabled: !_loading,
            errorText: _emailError,
          ),
          const SizedBox(height: VeriqooSpacing.s24),
          VeriqooTextField(
            controller: _passwordController,
            label: AuthStrings.signupPasswordLabel,
            hintText: AuthStrings.signupPasswordHint,
            obscureText: true,
            textInputAction: TextInputAction.next,
            enabled: !_loading,
            errorText: _passwordError,
          ),
          const SizedBox(height: VeriqooSpacing.s24),
          VeriqooTextField(
            controller: _confirmController,
            label: AuthStrings.signupConfirmLabel,
            hintText: AuthStrings.signupConfirmHint,
            obscureText: true,
            textInputAction: TextInputAction.done,
            enabled: !_loading,
            errorText: _confirmError,
            onSubmitted: (_) => _signUp(),
          ),
          AuthMessage(_submitError),
          const SizedBox(height: VeriqooSpacing.s32),
          VeriqooButton(
            label: AuthStrings.signupCreateCta,
            expand: true,
            loading: _loading,
            onPressed: _signUp,
          ),
        ],
      ),
    );
  }
}

/// Inline "check your email" confirmation shown when the project is configured
/// for magic-link sign-up rather than a six-digit code.
class _CheckEmailState extends StatelessWidget {
  const _CheckEmailState({required this.onContinue});

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
          AuthStrings.signupCheckEmailTitle,
          textAlign: TextAlign.center,
          style: VeriqooType.h3.copyWith(color: tokens.textPrimary),
        ),
        const SizedBox(height: VeriqooSpacing.s8),
        Text(
          AuthStrings.signupCheckEmailBody,
          textAlign: TextAlign.center,
          style: VeriqooType.body.copyWith(color: tokens.textSecondary),
        ),
        const SizedBox(height: VeriqooSpacing.s24),
        VeriqooButton(
          label: AuthStrings.loginSignInCta,
          expand: true,
          onPressed: onContinue,
        ),
      ],
    );
  }
}
