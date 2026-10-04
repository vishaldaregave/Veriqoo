import 'package:flutter/material.dart';
import '../../services/authority_api_service.dart';

class AuthorityCasesScreen extends StatefulWidget {
  final AuthorityApiService? apiService;

  const AuthorityCasesScreen({super.key, this.apiService});

  @override
  State<AuthorityCasesScreen> createState() => _AuthorityCasesScreenState();
}

class _AuthorityCasesScreenState extends State<AuthorityCasesScreen> {
  late final AuthorityApiService _api;
  late Future<List<AuthorityCaseSummary>> _casesFuture;

  String? _statusFilter;
  bool? _assignedFilter;
  bool _myCasesOnly = false;

  @override
  void initState() {
    super.initState();
    _api = widget.apiService ?? AuthorityApiService();
    _loadCases();
  }

  void _loadCases() {
    setState(() {
      _casesFuture = _api.listCases(
        status: _statusFilter,
        assigned: _assignedFilter,
        myCases: _myCasesOnly,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF7F7F3),
      body: SafeArea(
        child: Column(
          children: [
            _buildTopBar(),
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _buildHeader(),
                    const SizedBox(height: 16),
                    _buildFilters(),
                    const SizedBox(height: 20),
                    _buildCaseList(),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTopBar() {
    return Container(
      height: 48,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(bottom: BorderSide(color: Color(0xFFE4E7EC))),
      ),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: [
            const Icon(Icons.shield_outlined, color: Color(0xFF183B32), size: 20),
            const SizedBox(width: 8),
            const Text(
              'VERIQOO',
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, letterSpacing: 0.5),
            ),
            const SizedBox(width: 24),
            _navTab('Dashboard', false, () => Navigator.of(context).pushReplacementNamed('/dashboard')),
            _navTab('Authority Cases', true, null),
            _navTab('Products', false, () => Navigator.of(context).pushReplacementNamed('/products')),
            _navTab('Inspections', false, () => Navigator.of(context).pushReplacementNamed('/inspections')),
            const SizedBox(width: 16),
            const CircleAvatar(
              radius: 12,
              backgroundColor: Color(0xFF183B32),
              child: Icon(Icons.security, size: 14, color: Colors.white),
            ),
          ],
        ),
      ),
    );
  }

  Widget _navTab(String label, bool active, VoidCallback? onTap) {
    return Padding(
      padding: const EdgeInsets.only(right: 14),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(4),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          decoration: active
              ? BoxDecoration(
                  color: const Color(0xFFE8F0FF),
                  border: Border.all(color: const Color(0xFF80A9FF)),
                  borderRadius: BorderRadius.circular(4),
                )
              : null,
          child: Text(
            label,
            style: TextStyle(
              fontSize: 11,
              color: active ? const Color(0xFF2964D8) : const Color(0xFF344054),
              fontWeight: active ? FontWeight.w600 : FontWeight.w400,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: const [
              Text(
                'Authority Case Queue',
                style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.w700,
                  color: Color(0xFF17201D),
                ),
              ),
              SizedBox(height: 4),
              Text(
                'Manage and investigate consumer complaints verified within your legal metrology jurisdiction.',
                style: TextStyle(fontSize: 12, color: Color(0xFF68716D)),
              ),
            ],
          ),
        ),
        IconButton(
          onPressed: _loadCases,
          icon: const Icon(Icons.refresh_rounded, color: Color(0xFF183B32)),
          tooltip: 'Refresh Queue',
        ),
      ],
    );
  }

