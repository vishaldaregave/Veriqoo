# VERIQOO Design System — Phase 1 Implementation Plan

Monochrome design-system foundation for the Flutter monorepo at `c:\WorkSpace\Ajinkya\Veriqoo`.
Work DIRECTLY in the main workspace. Do NOT create a git worktree and do NOT commit.

---

## 0. Ground truth discovered during exploration (read before implementing)

- **Toolchain**: `flutter --version` → Flutter 3.47.4 / Dart 3.13.3 on PATH. Verification gate 1 passes.
- **Monorepo**: two pubspecs — `apps/user_app/pubspec.yaml` (name is literally `flutter_application_1`; keep it) and `packages/shared_core/pubspec.yaml` (name `shared_core`, SDK `^3.0.0`).
- `apps/user_app` depends on `shared_core` via `path: ../../packages/shared_core`. Platforms enabled: android, ios, web, windows, linux, macos. So gate 4 can use `flutter build web -t lib/gallery_main.dart` (web is already configured).
- `packages/shared_core/lib/` currently contains ONLY `services/` (4 files). `shared_core/pubspec.yaml` has NO `flutter:` section, NO `analysis_options.yaml`, NO `dev_dependencies`, NO `test/` dir. We must add a `flutter:` section (for fonts), `dev_dependencies` (flutter_test, flutter_lints), and an `analysis_options.yaml`.
- `apps/user_app/lib/` has `main.dart` (the live app — do NOT change behavior) and an empty `screens/`. `apps/user_app/test/` has `widget_test.dart` (a non-test placeholder that just calls `runApp`) and `compliance_analysis_test.dart`. We ADD a new test file; we do not need to touch the placeholder.
- Business models in `shared_core/lib/services/compliance_analysis.dart`: `ComplianceAnalysis` (productName, mrp, netQuantity, manufacturer, address, packingDate, customerCare, missingInformation: List<String>, possibleIssues: List<ComplianceIssue>, plus getters isCompliant) and `ComplianceIssue` (title, description, severity, ruleNumbers, ruleTitles, legalBasis?, ocrEvidence?, verificationStatus). There is also an enum `LegalVerificationStatus`. **These files are PRESERVED byte-for-byte**; the gallery mock data merely CONSTRUCTS these models, it does not modify the files.
- Icon package reality: the original `lucide_icons` package (lucide-icons/lucide-flutter) is archived/not actively maintained. `lucide_icons_flutter` (v1.14, May 2026) is actively maintained. **Decision below.**

---

## Design decisions (rationale, 1–2 sentences each)

