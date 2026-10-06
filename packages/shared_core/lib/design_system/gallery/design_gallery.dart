import 'package:flutter/material.dart';

import '../components/veriqoo_app_bar.dart';
import '../components/veriqoo_button.dart';
import '../components/veriqoo_empty_state.dart';
import '../components/veriqoo_error_state.dart';
import '../components/veriqoo_icon_button.dart';
import '../components/veriqoo_inspection_card.dart';
import '../components/veriqoo_loading.dart';
import '../components/veriqoo_navigation_bar.dart';
import '../components/veriqoo_scanner_overlay.dart';
import '../components/veriqoo_score.dart';
import '../components/veriqoo_section_header.dart';
import '../components/veriqoo_status.dart';
import '../components/veriqoo_text_field.dart';
import '../foundations/veriqoo_icons.dart';
import '../painters/compliance_markers.dart';
import '../painters/data_ticker.dart';
import '../painters/inspection_grid.dart';
import '../painters/ocr_overlay.dart';
import '../painters/product_outline.dart';
import '../painters/scanning_line.dart';
import '../painters/technical_coordinates.dart';
import '../painters/verification_pulse.dart';
import '../theme/veriqoo_radius.dart';
import '../theme/veriqoo_spacing.dart';
import '../theme/veriqoo_theme.dart';
import '../theme/veriqoo_tokens.dart';
import '../theme/veriqoo_typography.dart';
import 'mock_data.dart';

/// A living gallery of the VERIQOO design system.
///
/// Renders every token, type style, and component in one scrollable screen and
/// provides a dark/light toggle in the app-bar action. The toggle flips a
/// local [Brightness] via `setState` (no state-management package) and rebuilds
/// an inner [Theme] with [VeriqooTheme.dark] / [VeriqooTheme.light], so the
/// whole gallery re-themes without any per-widget branching.
class DesignGallery extends StatefulWidget {
  const DesignGallery({super.key});

  @override
  State<DesignGallery> createState() => _DesignGalleryState();
}

class _DesignGalleryState extends State<DesignGallery> {
  Brightness _brightness = Brightness.dark;
  int _navIndex = 1;

  final TextEditingController _defaultField = TextEditingController();
  final TextEditingController _filledField =
      TextEditingController(text: 'Organic Wheat Biscuits');
  final TextEditingController _errorField =
      TextEditingController(text: 'Rs.12O');

  bool get _isDark => _brightness == Brightness.dark;

  @override
  void dispose() {
    _defaultField.dispose();
    _filledField.dispose();
    _errorField.dispose();
    super.dispose();
  }