  Widget _buildFilters() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFFE4E7EC)),
      ),
      child: Wrap(
        spacing: 12,
        runSpacing: 10,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          const Text('Filters:', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 12)),
          DropdownButton<String?>(
            value: _statusFilter,
            hint: const Text('All Statuses', style: TextStyle(fontSize: 12)),
            underline: const SizedBox(),
            items: const [
              DropdownMenuItem(value: null, child: Text('All Statuses', style: TextStyle(fontSize: 12))),
              DropdownMenuItem(value: 'SUBMITTED', child: Text('SUBMITTED', style: TextStyle(fontSize: 12))),
              DropdownMenuItem(value: 'UNDER_REVIEW', child: Text('UNDER_REVIEW', style: TextStyle(fontSize: 12))),
              DropdownMenuItem(value: 'ACTION_TAKEN', child: Text('ACTION_TAKEN', style: TextStyle(fontSize: 12))),
              DropdownMenuItem(value: 'RESOLVED', child: Text('RESOLVED', style: TextStyle(fontSize: 12))),
              DropdownMenuItem(value: 'REJECTED', child: Text('REJECTED', style: TextStyle(fontSize: 12))),
            ],
            onChanged: (val) {
              setState(() => _statusFilter = val);
              _loadCases();
            },
          ),
          DropdownButton<bool?>(
            value: _assignedFilter,
            hint: const Text('All Assignments', style: TextStyle(fontSize: 12)),
            underline: const SizedBox(),
            items: const [
              DropdownMenuItem(value: null, child: Text('All Assignments', style: TextStyle(fontSize: 12))),
              DropdownMenuItem(value: true, child: Text('Assigned', style: TextStyle(fontSize: 12))),
              DropdownMenuItem(value: false, child: Text('Unassigned', style: TextStyle(fontSize: 12))),
            ],
            onChanged: (val) {
              setState(() => _assignedFilter = val);
              _loadCases();
            },
          ),
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Checkbox(
                value: _myCasesOnly,
                onChanged: (val) {
                  setState(() => _myCasesOnly = val ?? false);
                  _loadCases();
                },
              ),
              const Text('My Assigned Cases Only', style: TextStyle(fontSize: 12)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildCaseList() {
    return FutureBuilder<List<AuthorityCaseSummary>>(
      future: _casesFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(
            child: Padding(
              padding: EdgeInsets.all(40),
              child: CircularProgressIndicator(),
            ),
          );
        }

        if (snapshot.hasError) {
          final err = snapshot.error;
          final isForbidden = err is AuthorityApiException && (err.statusCode == 403 || err.statusCode == 401);
          return Container(
            width: double.infinity,
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: isForbidden ? const Color(0xFFFEF3F2) : Colors.white,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: isForbidden ? const Color(0xFFFECDCA) : const Color(0xFFE4E7EC)),
            ),
            child: Column(
              children: [
                Icon(
                  isForbidden ? Icons.gpp_bad_outlined : Icons.error_outline_rounded,
                  color: isForbidden ? const Color(0xFFB42318) : const Color(0xFFD92D20),
                  size: 44,
                ),
                const SizedBox(height: 12),
                Text(
                  isForbidden ? 'Access Denied' : 'Failed to Load Cases',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                    color: isForbidden ? const Color(0xFFB42318) : const Color(0xFF17201D),
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  err is AuthorityApiException ? err.message : err.toString(),
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 12, color: Color(0xFF475467)),
                ),
                const SizedBox(height: 16),
                ElevatedButton.icon(
                  onPressed: _loadCases,
                  icon: const Icon(Icons.refresh, size: 16),
                  label: const Text('Try Again'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF183B32),
                    foregroundColor: Colors.white,
                  ),
                ),
              ],
            ),
          );
        }

        final cases = snapshot.data ?? [];
        if (cases.isEmpty) {
          return Container(
            width: double.infinity,
            padding: const EdgeInsets.all(40),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: const Color(0xFFE4E7EC)),
            ),
            child: Column(
              children: const [
                Icon(Icons.inbox_outlined, size: 48, color: Color(0xFF98A2B3)),
                SizedBox(height: 12),
                Text(
                  'No cases found in this jurisdiction queue.',
                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: Color(0xFF344054)),
                ),
                SizedBox(height: 4),
                Text(
                  'Complaints submitted by consumers will appear here once verified against your jurisdiction.',
                  style: TextStyle(fontSize: 12, color: Color(0xFF667085)),
                ),
              ],
            ),
          );
        }

        return ListView.separated(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: cases.length,
          separatorBuilder: (_, __) => const SizedBox(height: 10),
          itemBuilder: (context, index) {
            final c = cases[index];
            return _buildCaseCard(c);
          },
        );
      },
    );
  }

  Widget _buildCaseCard(AuthorityCaseSummary c) {
    Color statusColor;
    Color statusBg;
    switch (c.status) {
      case 'SUBMITTED':
        statusColor = const Color(0xFF344054);
        statusBg = const Color(0xFFF2F4F7);
        break;
      case 'UNDER_REVIEW':
        statusColor = const Color(0xFFB54708);
        statusBg = const Color(0xFFFEF0C7);
        break;
      case 'ACTION_TAKEN':
        statusColor = const Color(0xFF175CD3);
        statusBg = const Color(0xFFEFF8FF);
        break;
      case 'RESOLVED':
        statusColor = const Color(0xFF027A48);
        statusBg = const Color(0xFFECFDF3);
        break;
      case 'REJECTED':
        statusColor = const Color(0xFFB42318);
        statusBg = const Color(0xFFFEF3F2);
        break;
      default:
        statusColor = const Color(0xFF344054);
        statusBg = const Color(0xFFF2F4F7);
    }

    return Card(
      elevation: 0,
      color: Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(10),
        side: const BorderSide(color: Color(0xFFE4E7EC)),
      ),
      child: InkWell(
        onTap: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => AuthorityCaseDetailScreen(
                caseId: c.id,
                apiService: _api,
                onStateChanged: _loadCases,
              ),
            ),
          );
        },
        borderRadius: BorderRadius.circular(10),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(
                    child: Text(
                      c.title,
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: Color(0xFF101828),
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: statusBg,
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      c.status,
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w700,
                        color: statusColor,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  _chip(Icons.category_outlined, c.issueType),
                  const SizedBox(width: 8),
                  _chip(Icons.location_on_outlined, '${c.stateCode ?? "IN"} / ${c.districtCode ?? "STATEWIDE"}'),
                  const SizedBox(width: 8),
                  _chip(Icons.account_balance_outlined, c.department),
                ],
              ),
              const SizedBox(height: 12),
              const Divider(height: 1, color: Color(0xFFF2F4F7)),
              const SizedBox(height: 8),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Row(
                    children: [
                      Icon(
                        c.assignedOfficerId != null ? Icons.person : Icons.person_outline,
                        size: 14,
                        color: c.assignedOfficerId != null ? const Color(0xFF175CD3) : const Color(0xFF667085),
                      ),
                      const SizedBox(width: 4),
                      Text(
                        c.assignedOfficerId != null ? 'Assigned' : 'Unassigned',
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w500,
                          color: c.assignedOfficerId != null ? const Color(0xFF175CD3) : const Color(0xFF667085),
                        ),
                      ),
                    ],
                  ),
                  Text(
                    'Submitted: ${c.createdAt.toLocal().toString().split('.').first}',
                    style: const TextStyle(fontSize: 10, color: Color(0xFF98A2B3)),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _chip(IconData icon, String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: const Color(0xFFF9FAFB),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: const Color(0xFFEAECF0)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 11, color: const Color(0xFF475467)),
          const SizedBox(width: 3),
          Text(label, style: const TextStyle(fontSize: 10, color: Color(0xFF344054))),
        ],
      ),
    );
  }
}