1. **Tokens via `ThemeExtension<VeriqooTokens>`** attached to `ThemeData.extensions`, with two complete instances (dark primary, light). Rationale: lets any widget read `Theme.of(context).extension<VeriqooTokens>()!` and switch themes with zero branching in widgets; it is the idiomatic Flutter mechanism and needs no state-management package (satisfies the "no riverpod/bloc" constraint).
2. **Fonts: bundle TTFs in `shared_core`, referenced via the `packages/shared_core/<Family>` prefix.** Rationale: offline-first is the stated goal; `google_fonts` fetches on first run (needs network once) and would fall back to Roboto in the offline widget test, failing gate 6. Download the SIL OFL files from the `google/fonts` GitHub raw endpoints (most reliable static host): Inter as the variable TTF `Inter[opsz,wght].ttf` (Flutter 3.x resolves weights from a variable axis), IBM Plex Mono as static `IBMPlexMono-Regular.ttf` + `IBMPlexMono-Medium.ttf`. **Fallback (only if downloads fail in the environment)**: switch the whole strategy to the `google_fonts` package added via `flutter pub add`, leave a `// TODO(fonts): bundle OFL TTFs offline` and still render Inter + IBM Plex Mono. Do not mix the two strategies.
3. **Icons: `lucide_icons_flutter` (primary).** Rationale: it is the maintained Lucide fork (`lucide_icons` is archived); the raw package is imported ONLY inside `VeriqooIcons`, so a later swap is a one-file change. **Fallback (only if it fails to resolve)**: `phosphor_flutter`, still wrapped by `VeriqooIcons`. Resolve the version with `flutter pub add` (no hand-picked numbers).
4. **Design-system deps live in `shared_core/pubspec.yaml`** so both apps inherit them; `user_app` keeps its existing path dependency on `shared_core`. The gallery entrypoint and the widget test live in `user_app` (where `flutter_test` is already configured and the web build target exists); the `DesignGallery` screen itself lives in `shared_core` (exported) so it is reusable and testable.
5. **DesignGallery location**: `shared_core/lib/design_system/gallery/design_gallery.dart`, exported from the barrel. `apps/user_app/lib/gallery_main.dart` is a thin entrypoint: its own `main()` → `runApp(MaterialApp(theme: VeriqooTheme.dark, darkTheme/light, home: DesignGallery()))`. This keeps `main.dart` untouched.
6. **WCAG / exact-token tension**: the task mandates EXACT token hex values. Computed contrast on dark bg `#0A0A0A`: `textSecondary #A0A0A0` = **7.57:1** (passes AA & AAA); `textTertiary #5E5E5E` = **3.05:1** (passes AA for large text / UI components ≥3:1, FAILS AA 4.5:1 for normal body text). Light bg `#F5F5F2`: `textSecondary #5E5E5E` = **5.93:1** (AA pass); `textTertiary #A0A0A0` = **2.39:1** (fails even large-text AA). **Decision**: keep the exact hex values (explicit mandate wins over the "bump" instruction) and MITIGATE by usage rule — `textTertiary` is restricted to large/decorative/disabled/meta use only, never essential body text; document this in `veriqoo_tokens.dart` doc comments and apply it in the gallery. This is a deliberate assumption; flagged in §Gaps.
7. **Reduced motion** is centralized in one helper (`VeriqooMotion.reduceMotion(context)`) reading `MediaQuery.disableAnimations` OR the platform accessibility reduce-motion flag; all painters/animations call it and resolve to a static end state when true.

---

## Token reference (encode these EXACT values)

### Primitive ramp — `veriqoo_colors.dart` (`VeriqooColors`, all `static const Color`)
`black #000000`, `deepBlack #0A0A0A`, `charcoal #111111`, `graphite #181818`, `borderStrongDark #2A2A2A`, `midGrey #5E5E5E`, `lightGrey #A0A0A0`, `borderGrey #D5D5D5`, `offWhite #F5F5F2`, `white #FFFFFF`. **No green, no accent anywhere.**

### Semantic token sets — `VeriqooTokens` ThemeExtension (two instances)
| token | DARK (primary) | LIGHT |
|---|---|---|
| bg | #0A0A0A | #F5F5F2 |
| bgTrue (hero/loading/scanner) | #000000 | #FFFFFF |
| surface | #111111 | #FFFFFF |
| surfaceRaised (nav/sheets/modals) | #181818 | #FFFFFF |
| borderHairline | white @ 10% opacity | #D5D5D5 |
| borderStrong | #2A2A2A | #A0A0A0 |
| textPrimary | #F5F5F2 | #0A0A0A |
| textSecondary | #A0A0A0 | #5E5E5E |
| textTertiary | #5E5E5E | #A0A0A0 |
| inverseBg | #FFFFFF | #0A0A0A |
| inverseText | #0A0A0A | #FFFFFF |

`VeriqooTokens` must implement `copyWith` and `lerp` (ThemeExtension contract) and expose `brightness`. Also expose the single soft-shadow token and a single restrained translucent-surface token here (or in `veriqoo_elevation.dart`).

### Typography — `VeriqooType` (`veriqoo_typography.dart`)
Font families (bundled, referenced with package prefix): `kInterFamily = 'packages/shared_core/Inter'`, `kMonoFamily = 'packages/shared_core/IBMPlexMono'`. Inter for all text; IBM Plex Mono for numerals/IDs/scores/OCR confidence with `fontFeatures: [FontFeature.tabularFigures()]`.

