import 'dart:async';
import 'dart:math';
import 'package:flutter/material.dart';
import '../../core/theme/pro_palette.dart';

/// Live Consumer Grievance & Compliance Heatmap across India.
///
/// Features:
/// - Real-time blinking compliance impact map of India (Red: High Violations -> Green: High Compliance)
/// - Configurable auto-sync interval (T seconds)
/// - Interactive state nodes with pulsing radar rings
/// - Detailed non-compliance breakdown per state (Legal Metrology, FSSAI, Consumer Protection rules)
class HeatmapScreen extends StatefulWidget {
  const HeatmapScreen({super.key});

  @override
  State<HeatmapScreen> createState() => _HeatmapScreenState();
}

class _HeatmapScreenState extends State<HeatmapScreen> with SingleTickerProviderStateMixin {
  AnimationController? _pulseController;
  Timer? _tickerTimer;

  int _selectedInterval = 4; // T seconds default
  int _secondsRemaining = 4;
  DateTime _lastUpdated = DateTime.now();

  String _selectedCategory = 'All Regulations';
  final List<String> _categories = [
    'All Regulations',
    'Legal Metrology (MRP)',
    'FSSAI Food Safety',
    'Packaged Commodity Rules',
    'Deceptive Advertising',
  ];

  int? _selectedStateIndex = 0; // Default to Maharashtra
  String? _lastBlinkedState;
  final List<Map<String, dynamic>> _states = [
    {
      'state': 'Maharashtra',
      'code': 'MH',
      'x': 0.32,
      'y': 0.58,
      'violationRate': 84.0,
      'complianceScore': 16.0,
      'status': 'Critical Violations',
      'color': ProPalette.crimsonViolation,
      'activeViolations': 1482,
      'inspectedSkus': 1764,
      'topBreach': 'Dual Pricing & MRP Gouging (PCR Rule 6)',
      'zone': 'Western Hub',
    },
    {
      'state': 'Delhi NCR',
      'code': 'DL',
      'x': 0.38,
      'y': 0.27,
      'violationRate': 78.0,
      'complianceScore': 22.0,
      'status': 'Critical Violations',
      'color': ProPalette.crimsonViolation,
      'activeViolations': 1240,
      'inspectedSkus': 1590,
      'topBreach': 'Counterfeit Cosmetics & Missing CDSCO Approval',
      'zone': 'Northern Hub',
    },
    {
      'state': 'Karnataka',
      'code': 'KA',
      'x': 0.35,
      'y': 0.74,
      'violationRate': 65.0,
      'complianceScore': 35.0,
      'status': 'High Non-Compliance',
      'color': Color(0xFFEA580C),
      'activeViolations': 986,
      'inspectedSkus': 1516,
      'topBreach': 'Deceptive Social Influencer Ads (ASCI Code)',
      'zone': 'Southern Tech Corridor',
    },
    {
      'state': 'Uttar Pradesh',
      'code': 'UP',
      'x': 0.50,
      'y': 0.34,
      'violationRate': 58.0,
      'complianceScore': 42.0,
      'status': 'Moderate Non-Compliance',
      'color': ProPalette.amberWarning,
      'activeViolations': 765,
      'inspectedSkus': 1318,
      'topBreach': 'Net Quantity Weight Deficit (LMA Sec 30)',
      'zone': 'Northern Belt',
    },
    {
      'state': 'Tamil Nadu',
      'code': 'TN',
      'x': 0.42,
      'y': 0.86,
      'violationRate': 52.0,
      'complianceScore': 48.0,
      'status': 'Moderate Non-Compliance',
      'color': ProPalette.amberWarning,
      'activeViolations': 842,
      'inspectedSkus': 1620,
      'topBreach': 'Missing Expiry & Customer Care Tel',
      'zone': 'Southern Manufacturing',
    },
    {
      'state': 'Gujarat',
      'code': 'GJ',
      'x': 0.18,
      'y': 0.48,
      'violationRate': 44.0,
      'complianceScore': 56.0,
      'status': 'Substantial Compliance',
      'color': Color(0xFFF59E0B),
      'activeViolations': 620,
      'inspectedSkus': 1409,
      'topBreach': 'Imported Batch Sticker Tampering',
      'zone': 'Western Trade',
    },
    {
      'state': 'West Bengal',
      'code': 'WB',
      'x': 0.72,
      'y': 0.48,
      'violationRate': 39.0,
      'complianceScore': 61.0,
      'status': 'Substantial Compliance',
      'color': Color(0xFF84CC16),
      'activeViolations': 480,
      'inspectedSkus': 1230,
      'topBreach': 'Unlabeled Origin Country (DGFT Order)',
      'zone': 'Eastern Zone',
    },
    {
      'state': 'Telangana',
      'code': 'TS',
      'x': 0.45,
      'y': 0.65,
      'violationRate': 35.0,
      'complianceScore': 65.0,
      'status': 'High Compliance',
      'color': Color(0xFF22C55E),
      'activeViolations': 510,
      'inspectedSkus': 1457,
      'topBreach': 'Misleading Health & Immunity Claims',
      'zone': 'Deccan Zone',
    },
    {
      'state': 'Punjab & Haryana',
      'code': 'PB',
      'x': 0.32,
      'y': 0.22,
      'violationRate': 28.0,
      'complianceScore': 72.0,
      'status': 'High Compliance',
      'color': ProPalette.emeraldVerified,
      'activeViolations': 312,
      'inspectedSkus': 1114,
      'topBreach': 'Inaccurate Font Size of Mandatory Declarations',
      'zone': 'Northwest Agri',
    },
    {
      'state': 'Kerala',
      'code': 'KL',
      'x': 0.36,
      'y': 0.89,
      'violationRate': 18.0,
      'complianceScore': 82.0,
      'status': 'Benchmark Compliance',
      'color': ProPalette.emeraldVerified,
      'activeViolations': 295,
      'inspectedSkus': 1638,
      'topBreach': 'Minor Packing Defect',
      'zone': 'Coastal South',
    },
    {
      'state': 'Assam & NE',
      'code': 'AS',
      'x': 0.88,
      'y': 0.36,
      'violationRate': 48.0,
      'complianceScore': 52.0,
      'status': 'Moderate Non-Compliance',
      'color': ProPalette.amberWarning,
      'activeViolations': 380,
      'inspectedSkus': 790,
      'topBreach': 'Missing FSSAI License Number Display',
      'zone': 'Northeast Frontier',
    },
  ];

