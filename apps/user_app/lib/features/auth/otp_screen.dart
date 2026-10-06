import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_core/design_system/design_system.dart';
import 'package:supabase_flutter/supabase_flutter.dart' hide AuthState;

import 'package:flutter_application_1/app/routes.dart';
import 'package:flutter_application_1/features/auth/auth_strings.dart';
import 'package:flutter_application_1/features/auth/widgets/auth_message.dart';
import 'package:flutter_application_1/features/auth/widgets/auth_scaffold.dart';
import 'package:flutter_application_1/features/auth/widgets/otp_input.dart';

/// Email one-time-code verification.
///
/// Shows six segmented cells ([OtpInput]), a resend action gated by a 60s
/// countdown, and a "change email" escape hatch. Verifying calls Supabase
/// `verifyOTP` with `OtpType.signup`; on success the session arrives and the
/// router guard advances to `/home`. The [email] to verify is passed in from
/// the route's `?email=` query parameter.
class OtpScreen extends StatefulWidget {
  const OtpScreen({super.key, this.email});

  /// The email whose code is being verified (from the route query param).
  final String? email;

  @override
  State<OtpScreen> createState() => _OtpScreenState();
}

class _OtpScreenState extends State<OtpScreen> {
  static const int _resendSeconds = 60;

  String _code = '';
  bool _verifying = false;
  bool _resending = false;
  String? _error;
  Timer? _timer;
  int _secondsLeft = _resendSeconds;

  bool get _hasEmail => widget.email != null && widget.email!.isNotEmpty;

  @override
  void initState() {
    super.initState();
    _startCountdown();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _startCountdown() {
    _timer?.cancel();
    setState(() => _secondsLeft = _resendSeconds);
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (_secondsLeft <= 1) {
        timer.cancel();
        setState(() => _secondsLeft = 0);
      } else {
        setState(() => _secondsLeft -= 1);
      }
    });
  }

  Future<void> _verify() async {
    if (!_hasEmail) {
      setState(() => _error = AuthStrings.otpMissingEmail);
      return;
    }
    if (_code.length != 6) {
      setState(() => _error = AuthStrings.errOtpIncomplete);
      return;
    }

    setState(() {
      _verifying = true;
      _error = null;
    });

    try {
      await Supabase.instance.client.auth.verifyOTP(
        email: widget.email,
        token: _code,
        type: OtpType.signup,
      );
      // Success: a session is established and the guard moves to /home.
    } on AuthException catch (error) {
      if (!mounted) return;
      setState(() => _error = error.message);
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = AuthStrings.errGeneric);
    } finally {
      if (mounted) {
        setState(() => _verifying = false);
      }
    }
  }

  Future<void> _resend() async {
    if (!_hasEmail || _secondsLeft > 0) return;

    setState(() {
      _resending = true;
      _error = null;
    });

    try {
      await Supabase.instance.client.auth.resend(
        type: OtpType.signup,
        email: widget.email,
      );
      if (!mounted) return;
      _startCountdown();
    } on AuthException catch (error) {
      if (!mounted) return;
      setState(() => _error = error.message);
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = AuthStrings.errGeneric);
    } finally {
      if (mounted) {
        setState(() => _resending = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    final busy = _verifying || _resending;

    return AuthScaffold(
      showBack: true,
      onBack: () => context.go(AppRoutes.signupPath),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            AuthStrings.otpTitle,
            textAlign: TextAlign.center,
            style: VeriqooType.h3.copyWith(color: tokens.textPrimary),
          ),
          const SizedBox(height: VeriqooSpacing.s12),
          Text(
            AuthStrings.otpSubtitle,
            textAlign: TextAlign.center,
            style: VeriqooType.body.copyWith(color: tokens.textSecondary),
          ),
          if (_hasEmail) ...[
            const SizedBox(height: VeriqooSpacing.s4),
            Text(
              widget.email!,
              textAlign: TextAlign.center,
              style: VeriqooType.mono.copyWith(color: tokens.textPrimary),
            ),
          ],
          const SizedBox(height: VeriqooSpacing.s32),
          OtpInput(
            enabled: !busy,
            onChanged: (value) => _code = value,
            onCompleted: (value) => _code = value,
          ),
          AuthMessage(_error),
          const SizedBox(height: VeriqooSpacing.s32),
          VeriqooButton(
            label: AuthStrings.otpVerifyCta,
            expand: true,
            loading: _verifying,
            onPressed: _resending ? null : _verify,
          ),
          const SizedBox(height: VeriqooSpacing.s16),
          _ResendControl(
            secondsLeft: _secondsLeft,
            resending: _resending,
            enabled: !_verifying && _hasEmail,
            onResend: _resend,
          ),
          const SizedBox(height: VeriqooSpacing.s8),
          VeriqooButton(
            label: AuthStrings.otpChangeEmailCta,
            variant: VeriqooButtonVariant.ghost,
            expand: true,
            onPressed: busy ? null : () => context.go(AppRoutes.signupPath),
          ),
        ],
      ),
    );
  }
}

/// Resend affordance: a disabled countdown line until it reaches zero, then an
/// enabled ghost button.
class _ResendControl extends StatelessWidget {
  const _ResendControl({
    required this.secondsLeft,
    required this.resending,
    required this.enabled,
    required this.onResend,
  });

  final int secondsLeft;
  final bool resending;
  final bool enabled;
  final VoidCallback onResend;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    if (secondsLeft > 0) {
      return Center(
        child: Text(
          '${AuthStrings.otpResendIn} ${secondsLeft}s',
          style: VeriqooType.caption.copyWith(color: tokens.textSecondary),
        ),
      );
    }
    return VeriqooButton(
      label: AuthStrings.otpResendCta,
      variant: VeriqooButtonVariant.ghost,
      expand: true,
      loading: resending,
      onPressed: enabled ? onResend : null,
    );
  }
}