| style | size | letterSpacing | weight | height | notes |
|---|---|---|---|---|---|
| display | 52 | -1.5 | w600 | 1.02 | Inter |
| h1 | 32 | -0.5 | w700 | 1.1 | Inter |
| h2 | 24 | -0.25 | w600 | 1.2 | Inter |
| h3 | 20 | 0 | w600 | 1.3 | Inter |
| bodyL | 16 | 0 | w400 | 1.5 | Inter |
| body | 14 | 0 | w400 | 1.5 | Inter |
| caption | 13 | 0 | w400 | 1.4 | Inter |
| meta | 11.5 | +0.14em (≈ 1.61 px) | w500 | 1.2 | Inter, UPPERCASE (apply via text transform at call sites) |
| mono | 13 | 0 | w400 | — | IBM Plex Mono, tabular figures |

`letterSpacing` in Flutter is in logical pixels: meta `0.14em` at 11.5 px → `letterSpacing: 11.5 * 0.14 = 1.61`. Each style is a `static const TextStyle` with explicit `color` left null (color comes from theme) OR provide `.withColor(Color)` helpers; prefer leaving color to be applied by widgets from tokens.

### Spacing — `VeriqooSpacing` (`veriqoo_spacing.dart`), `static const double`
`s4=4, s8=8, s12=12, s16=16, s24=24, s32=32, s48=48, s64=64, s80=80, s96=96`. All padding/gaps in the system use these; no arbitrary values.

### Radius — `VeriqooRadius` (`veriqoo_radius.dart`), `static const double` + `BorderRadius` helpers
`none=0` (reports/tables/technical panels/status chips), `sm=6` (inputs/buttons/nav items), `md=10` (sheets/small modals), `lg=20` (hero/auth surfaces only). Do NOT round everything.

### Elevation — `veriqoo_elevation.dart`
Default = hairline borders, not shadows. Exactly ONE soft shadow token (`VeriqooElevation.softShadow` — a `List<BoxShadow>`) reserved for floating nav + modals. One restrained translucent surface token allowed (e.g. `translucentSurface`), used sparingly.

### Motion — `VeriqooMotion` (`veriqoo_motion.dart`)
Durations: `fast=160ms`, `base=240ms`, `slow=320ms`, `cinematic=700ms`. Curves: `enter = Curves.easeOutCubic`, `move = Curves.easeInOutCubic`, `press =` a gentle spring WITHOUT overshoot (use a critically/over-damped `SpringDescription` so it settles without crossing the target, or `Curves.easeOutCubic` as the no-overshoot stand-in). `reduceMotion(BuildContext) → bool` honoring `MediaQuery.of(context).disableAnimations` and the platform reduce-motion accessibility flag; when true, all loops/sweeps resolve to a static end state.

---

## File manifest (every file to create, with purpose)

Barrel + theme (`packages/shared_core/lib/design_system/`):
- `design_system.dart` — single barrel; exports every public token/type/component/painter/motif/gallery file.
- `theme/veriqoo_colors.dart` — primitive ramp constants.
- `theme/veriqoo_tokens.dart` — `VeriqooTokens` ThemeExtension (dark + light), copyWith/lerp, usage doc comments incl. WCAG notes.
- `theme/veriqoo_typography.dart` — `VeriqooType` text styles + family constants + tabular-figure mono.
- `theme/veriqoo_spacing.dart` — spacing scale.
- `theme/veriqoo_radius.dart` — radius tokens + BorderRadius helpers.
- `theme/veriqoo_elevation.dart` — soft-shadow + translucent-surface tokens.
- `theme/veriqoo_motion.dart` — durations/curves + `reduceMotion`.
- `theme/veriqoo_theme.dart` — `VeriqooTheme.dark` / `VeriqooTheme.light` building `ThemeData` (fontFamily=Inter, extensions:[tokens], TextTheme from VeriqooType, scaffoldBackground from tokens, no Material elevation tints).
- `foundations/veriqoo_icons.dart` — `VeriqooIcons` facade mapping named getters (home, scan, history, profile, back, check, close, search, alert, camera, upload, etc.) to the chosen Lucide package. Only file importing the raw icon package.

