import 'package:flutter/material.dart';

import 'package:flutter_application_1/features/scan/scan_screen.dart';

/// `/scan/capture` renders the identical full-screen scanner instrument as the
/// `/scan` tab root, so a pushed capture route is coherent (and gets a real
/// back affordance, since the route can pop).
class ScanCaptureScreen extends StatelessWidget {
  const ScanCaptureScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const ScanScreen();
  }
}
