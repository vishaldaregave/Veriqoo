import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../core/theme/pro_palette.dart';
import 'instagram_ad_service.dart';

/// Screen for the Social & Instagram Ad Clickbait & Deceptive Claim Detector.
///
/// Integrates with the Veriqoo CP verification engine to analyze Instagram
/// posts, ads, and reels in real-time for clickbait hooks, artificial discounts,
/// micro-price bait, fake scarcity, and statutory compliance violations.
class AdDetectorScreen extends StatefulWidget {
  const AdDetectorScreen({super.key});

  @override
  State<AdDetectorScreen> createState() => _AdDetectorScreenState();
}

class _AdDetectorScreenState extends State<AdDetectorScreen> {
  final TextEditingController _urlController = TextEditingController();
  final TextEditingController _contextController = TextEditingController();

  bool _isLoading = false;
  bool _isBackendConnected = false;
  InstagramAdResult? _currentResult;
  final List<InstagramAdResult> _history = [];

  // Sample ads for instant testing
  final List<Map<String, String>> _samplePresets = [
    {
      'label': '🥚 Instamart ₹1 Deal',
      'url': 'https://www.instagram.com/p/DdtozWUM5Dh/?stkn=MTgycXoxazUwYXFh',
      'context': 'Pick any breakfast favourite at ₹1 and get free delivery too! 🥚🍞🥛🛵',
    },
    {
      'label': '⌚ Swiss Replica (98% OFF)',
      'url': 'https://www.instagram.com/reel/C8XYZ12345/',
      'context': 'Luxury Chronograph - Direct Factory Outlet ₹85,000 now ₹1,499 (98% OFF) ending tonight!',
    },
    {
      'label': '🌿 Miracle Hair Regrowth',
      'url': 'https://www.instagram.com/reel/DB987654321/',
      'context': 'Stops Baldness & Regrows Full Hair in 48 Hours! Doctor recommended 100% organic ₹4,999 now ₹299',
    },
  ];

  @override
  void initState() {
    super.initState();
    _checkBackendHealth();
  }

  @override
  void dispose() {
    _urlController.dispose();
    _contextController.dispose();
    super.dispose();
  }

  Future<void> _checkBackendHealth() async {
    final ok = await InstagramAdService.checkHealth();
    if (mounted) {
      setState(() {
        _isBackendConnected = ok;
      });
    }
  }

