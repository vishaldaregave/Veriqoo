import 'package:flutter/material.dart';
import 'package:shared_core/design_system/design_system.dart';

/// Separate entrypoint for the VERIQOO design gallery.
///
/// This is intentionally independent of `main.dart` (the live app): it boots
/// straight into [DesignGallery] with no Supabase / dotenv setup so the design
/// system can be reviewed on its own. Run it with:
///
/// ```sh
/// flutter run -t lib/gallery_main.dart
/// flutter build web -t lib/gallery_main.dart
/// ```
void main() {
  runApp(const VeriqooGalleryApp());
}

/// Wraps [DesignGallery] in a [MaterialApp] themed with [VeriqooTheme]. The
/// gallery screen itself owns the dark/light toggle, so these themes just set
/// the baseline before the first toggle.
class VeriqooGalleryApp extends StatelessWidget {
  const VeriqooGalleryApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'VERIQOO Design System',
      theme: VeriqooTheme.light,
      darkTheme: VeriqooTheme.dark,
      themeMode: ThemeMode.dark,
      home: const DesignGallery(),
    );
  }
}