  void _toggleBrightness() {
    setState(() {
      _brightness = _isDark ? Brightness.light : Brightness.dark;
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = _isDark ? VeriqooTheme.dark : VeriqooTheme.light;
    // Wrap the entire gallery in the selected VERIQOO theme so every component
    // resolves its tokens from here regardless of the ambient app theme.
    return Theme(
      data: theme,
      child: Builder(
        builder: (context) {
          final tokens = Theme.of(context).extension<VeriqooTokens>()!;
          return Scaffold(
            backgroundColor: tokens.bg,
            appBar: VeriqooAppBar(
              title: 'VERIQOO DESIGN SYSTEM',
              showBack: false,
              action: VeriqooIconButton(
                icon: VeriqooIcons.settings,
                semanticLabel: _isDark
                    ? 'Switch to light theme'
                    : 'Switch to dark theme',
                onPressed: _toggleBrightness,
              ),
            ),
            body: SafeArea(
              top: false,
              child: ListView(
                padding: const EdgeInsets.fromLTRB(
                  VeriqooSpacing.s24,
                  VeriqooSpacing.s24,
                  VeriqooSpacing.s24,
                  VeriqooSpacing.s96,
                ),
                children: [
                  _buildHeader(tokens),
                  const SizedBox(height: VeriqooSpacing.s48),
                  _section(
                    'Color',
                    'Monochrome ramp · both schemes',
                    _buildColorSwatches(),
                  ),
                  _section('Typography', 'Display to mono', _buildTypeRamp(tokens)),
                  _section('Spacing', '4 to 96', _buildSpacingScale(tokens)),
                  _section(
                    'Radius',
                    'None · sm · md · lg',
                    _buildRadiusScale(tokens),
                  ),
                  _section(
                    'Status',
                    'Shape + glyph + label (never color)',
                    _buildStatusChips(),
                  ),
                  _section('Buttons', 'Variant × state × size', _buildButtons()),
                  _section('Text fields', 'Default · focus · error',
                      _buildTextFields()),
                  _section('App bar', null, _buildAppBarPreview()),
                  _section('Navigation bar', null, _buildNavBarPreview()),
                  _section('Score', 'Animated count-up', _buildScore()),
                  _section(
                    'Inspection ledger',
                    'Mixed verification outcomes',
                    _buildInspectionList(),
                  ),
                  _section('Loading', 'Verification-scan motif',
                      _buildLoading()),
                  _section('Empty & error states', null, _buildStates()),
                  _section('Scanner overlay', null, _buildScanner(tokens)),
                  _section(
                    'Background painters',
                    'Low-opacity ambient effects',
                    _buildPainters(tokens),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  // --- Section scaffolding ---------------------------------------------------

  Widget _section(String title, String? subtitle, Widget content) {
    return Padding(
      padding: const EdgeInsets.only(bottom: VeriqooSpacing.s48),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          VeriqooSectionHeader(title: title, subtitle: subtitle),
          const SizedBox(height: VeriqooSpacing.s16),
          content,
        ],
      ),
    );
  }

  // --- Header ----------------------------------------------------------------

  Widget _buildHeader(VeriqooTokens tokens) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'VERIQOO',
          style: VeriqooType.display.copyWith(color: tokens.textPrimary),
        ),
        const SizedBox(height: VeriqooSpacing.s8),
        Text(
          'A monochrome compliance-inspection design system.',
          style: VeriqooType.bodyL.copyWith(color: tokens.textSecondary),
        ),
        const SizedBox(height: VeriqooSpacing.s16),
        Row(
          children: [
            Text(
              VeriqooMockData.heroInspectionId,
              style: VeriqooType.mono.copyWith(color: tokens.textSecondary),
            ),
            const SizedBox(width: VeriqooSpacing.s16),
            Text(
              VeriqooMockData.heroOcrConfidence,
              style: VeriqooType.mono.copyWith(color: tokens.textTertiary),
            ),
          ],
        ),
      ],
    );
  }

  // --- Color swatches --------------------------------------------------------

  Widget _buildColorSwatches() {
    const entries = <_SwatchSpec>[
      _SwatchSpec('bg', _TokenRef.bg),
      _SwatchSpec('surface', _TokenRef.surface),
      _SwatchSpec('surfaceRaised', _TokenRef.surfaceRaised),
      _SwatchSpec('borderStrong', _TokenRef.borderStrong),
      _SwatchSpec('textPrimary', _TokenRef.textPrimary),
      _SwatchSpec('textSecondary', _TokenRef.textSecondary),
      _SwatchSpec('textTertiary', _TokenRef.textTertiary),
      _SwatchSpec('inverseBg', _TokenRef.inverseBg),
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: const [
            SizedBox(width: 130),
            Expanded(child: _SchemeHeader('DARK')),
            SizedBox(width: VeriqooSpacing.s16),
            Expanded(child: _SchemeHeader('LIGHT')),
          ],
        ),
        const SizedBox(height: VeriqooSpacing.s8),
        for (final entry in entries)
          Padding(
            padding: const EdgeInsets.only(bottom: VeriqooSpacing.s8),
            child: Row(
              children: [
                SizedBox(
                  width: 130,
                  child: Text(
                    entry.label,
                    style: VeriqooType.mono.copyWith(fontSize: 11),
                  ),
                ),
                Expanded(child: _swatch(entry.ref.resolve(VeriqooTokens.dark))),
                const SizedBox(width: VeriqooSpacing.s16),
                Expanded(
                    child: _swatch(entry.ref.resolve(VeriqooTokens.light))),
              ],
            ),
          ),
      ],
    );
  }

  Widget _swatch(Color color) {
    return Container(
      height: 40,
      decoration: BoxDecoration(
        color: color,
        border: Border.all(color: const Color(0x33808080), width: 1),
      ),
    );
  }

  // --- Typography ------------------------------------------------------------

  Widget _buildTypeRamp(VeriqooTokens tokens) {
    final primary = tokens.textPrimary;
    final rows = <_TypeSample>[
      _TypeSample('display', VeriqooType.display, 'Verified'),
      _TypeSample('h1', VeriqooType.h1, 'Compliance report'),
      _TypeSample('h2', VeriqooType.h2, 'Product declarations'),
      _TypeSample('h3', VeriqooType.h3, 'Net quantity'),
      _TypeSample('bodyL', VeriqooType.bodyL, 'Inspect packaged products.'),
      _TypeSample('body', VeriqooType.body, 'Checked against mandatory rules.'),
      _TypeSample('caption', VeriqooType.caption, 'Captured 04 Oct 2026.'),
      _TypeSample('meta', VeriqooType.meta, 'SECTION LABEL'),
      _TypeSample('mono', VeriqooType.mono, 'VRQ-20261004-0182  87/100'),
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final row in rows)
          Padding(
            padding: const EdgeInsets.only(bottom: VeriqooSpacing.s16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  row.name.toUpperCase(),
                  style: VeriqooType.meta.copyWith(color: tokens.textTertiary),
                ),
                const SizedBox(height: VeriqooSpacing.s4),
                Text(row.sample, style: row.style.copyWith(color: primary)),
              ],
            ),
          ),
      ],
    );
  }

  // --- Spacing ---------------------------------------------------------------

  Widget _buildSpacingScale(VeriqooTokens tokens) {
    const steps = <double>[
      VeriqooSpacing.s4,
      VeriqooSpacing.s8,
      VeriqooSpacing.s12,
      VeriqooSpacing.s16,
      VeriqooSpacing.s24,
      VeriqooSpacing.s32,
      VeriqooSpacing.s48,
      VeriqooSpacing.s64,
      VeriqooSpacing.s80,
      VeriqooSpacing.s96,
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final step in steps)
          Padding(
            padding: const EdgeInsets.only(bottom: VeriqooSpacing.s8),
            child: Row(
              children: [
                SizedBox(
                  width: 48,
                  child: Text(
                    step.toInt().toString(),
                    style: VeriqooType.mono.copyWith(fontSize: 11),
                  ),
                ),
                Container(height: 12, width: step, color: tokens.textPrimary),
              ],
            ),
          ),
      ],
    );
  }

  // --- Radius ----------------------------------------------------------------

  Widget _buildRadiusScale(VeriqooTokens tokens) {
    const specs = <_RadiusSpec>[
      _RadiusSpec('none', VeriqooRadius.none),
      _RadiusSpec('sm', VeriqooRadius.sm),
      _RadiusSpec('md', VeriqooRadius.md),
      _RadiusSpec('lg', VeriqooRadius.lg),
    ];
    return Wrap(
      spacing: VeriqooSpacing.s16,
      runSpacing: VeriqooSpacing.s16,
      children: [
        for (final spec in specs)
          Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 64,
                height: 64,
                decoration: BoxDecoration(
                  color: tokens.surface,
                  borderRadius: BorderRadius.circular(spec.radius),
                  border: Border.all(color: tokens.borderStrong, width: 1),
                ),
              ),
              const SizedBox(height: VeriqooSpacing.s8),
              Text(
                '${spec.label} · ${spec.radius.toInt()}',
                style: VeriqooType.meta.copyWith(color: tokens.textSecondary),
              ),
            ],
          ),
      ],
    );
  }

  // --- Status ----------------------------------------------------------------

  Widget _buildStatusChips() {
    return Wrap(
      spacing: VeriqooSpacing.s24,
      runSpacing: VeriqooSpacing.s16,
      children: const [
        VeriqooStatus(kind: VeriqooStatusKind.verified),
        VeriqooStatus(kind: VeriqooStatusKind.flag),
        VeriqooStatus(kind: VeriqooStatusKind.missing),
        VeriqooStatus(kind: VeriqooStatusKind.violation),
      ],
    );
  }

  // --- Buttons ---------------------------------------------------------------

  Widget _buildButtons() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final variant in VeriqooButtonVariant.values) ...[
          Text(
            variant.name.toUpperCase(),
            style: VeriqooType.meta,
          ),
          const SizedBox(height: VeriqooSpacing.s8),
          Wrap(
            spacing: VeriqooSpacing.s12,
            runSpacing: VeriqooSpacing.s12,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              VeriqooButton(
                label: 'Default',
                variant: variant,
                icon: VeriqooIcons.scan,
                onPressed: () {},
              ),
              VeriqooButton(
                label: 'Small',
                variant: variant,
                size: VeriqooButtonSize.small,
                onPressed: () {},
              ),
              VeriqooButton(
                label: 'Large',
                variant: variant,
                size: VeriqooButtonSize.large,
                onPressed: () {},
              ),
              VeriqooButton(
                label: 'Disabled',
                variant: variant,
                onPressed: null,
              ),
              VeriqooButton(
                label: 'Loading',
                variant: variant,
                loading: true,
                onPressed: () {},
              ),
            ],
          ),
          const SizedBox(height: VeriqooSpacing.s24),
        ],
      ],
    );
  }

  // --- Text fields -----------------------------------------------------------

  Widget _buildTextFields() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        VeriqooTextField(
          controller: _defaultField,
          label: 'Product name',
          hintText: 'Search product or inspection',
          prefixIcon: VeriqooIcons.search,
        ),
        const SizedBox(height: VeriqooSpacing.s24),
        VeriqooTextField(
          controller: _filledField,
          label: 'Manufacturer',
          helperText: 'Tap to focus and see the animated underline.',
        ),
        const SizedBox(height: VeriqooSpacing.s24),
        VeriqooTextField(
          controller: _errorField,
          label: 'MRP',
          errorText: 'Enter a valid amount, e.g. Rs.120',
        ),
      ],
    );
  }

  // --- App bar ---------------------------------------------------------------

  Widget _buildAppBarPreview() {
    return _previewFrame(
      child: VeriqooAppBar(
        title: 'Inspection detail',
        showBack: false,
        action: VeriqooIconButton(
          icon: VeriqooIcons.search,
          semanticLabel: 'Search',
          onPressed: () {},
        ),
      ),
    );
  }

  // --- Navigation bar --------------------------------------------------------

  Widget _buildNavBarPreview() {
    return VeriqooNavigationBar(
      currentIndex: _navIndex,
      onDestinationSelected: (index) => setState(() => _navIndex = index),
    );
  }

  // --- Score -----------------------------------------------------------------

  Widget _buildScore() {
    return Center(
      child: VeriqooScore(
        value: VeriqooMockData.heroScore,
        caption: 'Score',
      ),
    );
  }

  // --- Inspection ledger -----------------------------------------------------

  Widget _buildInspectionList() {
    return Column(
      children: [
        for (final row in VeriqooMockData.inspections)
          VeriqooInspectionCard(
            inspectionId: row.inspectionId,
            timestamp: row.timestamp,
            product: row.analysis.productName,
            score: row.score,
            status: row.status,
            onTap: () {},
          ),
      ],
    );
  }

  // --- Loading ---------------------------------------------------------------

  Widget _buildLoading() {
    return const Center(child: VeriqooLoading(message: 'Verifying label'));
  }

  // --- Empty & error ---------------------------------------------------------

  Widget _buildStates() {
    return Column(
      children: [
        _previewFrame(
          height: 240,
          child: VeriqooEmptyState(
            icon: VeriqooIcons.history,
            title: 'No inspections yet',
            message: 'Your scanned products will appear here.',
          ),
        ),
        const SizedBox(height: VeriqooSpacing.s16),
        _previewFrame(
          height: 240,
          child: VeriqooErrorState(
            message: 'We could not read the label. Try again in better light.',
            onRetry: () {},
          ),
        ),
      ],
    );
  }

  // --- Scanner ---------------------------------------------------------------

  Widget _buildScanner(VeriqooTokens tokens) {
    return ClipRect(
      child: SizedBox(
        height: 360,
        child: DecoratedBox(
          decoration: BoxDecoration(
            border: Border.all(color: tokens.borderHairline, width: 1),
          ),
          child: const VeriqooScannerOverlay(
            hint: 'Align the label within the frame',
          ),
        ),
      ),
    );
  }

  // --- Painters --------------------------------------------------------------

  Widget _buildPainters(VeriqooTokens tokens) {
    final painters = <_PainterSpec>[
      const _PainterSpec('InspectionGrid', InspectionGrid()),
      const _PainterSpec('ScanningLine', ScanningLine()),
      const _PainterSpec('OCROverlay', OCROverlay()),
      const _PainterSpec('DataTicker', DataTicker()),
      const _PainterSpec('ProductOutline', ProductOutline()),
      const _PainterSpec('VerificationPulse', VerificationPulse()),
      const _PainterSpec('ComplianceMarkers', ComplianceMarkers()),
      const _PainterSpec('TechnicalCoordinates', TechnicalCoordinates()),
    ];
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = (constraints.maxWidth - VeriqooSpacing.s16) / 2;
        return Wrap(
          spacing: VeriqooSpacing.s16,
          runSpacing: VeriqooSpacing.s16,
          children: [
            for (final spec in painters)
              SizedBox(
                width: width,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      height: 120,
                      decoration: BoxDecoration(
                        color: tokens.bgTrue,
                        border:
                            Border.all(color: tokens.borderHairline, width: 1),
                      ),
                      child: ClipRect(child: spec.painter),
                    ),
                    const SizedBox(height: VeriqooSpacing.s8),
                    Text(
                      spec.label,
                      style: VeriqooType.mono.copyWith(
                        color: tokens.textSecondary,
                        fontSize: 11,
                      ),
                    ),
                  ],
                ),
              ),
          ],
        );
      },
    );
  }

  // --- Shared ----------------------------------------------------------------

  Widget _previewFrame({required Widget child, double? height}) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    final framed = DecoratedBox(
      decoration: BoxDecoration(
        color: tokens.surface,
        border: Border.all(color: tokens.borderHairline, width: 1),
      ),
      child: child,
    );
    if (height == null) {
      return framed;
    }
    return SizedBox(height: height, child: framed);
  }
}