Components (`packages/shared_core/lib/design_system/components/`), one file each:
- `veriqoo_button.dart` — `VeriqooButton` (primary=inverse fill, secondary=hairline outline, ghost=text-only; size enum; disabled + loading; press scale-down micro-interaction using `VeriqooMotion.press`, no overshoot; min 44×44 target; Semantics label).
- `veriqoo_icon_button.dart` — `VeriqooIconButton` (44×44 min, Semantics label, hairline/ghost variants).
- `veriqoo_text_field.dart` — `VeriqooTextField` (animated focus underline via AnimatedContainer/motion, label, error state, hairline default border).
- `veriqoo_app_bar.dart` — `VeriqooAppBar` implements `PreferredSizeWidget` (left back / center title / right action; back auto-hidden when `Navigator.canPop(context) == false`).
- `veriqoo_navigation_bar.dart` — `VeriqooNavigationBar` (floating, uses softShadow token; four destinations Home/Scan/History/Profile; Scan visually emphasized; subtle active indicator; monochrome line icons via VeriqooIcons; radius sm).
- `veriqoo_section_header.dart` — `VeriqooSectionHeader` (meta/uppercase label + optional trailing action).
- `veriqoo_divider.dart` — `VeriqooDivider` (hairline using borderHairline token).
- `veriqoo_status.dart` — `VeriqooStatus` + `VeriqooStatusKind` enum (the four encodings below). Radius none for the chip.
- `veriqoo_score.dart` — `VeriqooScore` (custom monochrome radial ring painter + count-up animation to e.g. 87; shows `87/100` in mono tabular; respects reduceMotion → jump to final).
- `veriqoo_inspection_card.dart` — `VeriqooInspectionCard` (editorial LEDGER ROW: inspection ID (mono), timestamp (mono), product (body), score, status chip, hairline separators; radius none; NOT a floating rounded card).
- `veriqoo_bottom_sheet.dart` — `VeriqooBottomSheet` (surfaceRaised, radius md top corners, static `show` helper using showModalBottomSheet).
- `veriqoo_modal.dart` — `VeriqooModal` (surfaceRaised, radius md, softShadow, static `show` using showDialog).
- `veriqoo_loading.dart` — `VeriqooLoading` (uses the shared Verification-Scan motif widget).
- `veriqoo_empty_state.dart` — `VeriqooEmptyState` (monoline icon + title + body + optional action).
- `veriqoo_error_state.dart` — `VeriqooErrorState` (same skeleton, error framing, retry action).
- `veriqoo_scanner_overlay.dart` — `VeriqooScannerOverlay` (four precise corner markers + thin scanning line + sample OCR detection boxes with tiny field labels; built on the shared motif).

Painters (`packages/shared_core/lib/design_system/painters/`), lightweight `CustomPainter`s, low opacity, repaint-throttled, pause offscreen / on reduced-motion, sit BELOW content:
- `inspection_grid.dart` (`InspectionGrid`), `scanning_line.dart` (`ScanningLine`), `ocr_overlay.dart` (`OCROverlay`), `data_ticker.dart` (`DataTicker` — ticks tiny labels "OCR 98.2%", "FIELD DETECTED", "VERIFYING", "DECLARATION FOUND"), `product_outline.dart` (`ProductOutline`), `verification_pulse.dart` (`VerificationPulse`), `compliance_markers.dart` (`ComplianceMarkers`), `technical_coordinates.dart` (`TechnicalCoordinates`).
- Shared base: a small `_PausablePainter`/ticker mixin or helper so each painter stops its `Ticker`/`shouldRepaint` when offscreen (use `VisibilityDetector`-free approach: a `TickerMode`/`AnimatedBuilder` gated by an `enabled` flag passed by the host, plus reduceMotion check).

Motif (`packages/shared_core/lib/design_system/motif/`):
- `verification_scan.dart` — `VerificationScan` reusable widget + its painter: a 1–2px luminous hairline sweeping across structured product data, four corner markers "locking", OCR boxes fading in staggered ~40ms. Consumed by `VeriqooLoading` and `VeriqooScannerOverlay`. Reduced-motion → final locked state, no sweep.

