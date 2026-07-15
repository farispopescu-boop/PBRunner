// lib/screens/home_screen.dart
import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:image_picker/image_picker.dart';
import 'package:percent_indicator/percent_indicator.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../theme.dart';
import '../models/athlete_model.dart';
import '../models/job_model.dart';
import '../services/api_service.dart';
import 'result_screen.dart';
import 'athletes_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  // ── State ────────────────────────────────────────────────────────────────
  File? _selectedVideo;
  Athlete? _selectedAthlete;
  String _lang = 'ro';
  double _slowmoFps = 0.0;
  bool _isUploading = false;
  String? _currentJobId;
  JobStatus? _jobStatus;
  Timer? _pollTimer;
  String? _errorMessage;
  bool _jobHandled = false; // previne salvarea duplicata in istoric

  final _api = ApiService();

  @override
  void initState() {
    super.initState();
    _loadSavedAthlete();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadSavedAthlete() async {
    final prefs = await SharedPreferences.getInstance();
    final name = prefs.getString('last_athlete_name');
    if (name != null && mounted) {
      setState(() {
        _selectedAthlete = Athlete(
          name: name,
          heightCm: prefs.getDouble('last_height') ?? 184,
          weightKg: prefs.getDouble('last_weight') ?? 82,
          age: prefs.getInt('last_age') ?? 21,
        );
      });
    }
  }

  // ── Video selection ──────────────────────────────────────────────────────
  Future<void> _pickVideo() async {
    final picker = ImagePicker();
    final source = await _showSourceDialog();
    if (source == null) return;

    final picked = await picker.pickVideo(
      source: source,
      maxDuration: const Duration(minutes: 2),
    );
    if (picked == null) return;

    setState(() {
      _selectedVideo = File(picked.path);
      _currentJobId = null;
      _jobStatus = null;
      _errorMessage = null;
    });
  }

  Future<ImageSource?> _showSourceDialog() async {
    return showModalBottomSheet<ImageSource>(
      context: context,
      backgroundColor: PBTheme.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Selectează video',
                style: TextStyle(
                    color: PBTheme.textPrimary,
                    fontWeight: FontWeight.bold,
                    fontSize: 18)),
            const SizedBox(height: 20),
            _sourceOption(
              icon: Icons.videocam_outlined,
              title: 'Filmează acum',
              subtitle: 'Deschide camera',
              onTap: () => Navigator.pop(context, ImageSource.camera),
            ),
            const SizedBox(height: 12),
            _sourceOption(
              icon: Icons.photo_library_outlined,
              title: 'Din galerie',
              subtitle: 'Alege video existent',
              onTap: () => Navigator.pop(context, ImageSource.gallery),
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  Widget _sourceOption({
    required IconData icon,
    required String title,
    required String subtitle,
    required VoidCallback onTap,
  }) =>
      InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
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
              child: Icon(icon, color: PBTheme.accent, size: 24),
            ),
            const SizedBox(width: 16),
            Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(title,
                  style: const TextStyle(
                      color: PBTheme.textPrimary, fontWeight: FontWeight.w600)),
              Text(subtitle,
                  style: const TextStyle(
                      color: PBTheme.textSecondary, fontSize: 12)),
            ]),
          ]),
        ),
      );

  // ── Submit analysis ──────────────────────────────────────────────────────
  Future<void> _submitAnalysis() async {
    if (_selectedVideo == null) {
      _showSnack('Selectează un video mai întâi');
      return;
    }
    if (_selectedAthlete == null) {
      _showSnack('Selectează sau creează un atlet');
      return;
    }

    // Verifica conexiune
    final online = await _api.isOnline();
    if (!online) {
      _showSnack('Serverul nu e accesibil. Verifică conexiunea.');
      return;
    }

    setState(() {
      _isUploading = true;
      _errorMessage = null;
      _jobStatus = null;
    });

    try {
      final job = await _api.submitVideo(
        videoFile: _selectedVideo!,
        athleteName: _selectedAthlete!.name,
        heightCm: _selectedAthlete!.heightCm,
        weightKg: _selectedAthlete!.weightKg,
        age: _selectedAthlete!.age,
        lang: _lang,
        slowmoFps: _slowmoFps,
      );

      setState(() {
        _currentJobId = job.jobId;
        _isUploading = false;
      });

      _startPolling(job.jobId);

      // Salveaza ultimul atlet folosit
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('last_athlete_name', _selectedAthlete!.name);
      await prefs.setDouble('last_height', _selectedAthlete!.heightCm);
      await prefs.setDouble('last_weight', _selectedAthlete!.weightKg);
      await prefs.setInt('last_age', _selectedAthlete!.age);
    } catch (e) {
      setState(() {
        _isUploading = false;
        _errorMessage = e.toString();
      });
    }
  }

  void _startPolling(String jobId) {
    _pollTimer?.cancel();
    _jobHandled = false; // reset la fiecare job nou
    _pollTimer = Timer.periodic(const Duration(seconds: 3), (timer) async {
      try {
        final status = await _api.getJobStatus(jobId);
        if (!mounted) return;
        setState(() => _jobStatus = status);

        if (status.isDone) {
          timer.cancel();
          if (!_jobHandled) {
            _jobHandled = true; // garantam ca se apeleaza O SINGURA DATA
            _onAnalysisDone(jobId);
          }
        } else if (status.isError) {
          timer.cancel();
          setState(() {
            _errorMessage = status.message;
            _currentJobId = null; // reset ca sa permita retrimitere
          });
        }
      } catch (e) {
        // Continua polling la erori de retea
      }
    });
  }

  Future<void> _onAnalysisDone(String jobId) async {
    // Salveaza in istoric O SINGURA DATA
    await _saveToHistory(jobId);

    try {
      final result = await _api.getResult(jobId);
      if (!mounted) return;
      await Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => ResultScreen(result: result, jobId: jobId),
        ),
      );
      // Dupa intoarcerea din ResultScreen, resetam starea
      if (mounted) {
        setState(() {
          _currentJobId = null;
          _jobStatus = null;
          _jobHandled = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = 'Eroare la rezultate: $e';
          _currentJobId = null;
        });
      }
    }
  }

  Future<void> _saveToHistory(String jobId) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final history = prefs.getStringList('job_history') ?? [];

      // Verifica daca jobId exista deja (previne duplicatele)
      final exists = history.any((e) {
        try {
          final m = jsonDecode(e) as Map<String, dynamic>;
          return m['job_id'] == jobId;
        } catch (_) {
          return false;
        }
      });
      if (exists) return;

      final entry = jsonEncode({
        'job_id': jobId,
        'athlete_name': _selectedAthlete?.name ?? 'Atlet',
        'created_at': DateTime.now().toIso8601String(),
      });
      history.insert(0, entry);

      // Pastreaza max 50 analize in istoric
      if (history.length > 50) history.removeLast();
      await prefs.setStringList('job_history', history);
    } catch (_) {}
  }

  void _showSnack(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor: PBTheme.surface,
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  // ── UI ───────────────────────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: CustomScrollView(
        slivers: [
          _buildAppBar(),
          SliverPadding(
            padding: const EdgeInsets.all(16),
            sliver: SliverList(
              delegate: SliverChildListDelegate([
                _buildAthleteSelector(),
                const SizedBox(height: 16),
                _buildVideoSelector(),
                const SizedBox(height: 16),
                _buildOptions(),
                const SizedBox(height: 20),
                _buildAnalyzeButton(),
                if (_currentJobId != null) ...[
                  const SizedBox(height: 20),
                  _buildProgressCard(),
                ],
                if (_errorMessage != null) ...[
                  const SizedBox(height: 16),
                  _buildErrorCard(),
                ],
                const SizedBox(height: 80),
              ]),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAppBar() => SliverAppBar(
        floating: true,
        backgroundColor: PBTheme.bg,
        title: Row(children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              gradient: PBTheme.accentGrad,
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Center(
              child: Text('PB',
                  style: TextStyle(
                      color: Colors.black,
                      fontWeight: FontWeight.w900,
                      fontSize: 13)),
            ),
          ),
          const SizedBox(width: 12),
          const Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('PBRunner',
                  style: TextStyle(
                      color: PBTheme.textPrimary,
                      fontWeight: FontWeight.w800,
                      fontSize: 18)),
              Text('Analiză biomechanică sprint',
                  style: TextStyle(color: PBTheme.textSecondary, fontSize: 11)),
            ],
          ),
        ]),
      );

  Widget _buildAthleteSelector() => GestureDetector(
        onTap: () async {
          final result = await Navigator.push<Athlete>(
            context,
            MaterialPageRoute(
                builder: (_) => const AthletesScreen(selectionMode: true)),
          );
          if (result != null) setState(() => _selectedAthlete = result);
        },
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: PBTheme.cardDecor(glow: _selectedAthlete != null),
          child: Row(children: [
            CircleAvatar(
              radius: 24,
              backgroundColor: PBTheme.accentGlow,
              child: Text(
                _selectedAthlete?.initials ?? '+',
                style: TextStyle(
                  color: _selectedAthlete != null
                      ? PBTheme.accent
                      : PBTheme.textDim,
                  fontWeight: FontWeight.bold,
                  fontSize: _selectedAthlete != null ? 16 : 20,
                ),
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: _selectedAthlete == null
                  ? const Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Selectează atlet',
                            style: TextStyle(
                                color: PBTheme.accent,
                                fontWeight: FontWeight.w600)),
                        Text('Atingeți pentru a alege sau crea',
                            style: TextStyle(
                                color: PBTheme.textDim, fontSize: 12)),
                      ],
                    )
                  : Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(_selectedAthlete!.name,
                            style: const TextStyle(
                                color: PBTheme.textPrimary,
                                fontWeight: FontWeight.w600)),
                        Text(
                            '${_selectedAthlete!.heightCm.toStringAsFixed(0)}cm  '
                            '${_selectedAthlete!.weightKg.toStringAsFixed(0)}kg  '
                            '${_selectedAthlete!.age} ani',
                            style: const TextStyle(
                                color: PBTheme.textSecondary, fontSize: 12)),
                      ],
                    ),
            ),
            const Icon(Icons.chevron_right, color: PBTheme.textDim),
          ]),
        ),
      );

  Widget _buildVideoSelector() => GestureDetector(
        onTap: _pickVideo,
        child: Container(
          height: 180,
          decoration: PBTheme.cardDecor(
            glow: _selectedVideo != null,
          ),
          child: _selectedVideo == null
              ? Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: PBTheme.accentGlow,
                        shape: BoxShape.circle,
                      ),
                      child: const Icon(Icons.videocam_outlined,
                          color: PBTheme.accent, size: 32),
                    ),
                    const SizedBox(height: 12),
                    const Text('Adaugă video sprint',
                        style: TextStyle(
                            color: PBTheme.accent,
                            fontWeight: FontWeight.w600)),
                    const SizedBox(height: 4),
                    const Text('MP4 / MOV — max 2 minute',
                        style: TextStyle(color: PBTheme.textDim, fontSize: 12)),
                  ],
                )
              : Stack(
                  children: [
                    Center(
                      child: Icon(Icons.check_circle,
                          color: PBTheme.green, size: 48),
                    ),
                    Positioned(
                      bottom: 12,
                      left: 12,
                      right: 12,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 12, vertical: 8),
                        decoration: BoxDecoration(
                          color: Colors.black54,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Row(children: [
                          const Icon(Icons.videocam,
                              color: PBTheme.accent, size: 16),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              _selectedVideo!.path.split('/').last,
                              style: const TextStyle(
                                  color: PBTheme.textPrimary, fontSize: 12),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          const SizedBox(width: 8),
                          GestureDetector(
                            onTap: () => setState(() => _selectedVideo = null),
                            child: const Icon(Icons.close,
                                color: PBTheme.textSecondary, size: 18),
                          ),
                        ]),
                      ),
                    ),
                  ],
                ),
        ),
      );

  Widget _buildOptions() => Container(
        padding: const EdgeInsets.all(16),
        decoration: PBTheme.cardDecor(),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Opțiuni',
                style: TextStyle(
                    color: PBTheme.textSecondary,
                    fontSize: 12,
                    fontWeight: FontWeight.w600)),
            const SizedBox(height: 12),
            Row(children: [
              Expanded(
                child: _optionChip('🇷🇴 Română', _lang == 'ro',
                    () => setState(() => _lang = 'ro')),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _optionChip('🇬🇧 English', _lang == 'en',
                    () => setState(() => _lang = 'en')),
              ),
            ]),
            const SizedBox(height: 12),
            Row(children: [
              const Text('Slow motion output:',
                  style: TextStyle(color: PBTheme.textSecondary, fontSize: 13)),
              const SizedBox(width: 8),
              Expanded(
                child: DropdownButton<double>(
                  value: _slowmoFps,
                  dropdownColor: PBTheme.surface,
                  style: const TextStyle(color: PBTheme.textPrimary),
                  underline: const SizedBox(),
                  items: const [
                    DropdownMenuItem(value: 0.0, child: Text('Normal')),
                    DropdownMenuItem(value: 10.0, child: Text('10fps (slow)')),
                    DropdownMenuItem(value: 5.0, child: Text('5fps (x-slow)')),
                  ],
                  onChanged: (v) => setState(() => _slowmoFps = v ?? 0.0),
                ),
              ),
            ]),
          ],
        ),
      );

  Widget _optionChip(String label, bool selected, VoidCallback onTap) =>
      GestureDetector(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 10),
          decoration: BoxDecoration(
            color: selected ? PBTheme.accentGlow : PBTheme.surface,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(
              color: selected ? PBTheme.accent : PBTheme.border,
            ),
          ),
          child: Center(
            child: Text(label,
                style: TextStyle(
                  color: selected ? PBTheme.accent : PBTheme.textSecondary,
                  fontWeight: FontWeight.w600,
                  fontSize: 13,
                )),
          ),
        ),
      );

  Widget _buildAnalyzeButton() {
    // Dezactivat in timpul upload-ului SAU in timpul polling-ului
    // (previne crearea de joburi duplicate)
    final isActive = _isUploading ||
        (_currentJobId != null && !(_jobStatus?.isError ?? false));
    final canSubmit =
        _selectedVideo != null && _selectedAthlete != null && !isActive;

    return ElevatedButton(
      onPressed: canSubmit ? _submitAnalysis : null,
      style: ElevatedButton.styleFrom(
        backgroundColor: canSubmit ? PBTheme.accent : PBTheme.border,
        foregroundColor: canSubmit ? Colors.black : PBTheme.textDim,
        minimumSize: const Size(double.infinity, 56),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      ),
      child: isActive
          ? const Row(mainAxisAlignment: MainAxisAlignment.center, children: [
              SizedBox(
                  height: 22,
                  width: 22,
                  child: CircularProgressIndicator(
                      color: Colors.black, strokeWidth: 2.5)),
              SizedBox(width: 10),
              Text('Se procesează...',
                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
            ])
          : const Row(mainAxisAlignment: MainAxisAlignment.center, children: [
              Icon(Icons.bolt, size: 22),
              SizedBox(width: 8),
              Text('Analizează',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
            ]),
    ).animate(target: canSubmit ? 1 : 0).shimmer(duration: 2.seconds);
  }

  Widget _buildProgressCard() {
    final status = _jobStatus;
    final progress = (status?.progress ?? 0) / 100.0;
    final msg = status?.message ?? 'Se încarcă...';
    final isDone = status?.isDone ?? false;

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: PBTheme.cardDecor(glow: true),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            if (!isDone)
              const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(
                      color: PBTheme.accent, strokeWidth: 2)),
            if (isDone)
              const Icon(Icons.check_circle, color: PBTheme.green, size: 20),
            const SizedBox(width: 12),
            Expanded(
              child: Text(msg,
                  style: const TextStyle(
                      color: PBTheme.textPrimary, fontWeight: FontWeight.w600)),
            ),
            Text('${status?.progress ?? 0}%',
                style: const TextStyle(
                    color: PBTheme.accent, fontWeight: FontWeight.w700)),
          ]),
          const SizedBox(height: 14),
          LinearPercentIndicator(
            lineHeight: 6,
            percent: progress.clamp(0.0, 1.0),
            backgroundColor: PBTheme.border,
            progressColor: isDone ? PBTheme.green : PBTheme.accent,
            barRadius: const Radius.circular(4),
            padding: EdgeInsets.zero,
            animation: true,
            animateFromLastPercent: true,
          ),
          const SizedBox(height: 10),
          const Text(
            'Analiza rulează pe server. Poți lăsa aplicația deschisă.',
            style: TextStyle(color: PBTheme.textDim, fontSize: 11),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorCard() => Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: PBTheme.red.withOpacity(0.08),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: PBTheme.red.withOpacity(0.3)),
        ),
        child: Row(children: [
          const Icon(Icons.error_outline, color: PBTheme.red, size: 20),
          const SizedBox(width: 12),
          Expanded(
            child: Text(_errorMessage!,
                style: const TextStyle(color: PBTheme.red, fontSize: 13)),
          ),
          IconButton(
            icon: const Icon(Icons.refresh, color: PBTheme.accent, size: 20),
            onPressed: () => setState(() {
              _errorMessage = null;
              _currentJobId = null;
              _jobStatus = null;
            }),
          ),
        ]),
      );
}