  Future<void> _verifyAd({String? explicitUrl, String? explicitContext}) async {
    final url = explicitUrl ?? _urlController.text.trim();
    final contextText = explicitContext ?? _contextController.text.trim();

    if (url.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please enter or paste an Instagram post/reel link.'),
          backgroundColor: ProPalette.crimsonViolation,
        ),
      );
      return;
    }

    setState(() {
      _isLoading = true;
    });

    try {
      final result = await InstagramAdService.verifyAd(
        url: url,
        contextText: contextText.isNotEmpty ? contextText : null,
      );

      if (mounted) {
        setState(() {
          _currentResult = result;
          // Add to top of history if not already present
          if (!_history.any((item) => item.url == result.url)) {
            _history.insert(0, result);
          }
        });
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Verification error: '),
            backgroundColor: ProPalette.crimsonViolation,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _pasteFromClipboard() async {
    final data = await Clipboard.getData(Clipboard.kTextPlain);
    if (data != null && data.text != null && data.text!.isNotEmpty) {
      setState(() {
        _urlController.text = data.text!.trim();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Instagram Ad Shield'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Re-check Backend Connection',
            onPressed: _checkBackendHealth,
          ),
          IconButton(
            icon: const Icon(Icons.info_outline),
            tooltip: 'How the Shield Works',
            onPressed: () => _showExplanationDialog(context),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        children: [
          // 1. Guard & Backend Connectivity Status
          _buildBackendStatusCard(isDark),

          const SizedBox(height: 16),

          // 2. Interactive URL Input Card
          _buildInputCard(isDark),

          const SizedBox(height: 16),

          // 3. Quick Sample Presets
          _buildSampleChips(isDark),

          const SizedBox(height: 20),

          // 4. Live Verification Result
          if (_isLoading)
            _buildLoadingCard(isDark)
          else if (_currentResult != null)
            _buildResultCard(isDark, _currentResult!)
          else
            _buildEmptyStateCard(isDark),

          const SizedBox(height: 24),

          // 5. Verification History
          if (_history.isNotEmpty) _buildHistorySection(isDark),

          const SizedBox(height: 32),
        ],
      ),
    );
  }

  Widget _buildBackendStatusCard(bool isDark) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: _isBackendConnected
            ? ProPalette.emeraldBg.withValues(alpha: isDark ? 0.2 : 0.7)
            : ProPalette.amberBg.withValues(alpha: isDark ? 0.2 : 0.7),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: _isBackendConnected ? ProPalette.emeraldVerified : ProPalette.amberWarning,
          width: 1,
        ),
      ),
      child: Row(
        children: [
          Icon(
            _isBackendConnected ? Icons.check_circle : Icons.offline_bolt_outlined,
            color: _isBackendConnected ? ProPalette.emeraldText : ProPalette.amberWarning,
            size: 20,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _isBackendConnected
                      ? 'CP Verification Engine Online'
                      : 'CP Standalone Heuristics Active',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 13,
                    color: _isBackendConnected ? ProPalette.emeraldText : ProPalette.amberWarning,
                  ),
                ),
                Text(
                  _isBackendConnected
                      ? 'Connected to local port 5050 for deep web scraping & OCR analysis.'
                      : 'Operating on fast smart heuristics. Run  npm run api in CP for live scraping.',
                  style: TextStyle(
                    fontSize: 11,
                    color: isDark ? Colors.white70 : Colors.black87,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInputCard(bool isDark) {
    return Container(
      decoration: ProPalette.cardDecoration(context, elevated: true),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.link, color: ProPalette.electricBlue, size: 20),
              const SizedBox(width: 8),
              const Text(
                'Audit Instagram Ad or Reel',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
              ),
              const Spacer(),
              TextButton.icon(
                onPressed: _pasteFromClipboard,
                icon: const Icon(Icons.content_paste, size: 14),
                label: const Text('Paste', style: TextStyle(fontSize: 12)),
                style: TextButton.styleFrom(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  minimumSize: Size.zero,
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          TextField(
            controller: _urlController,
            decoration: InputDecoration(
              hintText: 'https://www.instagram.com/p/... or /reel/...',
              hintStyle: const TextStyle(fontSize: 13),
              prefixIcon: const Icon(Icons.search, size: 20),
              suffixIcon: _urlController.text.isNotEmpty
                  ? IconButton(
                      icon: const Icon(Icons.clear, size: 18),
                      onPressed: () {
                        setState(() {
                          _urlController.clear();
                        });
                      },
                    )
                  : null,
              contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
            ),
            onChanged: (_) => setState(() {}),
          ),
          const SizedBox(height: 8),
          TextField(
            controller: _contextController,
            decoration: InputDecoration(
              hintText: 'Optional: Paste ad caption, discount claim, or store URL',
              hintStyle: const TextStyle(fontSize: 12),
              prefixIcon: const Icon(Icons.notes, size: 18),
              contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
            ),
          ),
          const SizedBox(height: 14),
          SizedBox(
            width: double.infinity,
            height: 44,
            child: ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: ProPalette.primaryForest,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
              onPressed: _isLoading ? null : () => _verifyAd(),
              icon: _isLoading
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                    )
                  : const Icon(Icons.shield_outlined, size: 20),
              label: Text(
                _isLoading ? 'Analyzing Ad Claims & Clickbait...' : 'Audit Ad Claims & Safety Score',
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSampleChips(bool isDark) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Quick Test Samples:',
          style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: ProPalette.textMuted),
        ),
        const SizedBox(height: 6),
        Wrap(
          spacing: 8,
          runSpacing: 6,
          children: _samplePresets.map((preset) {
            return ActionChip(
              avatar: const Icon(Icons.play_arrow_rounded, size: 16),
              label: Text(preset['label']!, style: const TextStyle(fontSize: 11)),
              onPressed: () {
                _urlController.text = preset['url']!;
                _contextController.text = preset['context']!;
                _verifyAd(explicitUrl: preset['url'], explicitContext: preset['context']);
              },
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildLoadingCard(bool isDark) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: ProPalette.cardDecoration(context, elevated: true),
      child: const Column(
        children: [
          CircularProgressIndicator(color: ProPalette.primaryForest),
          SizedBox(height: 16),
          Text(
            'Auditing Instagram Ad...',
            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
          ),
          SizedBox(height: 6),
          Text(
            '1. Extracting post caption & creator profile\n'
            '2. Scanning ad creative image with OCR\n'
            '3. Detecting clickbait triggers & artificial discounts\n'
            '4. Evaluating CCPA & Metrology legal compliance',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 12, color: ProPalette.textMuted, height: 1.4),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyStateCard(bool isDark) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: ProPalette.cardDecoration(context, elevated: false),
      child: Column(
        children: [
          Icon(Icons.campaign_outlined, size: 48, color: ProPalette.textMuted.withValues(alpha: 0.5)),
          const SizedBox(height: 12),
          const Text(
            'No Ad Audited Yet',
            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
          ),
          const SizedBox(height: 4),
          const Text(
            'Paste any Instagram reel, sponsored story, or post link above to instantly calculate its Safety Score and Clickbait Risk.',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 12, color: ProPalette.textMuted),
          ),
        ],
      ),
    );
  }

  Widget _buildResultCard(bool isDark, InstagramAdResult result) {
    final isSafe = result.safetyScore >= 70;
    final isMedium = result.safetyScore >= 45 && result.safetyScore < 70;
    final scoreColor = isSafe
        ? ProPalette.emeraldVerified
        : isMedium
            ? ProPalette.amberWarning
            : ProPalette.crimsonViolation;

    final clickbaitColor = result.clickbaitLevel == 'LOW'
        ? ProPalette.emeraldVerified
        : result.clickbaitLevel == 'MODERATE'
            ? ProPalette.amberWarning
            : ProPalette.crimsonViolation;

    return Container(
      decoration: ProPalette.cardDecoration(context, accentBorder: scoreColor, elevated: true),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header: Scores
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 64,
                height: 64,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: scoreColor.withValues(alpha: 0.12),
                  border: Border.all(color: scoreColor, width: 2.5),
                ),
                child: Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        '',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w900,
                          color: scoreColor,
                        ),
                      ),
                      const Text(
                        'SAFETY',
                        style: TextStyle(fontSize: 8, fontWeight: FontWeight.bold, letterSpacing: 0.5),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: clickbaitColor.withValues(alpha: 0.15),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(
                            '🎣 Clickbait:  (/100)',
                            style: TextStyle(
                              color: clickbaitColor,
                              fontWeight: FontWeight.bold,
                              fontSize: 11,
                            ),
                          ),
                        ),
                        const Spacer(),
                        Text(
                          result.riskLevel,
                          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: scoreColor),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text(
                      result.productName,
                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'Entity:  () • Price: ',
                      style: const TextStyle(fontSize: 12, color: ProPalette.textMuted),
                    ),
                  ],
                ),
              ),
            ],
          ),

          const SizedBox(height: 14),
          const Divider(height: 1),
          const SizedBox(height: 12),

          // Clickbait & Ad Pressure Flags
          if (result.clickbaitFlags.isNotEmpty || result.pressureSignals.isNotEmpty) ...[
            const Text(
              '📢 Flagged Ad Pressure Tactics:',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: ProPalette.crimsonViolation),
            ),
            const SizedBox(height: 6),
            ...result.clickbaitFlags.map(
              (flag) => Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('⚠️ ', style: TextStyle(fontSize: 12)),
                    Expanded(
                      child: Text(
                        flag,
                        style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            ...result.pressureSignals.map(
              (sig) => Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('📌 ', style: TextStyle(fontSize: 12)),
                    Expanded(
                      child: Text(
                        ':  — ',
                        style: const TextStyle(fontSize: 11, color: ProPalette.textMuted),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 10),
          ],

          // Evidence check pill badges
          Wrap(
            spacing: 6,
            runSpacing: 4,
            children: [
              _buildEvidenceBadge('Instagram', result.evidenceCheck['instagram'] == true),
              _buildEvidenceBadge('Creative Media', result.evidenceCheck['image'] == true),
              _buildEvidenceBadge('Packaging OCR', result.evidenceCheck['ocr'] == true),
              _buildEvidenceBadge('Web Store', result.evidenceCheck['website'] == true),
            ],
          ),

          const SizedBox(height: 12),

          // Recommendation & Advice Box
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: isDark ? const Color(0xFF0F172A) : const Color(0xFFF1F5F9),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: isDark ? Colors.white10 : Colors.black12),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Row(
                  children: [
                    Icon(Icons.gavel, size: 16, color: ProPalette.purpleAct),
                    SizedBox(width: 6),
                    Text(
                      'Consumer Protection Advice',
                      style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  result.recommendation,
                  style: const TextStyle(fontSize: 12, height: 1.3),
                ),
              ],
            ),
          ),

          const SizedBox(height: 14),

          // Fact Check Dossier Action
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              style: OutlinedButton.styleFrom(
                foregroundColor: ProPalette.electricBlue,
                side: const BorderSide(color: ProPalette.electricBlue),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
              onPressed: () => _showFactCheckSheet(context, result),
              icon: const Icon(Icons.assessment_outlined, size: 18),
              label: const Text('View Full Fact-Check Dossier', style: TextStyle(fontSize: 13)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEvidenceBadge(String label, bool isAvailable) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: isAvailable ? ProPalette.emeraldBg : Colors.grey.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            isAvailable ? Icons.check : Icons.close,
            size: 11,
            color: isAvailable ? ProPalette.emeraldText : Colors.grey,
          ),
          const SizedBox(width: 3),
          Text(
            label,
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.bold,
              color: isAvailable ? ProPalette.emeraldText : Colors.grey,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHistorySection(bool isDark) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Recently Intercepted & Audited Ads',
          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
        ),
        const SizedBox(height: 10),
        ..._history.map((ad) {
          final isSafe = ad.safetyScore >= 70;
          final isMed = ad.safetyScore >= 45 && ad.safetyScore < 70;
          final color = isSafe
              ? ProPalette.emeraldVerified
              : isMed
                  ? ProPalette.amberWarning
                  : ProPalette.crimsonViolation;

          return Card(
            margin: const EdgeInsets.only(bottom: 8),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            child: ListTile(
              leading: CircleAvatar(
                backgroundColor: color.withValues(alpha: 0.15),
                child: Text(
                  '',
                  style: TextStyle(fontWeight: FontWeight.bold, color: color, fontSize: 13),
                ),
              ),
              title: Text(
                ad.productName,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
              ),
              subtitle: Text(
                ' •  Clickbait',
                style: const TextStyle(fontSize: 11),
              ),
              trailing: const Icon(Icons.chevron_right, size: 20),
              onTap: () {
                setState(() {
                  _currentResult = ad;
                });
                _showFactCheckSheet(context, ad);
              },
            ),
          );
        }),
      ],
    );
  }

  void _showFactCheckSheet(BuildContext context, InstagramAdResult ad) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) {
        final isDark = Theme.of(ctx).brightness == Brightness.dark;
        return Container(
          decoration: BoxDecoration(
            color: isDark ? ProPalette.darkSurface : ProPalette.lightSurface,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
          ),
          padding: const EdgeInsets.all(20),
          constraints: BoxConstraints(maxHeight: MediaQuery.of(ctx).size.height * 0.85),
          child: ListView(
            shrinkWrap: true,
            children: [
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: Colors.grey.withValues(alpha: 0.4),
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  const Icon(Icons.verified_outlined, color: ProPalette.electricBlue, size: 24),
                  const SizedBox(width: 8),
                  const Text(
                    'Veriqoo Fact-Check Dossier',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                'Dossier ID: ',
                style: const TextStyle(fontSize: 11, color: ProPalette.textMuted),
              ),
              const SizedBox(height: 14),
              Text(
                'Advertised Item: ',
                style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
              ),
              const SizedBox(height: 2),
              Text(
                'Advertiser / Creator:  ()',
                style: const TextStyle(fontSize: 13, color: ProPalette.textMuted),
              ),
              const SizedBox(height: 4),
              Text(
                'Advertised Price: ',
                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 16),
              const Text(
                'Statutory Laws & Advertising Guidelines:',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
              ),
              const SizedBox(height: 6),
              ...ad.laws.map(
                (law) => Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Row(
                    children: [
                      const Icon(Icons.gavel, size: 14, color: ProPalette.purpleAct),
                      const SizedBox(width: 6),
                      Text(law, style: const TextStyle(fontSize: 12)),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
              const Text(
                'Full Verification Findings & Rationale:',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
              ),
              const SizedBox(height: 6),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: isDark ? const Color(0xFF0F172A) : const Color(0xFFF8FAFC),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: isDark ? Colors.white10 : Colors.black12),
                ),
                child: Text(
                  ad.recommendation,
                  style: const TextStyle(fontSize: 12, height: 1.4),
                ),
              ),
              const SizedBox(height: 20),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: ProPalette.primaryForest,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 12),
                  ),
                  onPressed: () => Navigator.of(ctx).pop(),
                  icon: const Icon(Icons.check),
                  label: const Text('Close Dossier'),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  void _showExplanationDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.shield, color: ProPalette.electricBlue),
            SizedBox(width: 8),
            Text('Veriqoo Ad Shield'),
          ],
        ),
        content: const Text(
          'The Veriqoo Instagram Ad Shield inspects social media ads, reels, and stories in real-time.\n\n'
          'It connects to the Veriqoo CP engine to extract creator identity, creative image banners, '
          'and OCR packaging text, automatically detecting:\n'
          '• Micro-price anchors (e.g. ₹1 deals with hidden delivery terms)\n'
          '• Inflated discounts (fabricated reference MRP markups)\n'
          '• Artificial urgency countdowns & fake scarcity\n'
          '• Uncertified health & cosmetic miracle claims\n\n'
          'Audit results are cross-checked against CCPA Misleading Ads Guidelines and Legal Metrology Rules 2011.',
          style: TextStyle(fontSize: 13, height: 1.4),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('Understood'),
          ),
        ],
      ),
    );
  }
}
