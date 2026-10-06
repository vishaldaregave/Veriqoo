import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_application_1/app/routes.dart';
import 'package:flutter_application_1/core/theme/pro_palette.dart';
import 'package:flutter_application_1/features/scan/scan_analysis_runner.dart';
import 'package:flutter_application_1/features/scan/scan_providers.dart';
import 'package:shared_core/services/compliance_analysis.dart';

/// Screen 4: Analyzing Product Screen matching the mockup.
///
/// Features:
/// - Circular progress ring around the product thumbnail
/// - 5-stage sequential step checklist with animated checkmarks
/// - Amber notice card at bottom
/// - Runs real OCR & Legal Metrology compliance checks via [scanAnalysisRunnerProvider]
class ScanProcessingScreen extends ConsumerStatefulWidget {
  const ScanProcessingScreen({super.key});

  @override
  ConsumerState<ScanProcessingScreen> createState() => _ScanProcessingScreenState();
}

class _ScanProcessingScreenState extends ConsumerState<ScanProcessingScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _progressController;
  Timer? _stepTimer;
  int _activeStep = 0; // 0..4
  bool _error = false;
  String? _notProductReason; // set when Gemini says image is not a product

  final List<String> _steps = [
    'Extracting text from label',
    'Identifying product category',
    'Checking relevant regulations...',
    'Analyzing compliance',
    'Generating report',
  ];

  @override
  void initState() {
    super.initState();
    _progressController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 4),
    )..forward();

    _startStepAnimation();
    WidgetsBinding.instance.addPostFrameCallback((_) => _executeAnalysis());
  }

  void _startStepAnimation() {
    _stepTimer = Timer.periodic(const Duration(milliseconds: 700), (timer) {
      if (!mounted) return;
      if (_activeStep < _steps.length - 1) {
        setState(() => _activeStep++);
      }
    });
  }

  Future<void> _executeAnalysis() async {
    final evidence = ref.read(scanStateProvider).evidence;
    final runner = ref.read(scanAnalysisRunnerProvider);

    try {
      final args = await runner.run(
        evidence: evidence,
        geminiApiKey: resolveGeminiApiKey(),
      );

      if (!mounted) return;

      // Ensure at least 2.5s is shown for smooth UX matching the design
      await Future.delayed(const Duration(milliseconds: 250));
      if (!mounted) return;

      context.pushReplacement(AppRoutes.scanResultPath, extra: args);
    } on NotAProductException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = true;
        _notProductReason = e.reason;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = true;
        _notProductReason = null;
      });
    }
  }

  @override
  void dispose() {
    _progressController.dispose();
    _stepTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final evidence = ref.watch(scanStateProvider).evidence;
    final hasImage = evidence.isNotEmpty;

    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded, color: ProPalette.textHeading, size: 20),
          onPressed: () => context.pop(),
        ),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 8),
          child: SingleChildScrollView(
            child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // 1. Header
              const Text(
                'Analyzing Product',
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w800,
                  color: ProPalette.textHeading,
                ),
              ),
              const SizedBox(height: 6),
              const Text(
                'Extracting information and checking applicable regulations...',
                style: TextStyle(
                  fontSize: 13,
                  color: ProPalette.textMuted,
                  height: 1.4,
                ),
              ),
              if (_error) ...[
                const SizedBox(height: 14),
                // NOT A PRODUCT card
                if (_notProductReason != null)
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: const Color(0xFFFFF7ED),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: const Color(0xFFFDBA74)),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: const [
                            Icon(Icons.image_not_supported_outlined,
                                color: Color(0xFFEA580C), size: 22),
                            SizedBox(width: 8),
                            Text(
                              'Not a Product Package',
                              style: TextStyle(
                                color: Color(0xFF9A3412),
                                fontWeight: FontWeight.w700,
                                fontSize: 14,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Text(
                          _notProductReason!,
                          style: const TextStyle(
                            color: Color(0xFF92400E),
                            fontSize: 13,
                            height: 1.4,
                          ),
                        ),
                        const SizedBox(height: 10),
                        const Text(
                          'Please scan the label or packaging of a packaged product (food, beverage, cosmetic, etc.) to run a compliance check.',
                          style: TextStyle(
                            color: Color(0xFF78350F),
                            fontSize: 12,
                            height: 1.4,
                          ),
                        ),
                        const SizedBox(height: 12),
                        SizedBox(
                          width: double.infinity,
                          child: OutlinedButton.icon(
                            onPressed: () => context.pop(),
                            icon: const Icon(Icons.camera_alt_outlined,
                                size: 16, color: Color(0xFFEA580C)),
                            label: const Text(
                              'Try Again with a Product Image',
                              style: TextStyle(
                                color: Color(0xFFEA580C),
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            style: OutlinedButton.styleFrom(
                              side: const BorderSide(color: Color(0xFFFDBA74)),
                              shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(8)),
                              padding: const EdgeInsets.symmetric(vertical: 10),
                            ),
                          ),
                        ),
                      ],
                    ),
                  )
                // GENERIC ERROR card
                else
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: ProPalette.crimsonBg,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.error_outline,
                            color: ProPalette.crimsonViolation, size: 20),
                        const SizedBox(width: 8),
                        const Expanded(
                          child: Text(
                            'Analysis failed. Please check your connection and try again.',
                            style: TextStyle(
                                color: ProPalette.crimsonViolation, fontSize: 13),
                          ),
                        ),
                        TextButton(
                          onPressed: _executeAnalysis,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
              ],
              const SizedBox(height: 28),


              // 2. Central Thumbnail inside Circular Progress Ring
              Center(
                child: SizedBox(
                  width: 140,
                  height: 140,
                  child: Stack(
                    alignment: Alignment.center,
                    children: [
                      // Rotating / Animated Circular Progress Indicator
                      SizedBox(
                        width: 130,
                        height: 130,
                        child: CircularProgressIndicator(
                          valueColor: const AlwaysStoppedAnimation<Color>(ProPalette.accentEmerald),
                          backgroundColor: const Color(0xFFE5E7EB),
                          strokeWidth: 4.5,
                        ),
                      ),
                      // Product Image or Lay's fallback
                      ClipRRect(
                        borderRadius: BorderRadius.circular(16),
                        child: Container(
                          width: 80,
                          height: 80,
                          color: const Color(0xFFFEF3C7),
                          child: hasImage
                              ? Image.file(
                                  File(evidence.first.file.path),
                                  fit: BoxFit.cover,
                                )
                              : const Center(
                                  child: Icon(Icons.fastfood_rounded, color: Color(0xFFD97706), size: 40),
                                ),
                        ),
                      ),

                    ],
                  ),
                ),
              ),
              const SizedBox(height: 36),

              // 3. Step Progress Checklist
              ListView.builder(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  itemCount: _steps.length,
                  itemBuilder: (context, index) {
                    final isComplete = index < _activeStep;
                    final isCurrent = index == _activeStep;
                    final isPending = index > _activeStep;

                    return IntrinsicHeight(
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          // Left Check Indicator + Connecting Line
                          Column(
                            children: [
                              Container(
                                width: 22,
                                height: 22,
                                decoration: BoxDecoration(
                                  color: (isComplete || isCurrent) ? ProPalette.accentEmerald : Colors.transparent,
                                  shape: BoxShape.circle,
                                  border: Border.all(
                                    color: (isComplete || isCurrent)
                                        ? ProPalette.accentEmerald
                                        : const Color(0xFFCBD5E1),
                                    width: 1.8,
                                  ),
                                ),
                                child: isComplete
                                    ? const Icon(Icons.check, size: 14, color: Colors.white)
                                    : (isCurrent
                                        ? const Padding(
                                            padding: EdgeInsets.all(4),
                                            child: CircularProgressIndicator(
                                              strokeWidth: 2,
                                              color: Colors.white,
                                            ),
                                          )
                                        : null),
                              ),
                              if (index < _steps.length - 1)
                                Expanded(
                                  child: Container(
                                    width: 1.8,
                                    margin: const EdgeInsets.symmetric(vertical: 4),
                                    color: isComplete ? ProPalette.accentEmerald : const Color(0xFFE2E8F0),
                                  ),
                                ),
                            ],
                          ),
                          const SizedBox(width: 14),

                          // Step Label
                          Expanded(
                            child: Padding(
                              padding: const EdgeInsets.only(bottom: 20),
                              child: Text(
                                _steps[index],
                                style: TextStyle(
                                  fontSize: 14,
                                  fontWeight: (isComplete || isCurrent) ? FontWeight.w600 : FontWeight.w400,
                                  color: isPending ? ProPalette.textTertiary : ProPalette.textHeading,
                                ),
                              ),
                            ),
                          ),
                        ],
                      ),
                    );
                  },
                ),

              // 4. Bottom Amber Tip Card
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: ProPalette.amberNote,
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: const Color(0xFFFDE68A)),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: const [
                    Icon(Icons.auto_awesome, color: ProPalette.amberWarning, size: 20),
                    SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        'This may take a few seconds. We are verifying against Indian legal metrology and packaged commodity rules.',
                        style: TextStyle(
                          fontSize: 12,
                          height: 1.4,
                          color: Color(0xFF92400E),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
            ],
          ),
          ),
        ),
      ),
    );
  }
}