Gallery (`packages/shared_core/lib/design_system/gallery/`):
- `mock_data.dart` — realistic Indian mock data (see §Gallery). Builds real `ComplianceAnalysis` / `ComplianceIssue` instances (imported from `package:shared_core/services/compliance_analysis.dart`).
- `design_gallery.dart` — `DesignGallery` stateful screen with a dark/light toggle (local `setState`, no state package) that re-themes via an inner `Theme`/`MaterialApp` wrapper.

Entrypoint + test (`apps/user_app/`):
- `lib/gallery_main.dart` — `main()` → `runApp` of a `MaterialApp` using `VeriqooTheme.dark`/`.light` with `home: DesignGallery()`. Does NOT import or touch `main.dart`.
- `test/gallery_test.dart` — widget test (gate 5).

Config:
- `packages/shared_core/pubspec.yaml` — add icon dep (+ google_fonts only if fallback), `dev_dependencies` (flutter_test, flutter_lints), and `flutter:` section with `uses-material-design: true` + bundled `fonts:` + the OFL/font assets.
- `packages/shared_core/analysis_options.yaml` — `include: package:flutter_lints/flutter.yaml` with the same `analyzer.exclude` style as user_app.
- `packages/shared_core/assets/fonts/` — `Inter[opsz,wght].ttf`, `IBMPlexMono-Regular.ttf`, `IBMPlexMono-Medium.ttf`, `Inter-OFL.txt`, `IBMPlexMono-OFL.txt`.

### Status encodings (zero color — shape + glyph + label) — `VeriqooStatus`
- **VERIFIED** → solid FILLED square + check glyph (VeriqooIcons check) + label `"VERIFIED"`.
- **FLAG** → diagonal-HATCH outlined square (CustomPainter hatch) + label `"FLAG"`.
- **MISSING** → DASHED outlined square (dashed border painter) + label `"NOT DETECTED"`.
- **VIOLATION** → INVERTED solid high-contrast block (inverseBg fill, inverseText glyph) + label `"VIOLATION"`.
All chips: radius none, meta/uppercase label, Semantics label = the status word so it is announced without relying on color.

---

## Design Gallery contents (must render in BOTH dark and light)
Color swatches (both schemes side by side) · full type ramp (display→mono) · spacing scale samples · radius samples (none/sm/md/lg) · all four status chips · every `VeriqooButton` variant × state (primary/secondary/ghost × default/disabled/loading, all sizes) · text fields (default/focus/error) · `VeriqooAppBar` · `VeriqooNavigationBar` · `VeriqooScore` (animated count-up) · several `VeriqooInspectionCard` rows · `VeriqooLoading` · empty + error states · `VeriqooScannerOverlay` · each background painter in a bounded preview box. Dark/light toggle in the app bar action.

**Mock data (`mock_data.dart`)**: product "Organic Wheat Biscuits", MRP `Rs.120`, Net Quantity `200 g`, manufacturer "ABC Foods Pvt. Ltd.", inspection ID `VRQ-20261004-0182`, OCR confidence `OCR 98.2%`, scores like `87/100`. Provide a small list of `ComplianceAnalysis` rows with mixed statuses (verified / flag / missing / violation) for the inspection-card list.

---

## Ordered implementation items (each leaves the repo buildable)

