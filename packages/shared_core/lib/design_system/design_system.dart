/// VERIQOO design system — single public barrel.
///
/// Import this file to access the full design system:
///
/// ```dart
/// import 'package:shared_core/design_system/design_system.dart';
/// ```
///
/// Phase 1 exposes the token + theme foundation and the icon facade. Later
/// features add painters, the verification-scan motif, components, and the
/// gallery, which will be re-exported here.
library;

// Theme layer.
export 'theme/veriqoo_colors.dart';
export 'theme/veriqoo_tokens.dart';
export 'theme/veriqoo_typography.dart';
export 'theme/veriqoo_spacing.dart';
export 'theme/veriqoo_radius.dart';
export 'theme/veriqoo_elevation.dart';
export 'theme/veriqoo_motion.dart';
export 'theme/veriqoo_theme.dart';

// Foundations.
export 'foundations/veriqoo_icons.dart';

// Background painters (and their shared pause/reduced-motion base).
export 'painters/background_effect.dart';
export 'painters/inspection_grid.dart';
export 'painters/scanning_line.dart';
export 'painters/ocr_overlay.dart';
export 'painters/data_ticker.dart';
export 'painters/product_outline.dart';
export 'painters/verification_pulse.dart';
export 'painters/compliance_markers.dart';
export 'painters/technical_coordinates.dart';

// Signature verification-scan motif.
export 'motif/verification_scan.dart';

// Components.
export 'components/veriqoo_button.dart';
export 'components/veriqoo_icon_button.dart';
export 'components/veriqoo_text_field.dart';
export 'components/veriqoo_app_bar.dart';
export 'components/veriqoo_navigation_bar.dart';
export 'components/veriqoo_section_header.dart';
export 'components/veriqoo_divider.dart';
export 'components/veriqoo_status.dart';
export 'components/veriqoo_score.dart';
export 'components/veriqoo_inspection_card.dart';
export 'components/veriqoo_bottom_sheet.dart';
export 'components/veriqoo_modal.dart';
export 'components/veriqoo_loading.dart';
export 'components/veriqoo_empty_state.dart';
export 'components/veriqoo_error_state.dart';
export 'components/veriqoo_scanner_overlay.dart';

// Gallery (mock data + the design gallery screen).
export 'gallery/mock_data.dart';
export 'gallery/design_gallery.dart';