  final List<Map<String, String>> _liveAuditStream = [
    {
      'time': 'Just now',
      'state': 'Maharashtra',
      'badge': 'CRITICAL',
      'color': 'red',
      'title': 'Dual MRP Sticking Detected',
      'detail': 'Packaged Snack SKU #890123: Stamped MRP Rs 120 over printed Rs 90.',
    },
    {
      'time': '3s ago',
      'state': 'Delhi NCR',
      'badge': 'SEIZED',
      'color': 'red',
      'title': 'Counterfeit Hair Serum Batch',
      'detail': 'Missing mandatory importer registration number (Rule 6(1)(c)).',
    },
    {
      'time': '7s ago',
      'state': 'Karnataka',
      'badge': 'ALERT',
      'color': 'orange',
      'title': 'Deceptive Discount Claim 70% Off',
      'detail': 'E-commerce listing inflated original price to manufacture fake discount.',
    },
  ];
  @override
  void initState() {
    super.initState();
    _initPulse();
    _startPeriodicRefresh();
  }

  void _initPulse() {
    _pulseController ??= AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _initPulse();
  }

  @override
  void dispose() {
    _pulseController?.dispose();
    _tickerTimer?.cancel();
    super.dispose();
  }

  void _startPeriodicRefresh() {
    _tickerTimer?.cancel();
    _tickerTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted) return;
      if (_secondsRemaining > 1) {
        setState(() => _secondsRemaining--);
      } else {
        _triggerLiveComplianceSync();
        setState(() {
          _secondsRemaining = _selectedInterval;
          _lastUpdated = DateTime.now();
        });
      }
    });
  }

  void _triggerLiveComplianceSync() {
    final random = Random();
    final targetIndex = random.nextInt(_states.length);
    final targetState = _states[targetIndex];

    final delta = (random.nextDouble() * 4.0) - 1.8;
    double newRate = (targetState['violationRate'] as double) + delta;
    newRate = newRate.clamp(10.0, 95.0);

    final double compliance = 100.0 - newRate;
    Color newColor;
    String newStatus;

    if (newRate >= 75.0) {
      newColor = ProPalette.crimsonViolation;
      newStatus = 'Critical Violations';
    } else if (newRate >= 55.0) {
      newColor = const Color(0xFFEA580C);
      newStatus = 'High Non-Compliance';
    } else if (newRate >= 40.0) {
      newColor = ProPalette.amberWarning;
      newStatus = 'Moderate Non-Compliance';
    } else if (newRate >= 25.0) {
      newColor = const Color(0xFF84CC16);
      newStatus = 'Substantial Compliance';
    } else {
      newColor = ProPalette.emeraldVerified;
      newStatus = 'Benchmark Compliance';
    }

    final newViolations = (targetState['activeViolations'] as int) + random.nextInt(9) - 3;

    setState(() {
      targetState['violationRate'] = double.parse(newRate.toStringAsFixed(1));
      targetState['complianceScore'] = double.parse(compliance.toStringAsFixed(1));
      targetState['color'] = newColor;
      targetState['status'] = newStatus;
      targetState['activeViolations'] = max(50, newViolations);
      _lastBlinkedState = targetState['state'] as String;
    });

    final issueTypes = [
      'MRP Tampering & Gouging',
      'Missing Manufacturer Address',
      'Net Weight Deficit (-15g)',
      'Unsubstantiated Natural Claim',
      'Expired Batch Still on Shelf',
    ];
    final selectedIssue = issueTypes[random.nextInt(issueTypes.length)];

    _liveAuditStream.insert(0, {
      'time': 'Just now',
      'state': targetState['state'] as String,
      'badge': newRate > 60 ? 'NON-COMPLIANT' : 'AUDIT LOG',
      'color': newRate > 60 ? 'red' : 'green',
      'title': selectedIssue,
      'detail': 'Field sensor auto-flagged SKU #${random.nextInt(90000) + 10000} in ${targetState['state']}.',
    });

    if (_liveAuditStream.length > 8) {
      _liveAuditStream.removeLast();
    }
  }
  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    final selectedState = _selectedStateIndex != null ? _states[_selectedStateIndex!] : null;

    return Scaffold(
      backgroundColor: isDark ? const Color(0xFF0A0F1D) : const Color(0xFFF8FAFC),
      appBar: AppBar(
        title: const Text('India Compliance Heatmap'),
        actions: [
          IconButton(
            icon: const Icon(Icons.flash_on_rounded, color: Colors.amber),
            tooltip: 'Trigger Live Telemetry Sync',
            onPressed: () {
              _triggerLiveComplianceSync();
              setState(() {
                _secondsRemaining = _selectedInterval;
                _lastUpdated = DateTime.now();
              });
            },
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        children: [
          _buildLiveTelemetryBar(isDark),
          const SizedBox(height: 12),
          _buildCategoryFilter(isDark),
          const SizedBox(height: 16),
          _buildInteractiveIndiaMapCard(isDark),
          const SizedBox(height: 16),
          _buildImpactColorScaleLegend(isDark),
          const SizedBox(height: 16),
          if (selectedState != null) _buildSelectedStateDetailCard(selectedState, isDark),
          const SizedBox(height: 16),
          _buildNationalRankingsList(isDark),
          const SizedBox(height: 16),
          _buildLiveAuditIncidentFeed(isDark),
          const SizedBox(height: 32),
        ],
      ),
    );
  }

  Widget _buildLiveTelemetryBar(bool isDark) {
    return Container(
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF1E293B) : Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: isDark ? Colors.white12 : const Color(0xFFE2E8F0)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 6,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      child: Row(
        children: [
          AnimatedBuilder(
            animation: _pulseController ?? const AlwaysStoppedAnimation(0.0),
            builder: (context, child) {
              return Container(
                width: 10,
                height: 10,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: ProPalette.crimsonViolation.withValues(
                    alpha: 0.4 + 0.6 * sin((_pulseController?.value ?? 0.0) * pi),
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: ProPalette.crimsonViolation.withValues(alpha: 0.5),
                      blurRadius: 6 * (_pulseController?.value ?? 0.0),
                    ),
                  ],
                ),
              );
            },
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'LIVE SATELLITE TELEMETRY',
                style: TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.w900,
                  letterSpacing: 0.8,
                  color: ProPalette.crimsonViolation,
                ),
              ),
              Text(
                'Next pulse in ${_secondsRemaining}s • Last sync ${_formatTime(_lastUpdated)}',
                style: TextStyle(
                  fontSize: 11,
                  color: isDark ? Colors.white60 : Colors.black54,
                ),
              ),
            ],
          ),
        ),
        const Spacer(),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: isDark ? Colors.black26 : const Color(0xFFF1F5F9),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Row(
              children: [2, 4, 8].map((t) {
                final isSel = _selectedInterval == t;
                return InkWell(
                  onTap: () {
                    setState(() {
                      _selectedInterval = t;
                      _secondsRemaining = t;
                    });
                    _startPeriodicRefresh();
                  },
                  borderRadius: BorderRadius.circular(6),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: isSel ? ProPalette.primaryForest : Colors.transparent,
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      '${t}s',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: isSel ? FontWeight.bold : FontWeight.w500,
                        color: isSel ? Colors.white : (isDark ? Colors.white70 : Colors.black87),
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCategoryFilter(bool isDark) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: _categories.map((cat) {
          final isSel = _selectedCategory == cat;
          return Padding(
            padding: const EdgeInsets.only(right: 8),
            child: FilterChip(
              selected: isSel,
              label: Text(cat),
              backgroundColor: isDark ? const Color(0xFF1E293B) : Colors.white,
              selectedColor: ProPalette.forestCardDark,
              checkmarkColor: ProPalette.accentEmerald,
              labelStyle: TextStyle(
                color: isSel ? Colors.white : (isDark ? Colors.white70 : Colors.black87),
                fontSize: 12,
                fontWeight: isSel ? FontWeight.bold : FontWeight.normal,
              ),
              onSelected: (selected) {
                if (selected) setState(() => _selectedCategory = cat);
              },
            ),
          );
        }).toList(),
      ),
    );
  }
  Widget _buildInteractiveIndiaMapCard(bool isDark) {
    return Container(
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF111827) : Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: isDark ? Colors.white12 : const Color(0xFFE2E8F0)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.public, color: ProPalette.electricBlue, size: 20),
              const SizedBox(width: 8),
              const Text(
                'National Non-Compliance Map',
                style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16),
              ),
              const Spacer(),
              if (_lastBlinkedState != null)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: ProPalette.crimsonViolation.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: ProPalette.crimsonViolation.withValues(alpha: 0.3)),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.warning_amber_rounded, size: 12, color: ProPalette.crimsonViolation),
                      const SizedBox(width: 4),
                      Text(
                        'Pulsing: $_lastBlinkedState',
                        style: const TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                          color: ProPalette.crimsonViolation,
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            'Blinking beacons show real-time violation severity. Tap any state marker to inspect breaches.',
            style: TextStyle(fontSize: 12, color: isDark ? Colors.white60 : Colors.black54),
          ),
          const SizedBox(height: 16),
          Center(
            child: SizedBox(
              height: 380,
              width: double.infinity,
              child: LayoutBuilder(
                builder: (context, constraints) {
                  final mapWidth = constraints.maxWidth;
                  final mapHeight = constraints.maxHeight;

                  return Stack(
                    children: [
                      CustomPaint(
                        size: Size(mapWidth, mapHeight),
                        painter: IndiaMapSilhouettePainter(isDark: isDark),
                      ),
                      ..._states.asMap().entries.map((entry) {
                        final index = entry.key;
                        final data = entry.value;
                        final double posX = (data['x'] as double) * mapWidth;
                        final double posY = (data['y'] as double) * mapHeight;
                        final Color color = data['color'] as Color;
                        final double rate = data['violationRate'] as double;
                        final bool isSelected = _selectedStateIndex == index;
                        final bool isHotspot = rate >= 70.0;

                        return Positioned(
                          left: posX - 28,
                          top: posY - 28,
                          child: GestureDetector(
                            onTap: () {
                              setState(() {
                                _selectedStateIndex = index;
                              });
                            },
                            child: SizedBox(
                              width: 56,
                              height: 56,
                              child: Stack(
                                alignment: Alignment.center,
                                children: [
                                  if (isHotspot || isSelected)
                                    AnimatedBuilder(
                                      animation: _pulseController ?? const AlwaysStoppedAnimation(0.0),
                                      builder: (context, child) {
                                        final pulseVal = _pulseController?.value ?? 0.0;
                                        return Container(
                                          width: 32 + (24 * pulseVal),
                                          height: 32 + (24 * pulseVal),
                                          decoration: BoxDecoration(
                                            shape: BoxShape.circle,
                                            border: Border.all(
                                              color: color.withValues(alpha: max(0.0, 1.0 - pulseVal)),
                                              width: 2.0,
                                            ),
                                          ),
                                        );
                                      },
                                    ),
                                  Container(
                                    width: isSelected ? 34 : 26,
                                    height: isSelected ? 34 : 26,
                                    decoration: BoxDecoration(
                                      shape: BoxShape.circle,
                                      color: color,
                                      border: Border.all(
                                        color: Colors.white,
                                        width: isSelected ? 2.5 : 1.5,
                                      ),
                                      boxShadow: [
                                        BoxShadow(
                                          color: color.withValues(alpha: 0.6),
                                          blurRadius: isSelected ? 8 : 4,
                                          spreadRadius: isSelected ? 2 : 0,
                                        ),
                                      ],
                                    ),
                                    child: Center(
                                      child: Text(
                                        data['code'] as String,
                                        style: TextStyle(
                                          color: Colors.white,
                                          fontWeight: FontWeight.w900,
                                          fontSize: isSelected ? 11 : 9,
                                        ),
                                      ),
                                    ),
                                  ),
                                  Positioned(
                                    bottom: 0,
                                    child: Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                                      decoration: BoxDecoration(
                                        color: isDark ? Colors.black87 : Colors.white,
                                        borderRadius: BorderRadius.circular(4),
                                        border: Border.all(color: color, width: 0.8),
                                      ),
                                      child: Text(
                                        '${rate.toInt()}%',
                                        style: TextStyle(
                                          color: color,
                                          fontSize: 8,
                                          fontWeight: FontWeight.w900,
                                        ),
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        );
                      }),
                    ],
                  );
                },
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildImpactColorScaleLegend(bool isDark) {
    return Container(
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF1E293B) : Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: isDark ? Colors.white12 : const Color(0xFFE2E8F0)),
      ),
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'VIOLATION IMPACT SCALE',
                style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, letterSpacing: 0.5),
              ),
              Text(
                'Red = High Violations • Green = Safe',
                style: TextStyle(fontSize: 10, color: Colors.grey),
              ),
            ],
          ),
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: Container(
              height: 12,
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    ProPalette.emeraldVerified,
                    Color(0xFF84CC16),
                    Color(0xFFF59E0B),
                    Color(0xFFEA580C),
                    ProPalette.crimsonViolation,
                  ],
                ),
              ),
            ),
          ),
          const SizedBox(height: 6),
          const Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('0% (Compliant)', style: TextStyle(fontSize: 10, color: ProPalette.emeraldVerified, fontWeight: FontWeight.bold)),
              Text('50% (Moderate)', style: TextStyle(fontSize: 10, color: Color(0xFFF59E0B), fontWeight: FontWeight.bold)),
              Text('100% (Critical)', style: TextStyle(fontSize: 10, color: ProPalette.crimsonViolation, fontWeight: FontWeight.bold)),
            ],
          ),
        ],
      ),
    );
  }
  Widget _buildSelectedStateDetailCard(Map<String, dynamic> state, bool isDark) {
    final color = state['color'] as Color;
    final double violationRate = state['violationRate'] as double;
    final double complianceScore = state['complianceScore'] as double;

    return Container(
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF1E293B) : Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withValues(alpha: 0.4), width: 1.5),
        boxShadow: [
          BoxShadow(
            color: color.withValues(alpha: 0.12),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.15),
                  shape: BoxShape.circle,
                ),
                child: Icon(Icons.location_on, color: color, size: 22),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          state['state'] as String,
                          style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 17),
                        ),
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: color.withValues(alpha: 0.15),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            state['status'] as String,
                            style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.bold),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'Region: ${state['zone']}',
                      style: TextStyle(fontSize: 11, color: isDark ? Colors.white60 : Colors.black54),
                    ),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    '${violationRate.toInt()}%',
                    style: TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.w900,
                      color: color,
                    ),
                  ),
                  const Text('Non-Compliant', style: TextStyle(fontSize: 10, color: Colors.grey)),
                ],
              ),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                flex: violationRate.toInt(),
                child: Container(
                  height: 8,
                  decoration: BoxDecoration(
                    color: color,
                    borderRadius: const BorderRadius.horizontal(left: Radius.circular(4)),
                  ),
                ),
              ),
              Expanded(
                flex: complianceScore.toInt(),
                child: Container(
                  height: 8,
                  decoration: const BoxDecoration(
                    color: ProPalette.emeraldVerified,
                    borderRadius: BorderRadius.horizontal(right: Radius.circular(4)),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('Violations: ${state['activeViolations']} samples', style: TextStyle(fontSize: 10, color: color, fontWeight: FontWeight.bold)),
              Text('Compliance Index: ${complianceScore.toInt()}/100', style: const TextStyle(fontSize: 10, color: ProPalette.emeraldVerified, fontWeight: FontWeight.bold)),
            ],
          ),
          const SizedBox(height: 14),
          const Divider(height: 1),
          const SizedBox(height: 12),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(Icons.gavel_rounded, size: 16, color: ProPalette.amberWarning),
              const SizedBox(width: 8),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Primary Regulatory Breach',
                      style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      state['topBreach'] as String,
                      style: TextStyle(fontSize: 12, color: isDark ? Colors.white70 : Colors.black87),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildNationalRankingsList(bool isDark) {
    final sorted = List<Map<String, dynamic>>.from(_states)
      ..sort((a, b) => (b['violationRate'] as double).compareTo(a['violationRate'] as double));

    return Container(
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF1E293B) : Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: isDark ? Colors.white12 : const Color(0xFFE2E8F0)),
      ),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'State-by-State Violation Audit',
                style: TextStyle(fontWeight: FontWeight.w800, fontSize: 15),
              ),
              Text(
                'Ranked by Non-Compliance',
                style: TextStyle(fontSize: 11, color: Colors.grey),
              ),
            ],
          ),
          const SizedBox(height: 14),
          ...sorted.map((data) {
            final color = data['color'] as Color;
            final double rate = data['violationRate'] as double;
            final originalIndex = _states.indexOf(data);
            final isSelected = _selectedStateIndex == originalIndex;

            return InkWell(
              onTap: () {
                setState(() => _selectedStateIndex = originalIndex);
              },
              borderRadius: BorderRadius.circular(8),
              child: Container(
                margin: const EdgeInsets.only(bottom: 10),
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                decoration: BoxDecoration(
                  color: isSelected
                      ? color.withValues(alpha: 0.1)
                      : (isDark ? Colors.black12 : const Color(0xFFF8FAFC)),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                    color: isSelected ? color : (isDark ? Colors.white10 : const Color(0xFFE2E8F0)),
                  ),
                ),
                child: Column(
                  children: [
                    Row(
                      children: [
                        Container(
                          width: 28,
                          height: 28,
                          decoration: BoxDecoration(
                            color: color.withValues(alpha: 0.15),
                            shape: BoxShape.circle,
                          ),
                          child: Center(
                            child: Text(
                              data['code'] as String,
                              style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 10),
                            ),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                data['state'] as String,
                                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                              ),
                              Text(
                                data['topBreach'] as String,
                                style: TextStyle(fontSize: 10, color: isDark ? Colors.white60 : Colors.black54),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ],
                          ),
                        ),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            Text(
                              '${rate.toInt()}% Non-Compliant',
                              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: color),
                            ),
                            Text(
                              '${data['activeViolations']} violations',
                              style: const TextStyle(fontSize: 10, color: Colors.grey),
                            ),
                          ],
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(4),
                      child: LinearProgressIndicator(
                        value: rate / 100.0,
                        minHeight: 5,
                        backgroundColor: isDark ? Colors.white10 : Colors.black12,
                        valueColor: AlwaysStoppedAnimation<Color>(color),
                      ),
                    ),
                  ],
                ),
              ),
            );
          }),
        ],
      ),
    );
  }

  Widget _buildLiveAuditIncidentFeed(bool isDark) {
    return Container(
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF1E293B) : Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: isDark ? Colors.white12 : const Color(0xFFE2E8F0)),
      ),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.sensors, color: ProPalette.crimsonViolation, size: 20),
              const SizedBox(width: 8),
              const Text(
                'Live Inspection Ticker',
                style: TextStyle(fontWeight: FontWeight.w800, fontSize: 15),
              ),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: ProPalette.crimsonViolation.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: const Text(
                  'Automated DCA Feed',
                  style: TextStyle(color: ProPalette.crimsonViolation, fontSize: 10, fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ..._liveAuditStream.map((incident) {
            final isRed = incident['color'] == 'red';
            final badgeColor = isRed ? ProPalette.crimsonViolation : ProPalette.emeraldVerified;

            return Container(
              margin: const EdgeInsets.only(bottom: 8),
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: isDark ? const Color(0xFF0F172A) : const Color(0xFFF8FAFC),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: isDark ? Colors.white10 : const Color(0xFFE2E8F0)),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    margin: const EdgeInsets.only(top: 2),
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: badgeColor,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Text(
                              incident['title'] ?? '',
                              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12),
                            ),
                            const Spacer(),
                            Text(
                              incident['time'] ?? '',
                              style: const TextStyle(fontSize: 10, color: Colors.grey),
                            ),
                          ],
                        ),
                        const SizedBox(height: 2),
                        Text(
                          incident['detail'] ?? '',
                          style: TextStyle(fontSize: 11, color: isDark ? Colors.white70 : Colors.black87),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  String _formatTime(DateTime dt) {
    final h = dt.hour.toString().padLeft(2, '0');
    final m = dt.minute.toString().padLeft(2, '0');
    final s = dt.second.toString().padLeft(2, '0');
    return '$h:$m:$s';
  }
}
/// CustomPainter rendering an authentic geometric silhouette of India with grid accents
class IndiaMapSilhouettePainter extends CustomPainter {
  final bool isDark;

  const IndiaMapSilhouettePainter({required this.isDark});

  @override
  void paint(Canvas canvas, Size size) {
    final double w = size.width;
    final double h = size.height;

    final path = Path();
    path.moveTo(0.36 * w, 0.05 * h); // Top Kashmir peak
    path.lineTo(0.44 * w, 0.08 * h); // Ladakh
    path.lineTo(0.46 * w, 0.16 * h); // Himachal/Uttarakhand
    path.lineTo(0.50 * w, 0.22 * h); // West Nepal border
    path.lineTo(0.66 * w, 0.27 * h); // East Nepal border
    path.lineTo(0.69 * w, 0.24 * h); // Sikkim peak
    path.lineTo(0.72 * w, 0.28 * h); // Bhutan border
    path.lineTo(0.85 * w, 0.26 * h); // Arunachal Pradesh
    path.lineTo(0.95 * w, 0.30 * h); // Far East border
    path.lineTo(0.94 * w, 0.38 * h); // Nagaland
    path.lineTo(0.88 * w, 0.45 * h); // Manipur / Mizoram
    path.lineTo(0.80 * w, 0.44 * h); // Tripura
    path.lineTo(0.77 * w, 0.38 * h); // Meghalaya
    path.lineTo(0.74 * w, 0.44 * h); // Bangladesh inlet
    path.lineTo(0.73 * w, 0.52 * h); // West Bengal / Sundarbans
    path.lineTo(0.64 * w, 0.58 * h); // Odisha coast
    path.lineTo(0.56 * w, 0.68 * h); // Andhra coast
    path.lineTo(0.48 * w, 0.82 * h); // Tamil Nadu coast
    path.lineTo(0.42 * w, 0.95 * h); // Kanyakumari southern apex
    path.lineTo(0.36 * w, 0.88 * h); // Kerala coast
    path.lineTo(0.32 * w, 0.74 * h); // Karnataka coast / Goa
    path.lineTo(0.28 * w, 0.60 * h); // Maharashtra coast / Mumbai
    path.lineTo(0.22 * w, 0.54 * h); // Gulf of Khambhat
    path.lineTo(0.12 * w, 0.50 * h); // Kathiawar / Kutch peninsula
    path.lineTo(0.14 * w, 0.42 * h); // Northern Gujarat
    path.lineTo(0.18 * w, 0.34 * h); // Thar Desert / Rajasthan border
    path.lineTo(0.26 * w, 0.22 * h); // Punjab border
    path.lineTo(0.32 * w, 0.12 * h); // J&K West border
    path.close();

    final fillPaint = Paint()
      ..color = isDark ? const Color(0xFF1E293B) : const Color(0xFFEDF2F7)
      ..style = PaintingStyle.fill;
    canvas.drawPath(path, fillPaint);

    final borderPaint = Paint()
      ..color = isDark ? const Color(0xFF38BDF8).withValues(alpha: 0.4) : const Color(0xFF94A3B8)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.0;
    canvas.drawPath(path, borderPaint);

    final gridPaint = Paint()
      ..color = isDark ? Colors.white.withValues(alpha: 0.04) : Colors.black.withValues(alpha: 0.03)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.0;

    final center = Offset(0.45 * w, 0.50 * h);
    canvas.drawCircle(center, 0.15 * w, gridPaint);
    canvas.drawCircle(center, 0.30 * w, gridPaint);
    canvas.drawCircle(center, 0.45 * w, gridPaint);

    canvas.drawLine(Offset(0.45 * w, 0.05 * h), Offset(0.45 * w, 0.95 * h), gridPaint);
    canvas.drawLine(Offset(0.10 * w, 0.50 * h), Offset(0.90 * w, 0.50 * h), gridPaint);
  }

  @override
  bool shouldRepaint(covariant IndiaMapSilhouettePainter oldDelegate) {
    return oldDelegate.isDark != isDark;
  }
}
