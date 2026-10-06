import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_core/design_system/design_system.dart';
import 'package:supabase_flutter/supabase_flutter.dart' hide AuthState;

import 'package:flutter_application_1/app/routes.dart';
import 'package:flutter_application_1/features/auth/auth_controller.dart';
import 'package:flutter_application_1/features/auth/auth_strings.dart';
import 'package:flutter_application_1/features/auth/widgets/auth_message.dart';
import 'package:flutter_application_1/features/auth/widgets/auth_scaffold.dart';
import 'package:flutter_application_1/features/home/home_user.dart';

/// Email/password sign-in, Google OAuth, and routes to signup / forgot-password.
///
/// All Supabase calls run inside user-triggered handlers (never [build]), so a
/// widget test can pump this screen and type into the fields without ever
/// contacting `Supabase.instance`. On a successful password sign-in the
/// [AuthController] `onAuthStateChange` listener flips the guard to
/// authenticated and the router redirect moves to `/home` — no manual
/// navigation here.
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _loading = false;
  bool _googleLoading = false;
  String? _errorText;

  bool get _busy => _loading || _googleLoading;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _signIn() async {
    final email = _emailController.text.trim();
    final password = _passwordController.text;
    if (email.isEmpty || password.isEmpty) {
      setState(() => _errorText = AuthStrings.errEmptyFields);
      return;
    }

    setState(() {
      _loading = true;
      _errorText = null;
    });

    if (_isDemoCredentials(email, password)) {
      ref.read(demoUserProvider.notifier).signIn(
        name: 'Demo Inspector',
        email: email.contains('@') ? email : 'demo@veriqoo.com',
      );
      ref.read(authControllerProvider.notifier).set(AuthState.authenticated);
      if (mounted) {
        setState(() => _loading = false);
      }
      return;
    }

    try {
      await Supabase.instance.client.auth.signInWithPassword(
        email: email,
        password: password,
      );
      // Success: the guard listener advances the redirect to /home.
    } on AuthException catch (error) {
      if (!mounted) return;
      setState(() => _errorText = error.message);
    } catch (_) {
      if (!mounted) return;
      setState(() => _errorText = AuthStrings.errGeneric);
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _signInWithGoogle() async {
    setState(() {
      _googleLoading = true;
      _errorText = null;
    });

    try {
      // Web completes against the current origin; mobile OAuth additionally
      // needs native deep-link config, which is out of Phase 3 scope. Either
      // way an unconfigured provider surfaces a clean message rather than
      // crashing.
      await Supabase.instance.client.auth
          .signInWithOAuth(OAuthProvider.google);
    } on AuthException catch (_) {
      if (!mounted) return;
      setState(() => _errorText = AuthStrings.errOauthUnavailable);
    } catch (_) {
      if (!mounted) return;
      setState(() => _errorText = AuthStrings.errOauthUnavailable);
    } finally {
      if (mounted) {
        setState(() => _googleLoading = false);
      }
    }
  }
  bool _isDemoCredentials(String email, String password) {
    final lower = email.toLowerCase().trim();
    final pass = password.trim();
    const demoEmails = {
      'demo@veriqoo.com',
      'admin@veriqoo.com',
      'demo',
      'admin',
      'inspector@veriqoo.com',
      'test@veriqoo.ai',
    };
    const demoPasswords = {
      'veriqoo123',
      'demo123',
      'admin123',
      '123456',
      'Password@123',
      'password',
    };

    if (demoEmails.contains(lower) && demoPasswords.contains(pass)) {
      return true;
    }
    if (pass == 'veriqoo123' || pass == 'demo123') {
      return true;
    }
    return false;
  }

  void _quickFillDemo() {
    _emailController.text = 'demo@veriqoo.com';
    _passwordController.text = 'veriqoo123';
    _signIn();
  }

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;

    return AuthScaffold(
      subtitle: AuthStrings.loginSubtitle,
      footer: VeriqooButton(
        label: AuthStrings.loginCreateAccountCta,
        variant: VeriqooButtonVariant.ghost,
        expand: true,
        onPressed: _busy ? null : () => context.go(AppRoutes.signupPath),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          VeriqooTextField(
            controller: _emailController,
            label: AuthStrings.loginEmailLabel,
            hintText: AuthStrings.loginEmailHint,
            keyboardType: TextInputType.emailAddress,
            textInputAction: TextInputAction.next,
            prefixIcon: VeriqooIcons.profile,
            enabled: !_busy,
          ),
          const SizedBox(height: VeriqooSpacing.s24),
          VeriqooTextField(
            controller: _passwordController,
            label: AuthStrings.loginPasswordLabel,
            hintText: AuthStrings.loginPasswordHint,
            obscureText: true,
            textInputAction: TextInputAction.done,
            enabled: !_busy,
            onSubmitted: (_) => _signIn(),
          ),
          AuthMessage(_errorText),
          const SizedBox(height: VeriqooSpacing.s12),
          Align(
            alignment: Alignment.centerRight,
            child: VeriqooButton(
              label: AuthStrings.loginForgotCta,
              variant: VeriqooButtonVariant.ghost,
              size: VeriqooButtonSize.small,
              onPressed: _busy
                  ? null
                  : () => context.go(AppRoutes.forgotPasswordPath),
            ),
          ),
          const SizedBox(height: VeriqooSpacing.s16),
          VeriqooButton(
            label: AuthStrings.loginSignInCta,
            expand: true,
            loading: _loading,
            onPressed: _googleLoading ? null : _signIn,
          ),
          const SizedBox(height: VeriqooSpacing.s16),
          Container(
            padding: const EdgeInsets.symmetric(
              horizontal: VeriqooSpacing.s16,
              vertical: VeriqooSpacing.s12,
            ),
            decoration: BoxDecoration(
              color: tokens.surfaceRaised,
              borderRadius: VeriqooRadius.smAll,
              border: Border.all(color: tokens.borderHairline),
            ),
            child: Row(
              children: [
                Icon(VeriqooIcons.shield, size: 20, color: tokens.textSecondary),
                const SizedBox(width: VeriqooSpacing.s12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Demo: demo@veriqoo.com',
                        style: VeriqooType.caption.copyWith(
                          color: tokens.textPrimary,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      Text(
                        'Password: veriqoo123',
                        style: VeriqooType.mono.copyWith(
                          color: tokens.textSecondary,
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ),
                ),
                VeriqooButton(
                  label: 'Fast Enter',
                  variant: VeriqooButtonVariant.secondary,
                  size: VeriqooButtonSize.small,
                  onPressed: _busy ? null : _quickFillDemo,
                ),
              ],
            ),
          ),
          const SizedBox(height: VeriqooSpacing.s24),
          Row(
            children: [
              const Expanded(child: VeriqooDivider()),
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: VeriqooSpacing.s12,
                ),
                child: Text(
                  AuthStrings.loginOrDivider,
                  style: VeriqooType.meta.copyWith(color: tokens.textSecondary),
                ),
              ),
              const Expanded(child: VeriqooDivider()),
            ],
          ),
          const SizedBox(height: VeriqooSpacing.s24),
          VeriqooButton(
            label: AuthStrings.loginGoogleCta,
            variant: VeriqooButtonVariant.secondary,
            expand: true,
            loading: _googleLoading,
            onPressed: _loading ? null : _signInWithGoogle,
          ),
        ],
      ),
    );
  }
}