class AuthorityCaseDetailScreen extends StatefulWidget {
  final String caseId;
  final AuthorityApiService apiService;
  final VoidCallback? onStateChanged;

  const AuthorityCaseDetailScreen({
    super.key,
    required this.caseId,
    required this.apiService,
    this.onStateChanged,
  });

  @override
  State<AuthorityCaseDetailScreen> createState() => _AuthorityCaseDetailScreenState();
}

class _AuthorityCaseDetailScreenState extends State<AuthorityCaseDetailScreen> {
  late Future<AuthorityCaseDetail> _detailFuture;
  late Future<List<CaseNote>> _notesFuture;
  late Future<List<CaseAuditEvent>> _auditFuture;

  final TextEditingController _noteController = TextEditingController();
  final TextEditingController _resolutionController = TextEditingController();
  bool _isSubmittingNote = false;
  bool _isAssigning = false;
  bool _isTransitioning = false;
  String? _actionError;

  @override
  void initState() {
    super.initState();
    _loadAll();
  }

  @override
  void dispose() {
    _noteController.dispose();
    _resolutionController.dispose();
    super.dispose();
  }

  void _loadAll() {
    setState(() {
      _actionError = null;
      _detailFuture = widget.apiService.getCaseDetails(widget.caseId);
      _notesFuture = widget.apiService.listNotes(widget.caseId);
      _auditFuture = widget.apiService.getAuditTimeline(widget.caseId);
    });
  }