- [ ] 1. Add design-system dependencies and font/analysis config to `shared_core`, then resolve.
      Add icon dep via `flutter pub add lucide_icons_flutter` (run in `packages/shared_core`); if it fails to resolve, `flutter pub add phosphor_flutter` instead (record which in findings). Download the OFL TTFs into `packages/shared_core/assets/fonts/` with `Invoke-WebRequest` from the `google/fonts` raw host:
      Inter → `https://raw.githubusercontent.com/google/fonts/main/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf` (save as `Inter[opsz,wght].ttf`); Inter OFL → `.../ofl/inter/OFL.txt` (save `Inter-OFL.txt`); IBM Plex Mono → `.../ofl/ibmplexmono/IBMPlexMono-Regular.ttf` and `.../ofl/ibmplexmono/IBMPlexMono-Medium.ttf`; IBM Plex Mono OFL → `.../ofl/ibmplexmono/OFL.txt` (save `IBMPlexMono-OFL.txt`). If any download fails, remove the `fonts:` block and `flutter pub add google_fonts` as the fallback (leave a `// TODO(fonts): bundle offline` where VeriqooType/theme sets families). Add to `shared_core/pubspec.yaml`: `dev_dependencies: flutter_test (sdk), flutter_lints: ^5.0.0`; a `flutter:` section with `uses-material-design: true` and the `fonts:` declaration (family `Inter` → variable ttf; family `IBMPlexMono` → Regular w400 + Medium w500). Create `packages/shared_core/analysis_options.yaml` (include `package:flutter_lints/flutter.yaml`).
      Files: `packages/shared_core/pubspec.yaml`, `packages/shared_core/analysis_options.yaml`, `packages/shared_core/assets/fonts/*` (+ `apps/user_app` only if google_fonts fallback must be mirrored — not expected since it inherits).
      Verify: `flutter pub get` succeeds in `packages/shared_core` AND in `apps/user_app` (exit 0, no resolution errors).

- [ ] 2. Create the token/theme layer: colors, tokens extension, typography, spacing, radius, elevation, motion, and the theme builder.
      Encode every value from the Token reference above. `VeriqooTokens` implements `copyWith`+`lerp`; `VeriqooTheme.dark`/`.light` attach it and wire fonts + TextTheme. Add WCAG usage doc comments on `textTertiary`.
      Files: `theme/veriqoo_colors.dart`, `theme/veriqoo_tokens.dart`, `theme/veriqoo_typography.dart`, `theme/veriqoo_spacing.dart`, `theme/veriqoo_radius.dart`, `theme/veriqoo_elevation.dart`, `theme/veriqoo_motion.dart`, `theme/veriqoo_theme.dart`.
      Verify: `flutter analyze` in `packages/shared_core` reports 0 errors.

- [ ] 3. Create the `VeriqooIcons` facade and the barrel `design_system.dart` exporting the theme layer + icons so far.
      Files: `foundations/veriqoo_icons.dart`, `design_system.dart`.
      Verify: `flutter analyze` in `packages/shared_core` → 0 errors; the barrel resolves (no unresolved exports).

- [ ] 4. Create the eight background painters plus the shared pause/reduced-motion helper.
      Low opacity, throttled repaint, pause when disabled/offscreen or reduced-motion. Export from the barrel.
      Files: all 8 files under `painters/` + any shared helper, and barrel export lines in `design_system.dart`.
      Verify: `flutter analyze` in `packages/shared_core` → 0 errors.

- [ ] 5. Create the signature `VerificationScan` motif (widget + painter): hairline sweep, corner-marker lock, staggered ~40ms OCR box fade-in; reduced-motion → static locked end state.
      Files: `motif/verification_scan.dart` + barrel export.
      Verify: `flutter analyze` in `packages/shared_core` → 0 errors.

- [ ] 6. Create the 16 components (one file each) using tokens/type/motion/icons/motif. Implement `VeriqooStatus` with the four shape+glyph+label encodings, `VeriqooScore` with the radial+count-up, `VeriqooInspectionCard` as a hairline ledger row, and `VeriqooAppBar` with auto-hidden back. Ensure 44×44 min targets, Semantics labels, visible focus states. Export all from the barrel.
      Files: all 16 files under `components/` + barrel export lines.
      Verify: `flutter analyze` in `packages/shared_core` → 0 errors.

- [ ] 7. Create the gallery mock data and `DesignGallery` screen (dark/light toggle, all sections from §Gallery). Export both from the barrel.
      Files: `gallery/mock_data.dart`, `gallery/design_gallery.dart` + barrel export.
      Verify: `flutter analyze` in `packages/shared_core` → 0 errors.

