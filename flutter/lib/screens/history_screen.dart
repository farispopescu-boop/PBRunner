// lib/screens/history_screen.dart
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../main.dart' show historyRefreshBus;
import '../theme.dart';
import '../services/api_service.dart';
import 'result_screen.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  List<Map<String, dynamic>> _history = [];
  bool _loading = true;
  final _api = ApiService();

  @override
  void initState() {
    super.initState();
    _loadHistory();
    // Asculta evenimente de refresh din main.dart
    historyRefreshBus.addListener(_onRefreshSignal);
  }

  @override
  void dispose() {
    historyRefreshBus.removeListener(_onRefreshSignal);
    super.dispose();
  }

  void _onRefreshSignal() {
    if (mounted) _loadHistory();
  }

  Future<void> _loadHistory() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getStringList('job_history') ?? [];
      if (!mounted) return;
      setState(() {
        _history = raw
            .map((s) => jsonDecode(s) as Map<String, dynamic>)
            .toList()
            .reversed
            .toList();
        _loading = false;
      });
    } catch (_) {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _openJob(Map<String, dynamic> job) async {
    final jobId = job['job_id'] as String?;
    if (jobId == null) return;
    try {
      final result = await _api.getResult(jobId);
      if (mounted) {
        await Navigator.push(
            context,
            MaterialPageRoute(
                builder: (_) => ResultScreen(result: result, jobId: jobId)));
        // La intoarcerea pe Istoric, reincarcam (poate s-a sters un job)
        if (mounted) _loadHistory();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
              content: Text('Job expirat sau indisponibil: $e'),
              backgroundColor: PBTheme.red),
        );
      }
    }
  }

  Future<void> _clearHistory() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: PBTheme.surface,
        title: const Text('Sterge istoricul?',
            style: TextStyle(color: PBTheme.textPrimary)),
        content: const Text('Toate analizele salvate local vor fi sterse.',
            style: TextStyle(color: PBTheme.textSecondary)),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Anuleaza')),
          TextButton(
              onPressed: () => Navigator.pop(ctx, true),
              child:
                  const Text('Sterge', style: TextStyle(color: PBTheme.red))),
        ],
      ),
    );
    if (confirm == true) {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove('job_history');
      _loadHistory();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: PBTheme.bg,
      appBar: AppBar(
        title: const Text('Istoric analize'),
        actions: [
          if (_history.isNotEmpty)
            IconButton(
              icon: const Icon(Icons.delete_sweep_outlined),
              tooltip: 'Sterge istoricul',
              onPressed: _clearHistory,
            ),
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Reincarca',
            onPressed: _loadHistory,
          ),
        ],
      ),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: PBTheme.accent))
          : RefreshIndicator(
              color: PBTheme.accent,
              backgroundColor: PBTheme.surface,
              onRefresh: _loadHistory,
              child: _history.isEmpty
                  ? ListView(
                      physics: const AlwaysScrollableScrollPhysics(),
                      children: [
                        SizedBox(
                            height: MediaQuery.of(context).size.height * 0.25),
                        const Center(
                          child: Column(
                            children: [
                              Icon(Icons.history,
                                  color: PBTheme.textDim, size: 64),
                              SizedBox(height: 16),
                              Text('Nicio analiza salvata',
                                  style: TextStyle(
                                      color: PBTheme.textSecondary,
                                      fontSize: 16)),
                              SizedBox(height: 8),
                              Text('Analizele recente apar aici',
                                  style: TextStyle(color: PBTheme.textDim)),
                              SizedBox(height: 16),
                              Text('Trage in jos pentru reincarcare',
                                  style: TextStyle(
                                      color: PBTheme.textDim, fontSize: 12)),
                            ],
                          ),
                        ),
                      ],
                    )
                  : ListView.separated(
                      padding: const EdgeInsets.all(16),
                      physics: const AlwaysScrollableScrollPhysics(),
                      itemCount: _history.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 10),
                      itemBuilder: (_, i) {
                        final job = _history[i];
                        return GestureDetector(
                          onTap: () => _openJob(job),
                          child: Container(
                            padding: const EdgeInsets.all(16),
                            decoration: PBTheme.cardDecor(),
                            child: Row(children: [
                              Container(
                                padding: const EdgeInsets.all(10),
                                decoration: BoxDecoration(
                                  color: PBTheme.accentGlow,
                                  borderRadius: BorderRadius.circular(10),
                                ),
                                child: const Icon(Icons.analytics_outlined,
                                    color: PBTheme.accent),
                              ),
                              const SizedBox(width: 14),
                              Expanded(
                                  child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(job['athlete_name'] ?? 'Atlet',
                                      style: const TextStyle(
                                          color: PBTheme.textPrimary,
                                          fontWeight: FontWeight.w600)),
                                  Text(job['created_at'] ?? '',
                                      style: const TextStyle(
                                          color: PBTheme.textSecondary,
                                          fontSize: 12)),
                                ],
                              )),
                              const Icon(Icons.chevron_right,
                                  color: PBTheme.textDim),
                            ]),
                          ),
                        );
                      },
                    ),
            ),
    );
  }
}