  Future<void> _handleSelfAssign(AuthorityCaseDetail caseDetail) async {
    setState(() {
      _isAssigning = true;
      _actionError = null;
    });

    try {
      final isCurrentlyUnassigned = caseDetail.assignedOfficerId == null;
      await widget.apiService.assignOfficer(
        caseId: widget.caseId,
        expectUnassigned: isCurrentlyUnassigned,
        expectedAssignedOfficerId: isCurrentlyUnassigned ? null : caseDetail.assignedOfficerId,
      );

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Successfully assigned case to yourself.')),
      );
      _loadAll();
      widget.onStateChanged?.call();
    } on AuthorityApiException catch (e) {
      setState(() {
        if (e.statusCode == 409) {
          _actionError = 'Assignment conflict: the case assignment was changed concurrently by another operation. Please review the updated case state.';
        } else {
          _actionError = e.message;
        }
      });
      _loadAll();
    } catch (e) {
      setState(() => _actionError = e.toString());
    } finally {
      if (mounted) setState(() => _isAssigning = false);
    }
  }

  Future<void> _handleAddNote() async {
    final text = _noteController.text.trim();
    if (text.isEmpty) {
      setState(() => _actionError = 'Investigation note cannot be empty.');
      return;
    }
    if (text.length > 5000) {
      setState(() => _actionError = 'Investigation note exceeds maximum length of 5000 characters.');
      return;
    }

    setState(() {
      _isSubmittingNote = true;
      _actionError = null;
    });

    try {
      await widget.apiService.addNote(caseId: widget.caseId, noteText: text);
      _noteController.clear();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Investigation note recorded.')),
      );
      _loadAll();
    } on AuthorityApiException catch (e) {
      setState(() => _actionError = e.message);
    } catch (e) {
      setState(() => _actionError = e.toString());
    } finally {
      if (mounted) setState(() => _isSubmittingNote = false);
    }
  }

  Future<void> _handleStatusTransition(AuthorityCaseDetail caseDetail, String targetStatus) async {
    final resolution = _resolutionController.text.trim();
    final requiresResolution = ['ACTION_TAKEN', 'RESOLVED', 'REJECTED'].contains(targetStatus);

    if (requiresResolution && resolution.isEmpty) {
      setState(() => _actionError = 'Resolution notes are required when moving to $targetStatus.');
      return;
    }

    setState(() {
      _isTransitioning = true;
      _actionError = null;
    });

    try {
      await widget.apiService.transitionStatus(
        caseId: widget.caseId,
        newStatus: targetStatus,
        expectedStatus: caseDetail.status,
        resolutionNotes: resolution.isNotEmpty ? resolution : null,
      );

      _resolutionController.clear();
      if (!mounted) return;
      Navigator.of(context, rootNavigator: true).pop(); // dismiss modal
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Case status transitioned to $targetStatus.')),
      );
      _loadAll();
      widget.onStateChanged?.call();
    } on AuthorityApiException catch (e) {
      setState(() {
        if (e.statusCode == 409) {
          _actionError = 'Status conflict: the case status has changed concurrently. Case details have been refreshed.';
        } else {
          _actionError = e.message;
        }
      });
      _loadAll();
    } catch (e) {
      setState(() => _actionError = e.toString());
    } finally {
      if (mounted) setState(() => _isTransitioning = false);
    }
  }

  void _showTransitionDialog(AuthorityCaseDetail caseDetail) {
    _resolutionController.clear();
    final validTargets = _getValidTransitions(caseDetail.status);

    if (validTargets.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No status transitions available for terminal status.')),
      );
      return;
    }

    String selectedTarget = validTargets.first;

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: const Text('Update Case Status', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Current Status: ${caseDetail.status}', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
              const SizedBox(height: 12),
              const Text('Target Status:', style: TextStyle(fontSize: 12)),
              DropdownButton<String>(
                value: selectedTarget,
                isExpanded: true,
                items: validTargets.map((s) => DropdownMenuItem(value: s, child: Text(s, style: const TextStyle(fontSize: 12)))).toList(),
                onChanged: (val) {
                  if (val != null) setDialogState(() => selectedTarget = val);
                },
              ),
              const SizedBox(height: 12),
              const Text('Resolution Notes / Action Summary:', style: TextStyle(fontSize: 12)),
              const SizedBox(height: 4),
              TextField(
                controller: _resolutionController,
                maxLines: 3,
                decoration: const InputDecoration(
                  hintText: 'Enter substantive explanation of regulatory findings or actions taken...',
                  hintStyle: TextStyle(fontSize: 11),
                  border: OutlineInputBorder(),
                ),
              ),
            ],
          ),
          actions: [
            TextButton(onPressed: () => Navigator.of(ctx).pop(), child: const Text('Cancel')),
            ElevatedButton(
              onPressed: _isTransitioning ? null : () => _handleStatusTransition(caseDetail, selectedTarget),
              style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF183B32), foregroundColor: Colors.white),
              child: _isTransitioning ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)) : const Text('Apply Transition'),
            ),
          ],
        ),
      ),
    );
  }

  List<String> _getValidTransitions(String currentStatus) {
    switch (currentStatus) {
      case 'SUBMITTED':
        return ['UNDER_REVIEW', 'REJECTED'];
      case 'UNDER_REVIEW':
        return ['ACTION_TAKEN', 'RESOLVED', 'REJECTED'];
      case 'ACTION_TAKEN':
        return ['RESOLVED', 'REJECTED'];
      default:
        return [];
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF7F7F3),
      appBar: AppBar(
        title: const Text('Investigation Case Details', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
        backgroundColor: Colors.white,
        elevation: 0,
        surfaceTintColor: Colors.transparent,
      ),
      body: FutureBuilder<AuthorityCaseDetail>(
        future: _detailFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }

          if (snapshot.hasError) {
            final err = snapshot.error;
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.error_outline, color: Color(0xFFD92D20), size: 48),
                    const SizedBox(height: 12),
                    Text(err is AuthorityApiException ? err.message : err.toString(), textAlign: TextAlign.center),
                    const SizedBox(height: 16),
                    ElevatedButton(onPressed: _loadAll, child: const Text('Retry')),
                  ],
                ),
              ),
            );
          }

          final caseDetail = snapshot.data!;
          return SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (_actionError != null) ...[
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: const Color(0xFFFEF3F2),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: const Color(0xFFFECDCA)),
                    ),
                    child: Text(_actionError!, style: const TextStyle(color: Color(0xFFB42318), fontSize: 12)),
                  ),
                  const SizedBox(height: 14),
                ],
                _buildOverviewCard(caseDetail),
                const SizedBox(height: 16),
                _buildEvidenceCard(caseDetail),
                const SizedBox(height: 16),
                _buildActionsCard(caseDetail),
                const SizedBox(height: 16),
                _buildNotesCard(),
                const SizedBox(height: 16),
                _buildAuditTimelineCard(),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildOverviewCard(AuthorityCaseDetail c) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFE4E7EC)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Case #${c.id.substring(0, 8)}',
                style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: Color(0xFF475467)),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: const Color(0xFFF2F4F7),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  c.status,
                  style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: Color(0xFF344054)),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(c.title, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: Color(0xFF101828))),
          const SizedBox(height: 8),
          Text(c.description, style: const TextStyle(fontSize: 13, height: 1.4, color: Color(0xFF344054))),
          const SizedBox(height: 14),
          const Divider(height: 1, color: Color(0xFFF2F4F7)),
          const SizedBox(height: 12),
          Wrap(
            spacing: 16,
            runSpacing: 8,
            children: [
              _infoRow('Department', c.department),
              _infoRow('State', c.stateCode ?? 'N/A'),
              _infoRow('District', c.districtCode ?? 'STATEWIDE'),
              _infoRow('Verified Jurisdiction', c.jurisdictionVerified ? 'YES' : 'NO'),
              _infoRow('Assigned Officer', c.assignedOfficerId ?? 'Unassigned'),
              if (c.savedProductId != null) _infoRow('Saved Product ID', c.savedProductId!),
              if (c.inspectionId != null) _infoRow('Inspection Ref', c.inspectionId!),
            ],
          ),
        ],
      ),
    );
  }

  Widget _infoRow(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontSize: 10, color: Color(0xFF667085))),
        const SizedBox(height: 2),
        Text(value, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Color(0xFF101828))),
      ],
    );
  }

  Widget _buildEvidenceCard(AuthorityCaseDetail c) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFE4E7EC)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Consumer Evidence', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: Color(0xFF101828))),
          const SizedBox(height: 10),
          if (c.evidenceImages.isEmpty)
            const Text('No evidence images attached to this complaint.', style: TextStyle(fontSize: 12, color: Color(0xFF667085)))
          else
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: c.evidenceImages.map((img) {
                final url = (img is Map<String, dynamic> ? img['url'] : img.toString()) as String?;
                if (url == null || url.isEmpty) {
                  return const SizedBox();
                }
                return ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: Image.network(
                    url,
                    width: 90,
                    height: 90,
                    fit: BoxFit.cover,
                    errorBuilder: (_, __, ___) => Container(
                      width: 90,
                      height: 90,
                      color: const Color(0xFFF2F4F7),
                      child: const Icon(Icons.broken_image, size: 24, color: Color(0xFF98A2B3)),
                    ),
                  ),
                );
              }).toList(),
            ),
        ],
      ),
    );
  }

  Widget _buildActionsCard(AuthorityCaseDetail c) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFE4E7EC)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Operational Actions', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: Color(0xFF101828))),
          const SizedBox(height: 12),
          Wrap(
            spacing: 12,
            runSpacing: 8,
            children: [
              ElevatedButton.icon(
                onPressed: _isAssigning ? null : () => _handleSelfAssign(c),
                icon: const Icon(Icons.assignment_ind_outlined, size: 16),
                label: Text(c.assignedOfficerId == null ? 'Assign to Me' : 'Reassign to Me'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF183B32),
                  foregroundColor: Colors.white,
                ),
              ),
              OutlinedButton.icon(
                onPressed: _isTransitioning ? null : () => _showTransitionDialog(c),
                icon: const Icon(Icons.published_with_changes_outlined, size: 16),
                label: const Text('Update Status'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: const Color(0xFF183B32),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildNotesCard() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFE4E7EC)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: const [
              Text('Confidential Investigation Notes', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: Color(0xFF101828))),
              Text('INTERNAL ONLY', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: Color(0xFFB42318))),
            ],
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _noteController,
            maxLines: 3,
            decoration: const InputDecoration(
              hintText: 'Record internal findings, inspection logs, or enforcement notes (1-5000 chars)...',
              hintStyle: TextStyle(fontSize: 11),
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerRight,
            child: ElevatedButton(
              onPressed: _isSubmittingNote ? null : _handleAddNote,
              style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF183B32), foregroundColor: Colors.white),
              child: _isSubmittingNote
                  ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                  : const Text('Add Note'),
            ),
          ),
          const SizedBox(height: 12),
          FutureBuilder<List<CaseNote>>(
            future: _notesFuture,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const Center(child: Padding(padding: EdgeInsets.all(12), child: CircularProgressIndicator(strokeWidth: 2)));
              }
              final notes = snapshot.data ?? [];
              if (notes.isEmpty) {
                return const Text('No internal notes recorded yet.', style: TextStyle(fontSize: 12, color: Color(0xFF667085)));
              }
              return ListView.separated(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: notes.length,
                separatorBuilder: (_, __) => const SizedBox(height: 8),
                itemBuilder: (context, idx) {
                  final n = notes[idx];
                  return Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: const Color(0xFFF9FAFB),
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: const Color(0xFFEAECF0)),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(n.noteText, style: const TextStyle(fontSize: 12, color: Color(0xFF344054))),
                        const SizedBox(height: 4),
                        Text(
                          'Recorded by ${n.authorId.substring(0, 8)} at ${n.createdAt.toLocal().toString().split('.').first}',
                          style: const TextStyle(fontSize: 10, color: Color(0xFF98A2B3)),
                        ),
                      ],
                    ),
                  );
                },
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _buildAuditTimelineCard() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFE4E7EC)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Case Audit Timeline', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: Color(0xFF101828))),
          const SizedBox(height: 12),
          FutureBuilder<List<CaseAuditEvent>>(
            future: _auditFuture,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const Center(child: Padding(padding: EdgeInsets.all(12), child: CircularProgressIndicator(strokeWidth: 2)));
              }
              final events = snapshot.data ?? [];
              if (events.isEmpty) {
                return const Text('No audit events available.', style: TextStyle(fontSize: 12, color: Color(0xFF667085)));
              }
              return ListView.separated(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: events.length,
                separatorBuilder: (_, __) => const SizedBox(height: 8),
                itemBuilder: (context, idx) {
                  final e = events[idx];
                  return Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(Icons.circle, size: 8, color: Color(0xFF183B32)),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              e.action,
                              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Color(0xFF101828)),
                            ),
                            if (e.previousState != null || e.newState != null)
                              Text(
                                '${e.previousState ?? "NONE"} -> ${e.newState ?? "NONE"}',
                                style: const TextStyle(fontSize: 10, color: Color(0xFF475467)),
                              ),
                            Text(
                              'By ${e.actorId.substring(0, 8)} at ${e.createdAt.toLocal().toString().split('.').first}',
                              style: const TextStyle(fontSize: 10, color: Color(0xFF98A2B3)),
                            ),
                          ],
                        ),
                      ),
                    ],
                  );
                },
              );
            },
          ),
        ],
      ),
    );
  }
}