- [ ] 8. Create the gallery entrypoint in `user_app` (separate from `main.dart`).
      `main()` wraps `DesignGallery` in a `MaterialApp` using `VeriqooTheme.dark` (theme) + `.light` (theme/darkTheme as the toggle drives it). Import only `package:shared_core/design_system/design_system.dart`.
      Files: `apps/user_app/lib/gallery_main.dart`.
      Verify: `flutter analyze` in `apps/user_app` → 0 errors; `flutter build web -t lib/gallery_main.dart` (run in `apps/user_app`) completes successfully (record the exact command that passed; if web were unavailable, fall back to `flutter build windows` / `flutter build apk --debug`).

- [ ] 9. Add the widget test that pumps `DesignGallery` and at least `VeriqooButton`, `VeriqooScore`, `VeriqooStatus`, `VeriqooScannerOverlay`, asserting no exceptions (use `tester.pumpWidget` wrapped in `MaterialApp(theme: VeriqooTheme.dark)`, `await tester.pump(const Duration(seconds: 1))` to let animations settle, and `expect(tester.takeException(), isNull)`).
      Files: `apps/user_app/test/gallery_test.dart`.
      Verify: `flutter test` in `apps/user_app` passes (all tests green).

- [ ] 10. Final verification sweep + font-render confirmation.
      Run, in order: (1) `flutter --version` (toolchain present); (2) `flutter pub get` in `packages/shared_core` and `apps/user_app`; (3) `flutter analyze` in both (0 errors, minimal warnings); (4) `flutter build web -t lib/gallery_main.dart` in `apps/user_app`; (5) `flutter test` in `apps/user_app`. Confirm Inter + IBM Plex Mono resolve, not Roboto: assert the bundled font assets exist, that `VeriqooType` families are `packages/shared_core/Inter` / `packages/shared_core/IBMPlexMono` (or, in the google_fonts fallback, that GoogleFonts.inter/ibmPlexMono are wired) and that the web build's `FontManifest.json` / `assets/packages/shared_core/assets/fonts/` lists the TTFs. Record the exact passing commands.
      Files: none (verification only).
      Verify: all five gates pass; preserved `shared_core/lib/services/` files are byte-identical (confirm no diff under that dir).

---

## Hard preservation / constraint checklist (reviewer gate)
- `packages/shared_core/lib/services/*` byte-identical (no edits). ✔ check with git diff on that path.
- `apps/user_app/lib/main.dart` behavior unchanged; app still compiles. Gallery is a separate `gallery_main.dart`. ✔
- No `go_router`, no riverpod/bloc added; components depend on no state-management lib. ✔
- Monochrome only; zero green; no gradients; no glassmorphism (one restrained translucent token ok); hairlines over shadows (single soft-shadow token only for floating nav + modals); radius strictly per tokens. ✔
- Full reduced-motion support; 44×44 targets; Semantics labels; visible focus. ✔
- Dark AND light both complete. ✔
- Fonts render Inter + IBM Plex Mono (not Roboto). ✔

---

## Gaps / assumptions (flagged, reasonable defaults taken)
1. **WCAG vs exact tokens**: kept exact hex (explicit mandate), mitigated via usage restriction on `textTertiary` (3.05:1 dark / 2.39:1 light — large/decorative/disabled only). If the reviewer requires AA for tertiary body text, that needs a token-value change the task currently forbids. Decision: keep exact + restrict usage.
2. **Font bundling vs google_fonts**: primary = bundle TTFs (offline-first + passes offline test); fallback = google_fonts if downloads fail. Explicit trigger condition, not left open.
3. **Icon package**: `lucide_icons_flutter` chosen over archived `lucide_icons`; `phosphor_flutter` fallback. Isolated behind `VeriqooIcons`.
4. **Inter variable font**: bundled as a single variable TTF; Flutter 3.47 resolves `fontWeight` from the `wght` axis. If a specific weight renders wrong, substitute static Inter TTFs (Regular/Medium/SemiBold/Bold) from the same `google/fonts` dir.