class _SchemeHeader extends StatelessWidget {
  const _SchemeHeader(this.label);

  final String label;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return Text(
      label,
      style: VeriqooType.meta.copyWith(color: tokens.textSecondary),
    );
  }
}

/// Which [VeriqooTokens] color a swatch row resolves, for both schemes.
enum _TokenRef {
  bg,
  surface,
  surfaceRaised,
  borderStrong,
  textPrimary,
  textSecondary,
  textTertiary,
  inverseBg;

  Color resolve(VeriqooTokens tokens) {
    switch (this) {
      case _TokenRef.bg:
        return tokens.bg;
      case _TokenRef.surface:
        return tokens.surface;
      case _TokenRef.surfaceRaised:
        return tokens.surfaceRaised;
      case _TokenRef.borderStrong:
        return tokens.borderStrong;
      case _TokenRef.textPrimary:
        return tokens.textPrimary;
      case _TokenRef.textSecondary:
        return tokens.textSecondary;
      case _TokenRef.textTertiary:
        return tokens.textTertiary;
      case _TokenRef.inverseBg:
        return tokens.inverseBg;
    }
  }
}

class _SwatchSpec {
  const _SwatchSpec(this.label, this.ref);

  final String label;
  final _TokenRef ref;
}

class _TypeSample {
  const _TypeSample(this.name, this.style, this.sample);

  final String name;
  final TextStyle style;
  final String sample;
}

class _RadiusSpec {
  const _RadiusSpec(this.label, this.radius);

  final String label;
  final double radius;
}

class _PainterSpec {
  const _PainterSpec(this.label, this.painter);

  final String label;
  final Widget painter;
}
