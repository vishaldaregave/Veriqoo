import 'package:flutter_application_1/features/auth/auth_actions.dart';

/// A test double for [AuthActions] that records sign-out invocations instead of
/// touching `Supabase.instance`. Override `authActionsProvider` with an
/// instance to observe taps.
class FakeAuthActions extends AuthActions {
  FakeAuthActions();

  int signOutCount = 0;

  @override
  Future<void> signOut() async {
    signOutCount++;
  }
}
