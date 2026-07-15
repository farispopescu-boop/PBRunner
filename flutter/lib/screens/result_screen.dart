// lib/screens/result_screen.dart
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:url_launcher/url_launcher.dart';
import '../theme.dart';
import '../models/job_model.dart';
import '../services/api_service.dart';
import '../widgets/phase_badge.dart';
import '../widgets/angle_chart.dart';
import '../widgets/metric_card.dart';

class ResultScreen extends StatefulWidget {
  final AnalysisResult result;
  final String jobId;

  const ResultScreen({super.key, required this.result, required this.jobId});

  @override
  State<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends State<ResultScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  VideoPlayerController? _videoController;
  bool _videoLoading = true;
  bool _videoError = false;
  File? _downloadedVideo;
  final _api = ApiService();

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _initVideo();
  }

  @override
  void dispose() {
    _tabController.dispose();
    _videoController?.dispose();
    super.dispose();
  }

  Future<void> _initVideo() async {
    if (!widget.result.hasVideo) {
      debugPrint(
          'VIDEO: hasVideo=false, downloadUrls=${widget.result.downloadUrls}');
      setState(() {
        _videoLoading = false;
        _videoError = true;
      });
      return;
    }

    try {
      final dir = await getTemporaryDirectory();
      final path = '${dir.path}/pbrunner_${widget.jobId}.mp4';

      // Daca fisierul exista deja local, nu il mai descarcam
      final existing = File(path);
      File videoFile;
      if (await existing.exists()) {
        videoFile = existing;
        debugPrint('VIDEO: folosesc fisier local cached');
      } else {
        debugPrint('VIDEO: descarc de pe server...');
        videoFile = await _api.downloadFile(widget.jobId, 'video', path);
        debugPrint('VIDEO: descarcat ${videoFile.lengthSync()} bytes');
      }

      _videoController = VideoPlayerController.file(videoFile);
      await _videoController!.initialize();
      debugPrint(
          'VIDEO: initializat OK, durata=${_videoController!.value.duration}');

      if (mounted) {
        setState(() {
          _videoLoading = false;
          _downloadedVideo = videoFile;
        });
      }
    } catch (e) {
      debugPrint('VIDEO ERROR: $e');
      setState(() {
        _videoLoading = false;
        _videoError = true;
      });
    }
  }

  Future<void> _shareResult() async {
    final files = <XFile>[];
    if (_downloadedVideo != null) files.add(XFile(_downloadedVideo!.path));
    Share.shareXFiles(
      files,
      text: 'Analiza PBRunner — ${widget.result.athleteName}\n'
          'Generat cu PBRunner (IAAF Elite Template)',
    );
  }

  Future<void> _openDashboard() async {
    if (!widget.result.hasDashboard) return;
    final url = '${ApiService.baseUrl}/download/${widget.jobId}/html';
    await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
  }

  Future<void> _downloadPdf() async {
    if (!widget.result.hasPdf) return;
    try {
      final dir = await getApplicationDocumentsDirectory();
      final path = '${dir.path}/pbrunner_${widget.jobId}.pdf';
      await _api.downloadFile(widget.jobId, 'pdf', path);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('PDF salvat în: $path'),
            backgroundColor: PBTheme.surface,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Eroare la descărcare PDF'),
            backgroundColor: PBTheme.red,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: PBTheme.bg,
      body: NestedScrollView(
        headerSliverBuilder: (ctx, _) => [
          SliverAppBar(
            expandedHeight: 280,
            pinned: true,
            backgroundColor: PBTheme.bg,
            actions: [
              IconButton(
                icon: const Icon(Icons.share_outlined),
                onPressed: _shareResult,
              ),
              IconButton(
                icon: const Icon(Icons.open_in_browser_outlined),
                onPressed: _openDashboard,
                tooltip: 'Dashboard HTML',
              ),
            ],
            flexibleSpace: FlexibleSpaceBar(background: _buildVideoPlayer()),
          ),
          SliverToBoxAdapter(child: _buildHeader()),
          SliverPersistentHeader(
            pinned: true,
            delegate: _TabBarDelegate(
              TabBar(
                controller: _tabController,
                indicatorColor: PBTheme.accent,
                labelColor: PBTheme.accent,
                unselectedLabelColor: PBTheme.textDim,
                tabs: const [
                  Tab(text: 'Metrici'),
                  Tab(text: 'Unghiuri'),
                  Tab(text: 'Acțiuni'),
                ],
              ),
            ),
          ),
        ],
        body: TabBarView(
          controller: _tabController,
          children: [_buildMetricsTab(), _buildAnglesTab(), _buildActionsTab()],
        ),
      ),
    );
  }

  Widget _buildVideoPlayer() {
    if (_videoLoading) {
      return Container(
        color: Colors.black,
        child: const Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              CircularProgressIndicator(color: PBTheme.accent),
              SizedBox(height: 12),
              Text(
                'Se descarcă video...',
                style: TextStyle(color: PBTheme.textSecondary),
              ),
            ],
          ),
        ),
      );
    }
    if (_videoError || _videoController == null) {
      return Container(
        color: Colors.black,
        child: const Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                Icons.videocam_off_outlined,
                color: PBTheme.textDim,
                size: 48,
              ),
              SizedBox(height: 8),
              Text(
                'Video indisponibil',
                style: TextStyle(color: PBTheme.textDim),
              ),
            ],
          ),
        ),
      );
    }

    return GestureDetector(
      onTap: () {
        setState(() {
          _videoController!.value.isPlaying
              ? _videoController!.pause()
              : _videoController!.play();
        });
      },
      child: Stack(
        alignment: Alignment.center,
        children: [
          Container(color: Colors.black),
          AspectRatio(
            aspectRatio: _videoController!.value.aspectRatio,
            child: VideoPlayer(_videoController!),
          ),
          if (!_videoController!.value.isPlaying)
            Container(
              padding: const EdgeInsets.all(14),
              decoration: const BoxDecoration(
                color: Colors.black54,
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.play_arrow,
                color: Colors.white,
                size: 36,
              ),
            ),
          Positioned(
            bottom: 0,
            left: 0,
            right: 0,
            child: VideoProgressIndicator(
              _videoController!,
              allowScrubbing: true,
              colors: const VideoProgressColors(
                playedColor: PBTheme.accent,
                bufferedColor: Colors.white24,
                backgroundColor: Colors.white10,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader() {
    final r = widget.result;
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      r.athleteName,
                      style: const TextStyle(
                        color: PBTheme.textPrimary,
                        fontWeight: FontWeight.w800,
                        fontSize: 22,
                      ),
                    ),
                    Text(
                      '${r.heightCm.toStringAsFixed(0)}cm  '
                      '${r.weightKg.toStringAsFixed(0)}kg  '
                      '${r.age} ani  |  '
                      '${r.totalFrames} frame-uri',
                      style: const TextStyle(
                        color: PBTheme.textSecondary,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          // Faze detectate
          if (r.phaseStats.isNotEmpty)
            Wrap(
              spacing: 8,
              children: r.phaseStats.keys
                  .map(
                    (ph) => PhaseBadge(
                      phase: ph,
                      frames: r.phaseStats[ph]!.frameCount,
                    ),
                  )
                  .toList(),
            ),
          const SizedBox(height: 12),
        ],
      ),
    );
  }

  Widget _buildMetricsTab() {
    final metrics = widget.result.metrics;
    if (metrics.isEmpty) {
      return const Center(
        child: Text('Fără date', style: TextStyle(color: PBTheme.textDim)),
      );
    }

    final order = [
      'trunk',
      'knee_L',
      'knee_R',
      'hip_L',
      'hip_R',
      'ankle_L',
      'ankle_R',
      'elbow_L',
      'elbow_R',
    ];
    final names = {
      'trunk': 'Trunchi',
      'knee_L': 'Genunchi STG',
      'knee_R': 'Genunchi DRP',
      'hip_L': 'Sold STG',
      'hip_R': 'Sold DRP',
      'ankle_L': 'Gleznă STG',
      'ankle_R': 'Gleznă DRP',
      'elbow_L': 'Cot STG',
      'elbow_R': 'Cot DRP',
    };

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Simetrie top
        _buildSymmetryRow(metrics),
        const SizedBox(height: 16),
        // Metrici individuale
        ...order.where((k) => metrics.containsKey(k)).map(
              (k) => Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: MetricCard(
                  label: names[k] ?? k,
                  metric: metrics[k]!,
                  idealRange: _idealRange(k),
                ),
              ),
            ),
      ],
    );
  }

  Widget _buildSymmetryRow(Map<String, dynamic> metrics) {
    double kd = 0, ed = 0;
    if (metrics.containsKey('knee_L') && metrics.containsKey('knee_R')) {
      kd = (metrics['knee_L']!.mean - metrics['knee_R']!.mean).abs();
    }
    if (metrics.containsKey('elbow_L') && metrics.containsKey('elbow_R')) {
      ed = (metrics['elbow_L']!.mean - metrics['elbow_R']!.mean).abs();
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: PBTheme.cardDecor(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'SIMETRIE L/R',
            style: TextStyle(
              color: PBTheme.textSecondary,
              fontSize: 11,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(child: _symItem('Genunchi', kd)),
              const SizedBox(width: 12),
              Expanded(child: _symItem('Coate', ed)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _symItem(String label, double diff) {
    final ok = diff < 10;
    final mid = diff < 20;
    final col = ok ? PBTheme.green : (mid ? PBTheme.orange : PBTheme.red);
    return Column(
      children: [
        Text(
          '${diff.toStringAsFixed(1)}°',
          style: TextStyle(
            color: col,
            fontWeight: FontWeight.w800,
            fontSize: 22,
          ),
        ),
        Text(
          label,
          style: const TextStyle(color: PBTheme.textSecondary, fontSize: 11),
        ),
        Text(
          ok ? '✓ Simetric' : (mid ? '~ Asimetrie medie' : '✗ Asimetrie mare'),
          style: TextStyle(color: col, fontSize: 10),
        ),
      ],
    );
  }

  Widget _buildAnglesTab() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        AngleChart(
          title: 'Genunchi STG vs DRP',
          leftKey: 'knee_L',
          rightKey: 'knee_R',
          frames: widget.result.framesSample,
        ),
        const SizedBox(height: 16),
        AngleChart(
          title: 'Sold STG vs DRP',
          leftKey: 'hip_L',
          rightKey: 'hip_R',
          frames: widget.result.framesSample,
        ),
        const SizedBox(height: 16),
        AngleChart(
          title: 'Cot STG vs DRP',
          leftKey: 'elbow_L',
          rightKey: 'elbow_R',
          frames: widget.result.framesSample,
        ),
      ],
    );
  }

  Widget _buildActionsTab() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _actionCard(
          icon: Icons.picture_as_pdf_outlined,
          title: 'Descarcă Raport PDF',
          subtitle: 'Raport complet cu comparație IAAF',
          color: PBTheme.red,
          onTap: _downloadPdf,
          available: widget.result.hasPdf,
        ),
        const SizedBox(height: 12),
        _actionCard(
          icon: Icons.open_in_browser_outlined,
          title: 'Dashboard Interactiv',
          subtitle: 'Grafice interactive în browser',
          color: PBTheme.accent,
          onTap: _openDashboard,
          available: widget.result.hasDashboard,
        ),
        const SizedBox(height: 12),
        _actionCard(
          icon: Icons.share_outlined,
          title: 'Distribuie Video Analizat',
          subtitle: 'Trimite video cu overlay roșu/verde',
          color: PBTheme.green,
          onTap: _shareResult,
          available: _downloadedVideo != null,
        ),
        const SizedBox(height: 24),
        // ML Profile
        if (widget.result.mlProfile.isNotEmpty) _buildMlCard(),
      ],
    );
  }

  Widget _actionCard({
    required IconData icon,
    required String title,
    required String subtitle,
    required Color color,
    required VoidCallback onTap,
    required bool available,
  }) =>
      Opacity(
        opacity: available ? 1.0 : 0.4,
        child: GestureDetector(
          onTap: available ? onTap : null,
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: PBTheme.cardDecor(),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: color.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(icon, color: color, size: 24),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: const TextStyle(
                          color: PBTheme.textPrimary,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      Text(
                        subtitle,
                        style: const TextStyle(
                          color: PBTheme.textSecondary,
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ),
                ),
                Icon(Icons.chevron_right, color: color.withOpacity(0.6)),
              ],
            ),
          ),
        ),
      );

  Widget _buildMlCard() {
    final ml = widget.result.mlProfile;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: PBTheme.cardDecor(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.psychology_outlined, color: PBTheme.accent, size: 18),
              SizedBox(width: 8),
              Text(
                'Profil ML Atlet',
                style: TextStyle(
                  color: PBTheme.textPrimary,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (ml['cluster_names'] != null)
            Text(
              'Cluster: ${ml['cluster_names']}',
              style: const TextStyle(
                color: PBTheme.textSecondary,
                fontSize: 13,
              ),
            ),
        ],
      ),
    );
  }

  Map<double, double>? _idealRange(String key) {
    const ranges = {
      'trunk': [0.0, 25.0],
      'knee_L': [100.0, 120.0],
      'knee_R': [100.0, 120.0],
      'hip_L': [20.0, 45.0],
      'hip_R': [20.0, 45.0],
      'elbow_L': [80.0, 100.0],
      'elbow_R': [80.0, 100.0],
    };
    final r = ranges[key];
    if (r == null) return null;
    return {r[0]: r[1]};
  }
}

class _TabBarDelegate extends SliverPersistentHeaderDelegate {
  final TabBar tabBar;
  _TabBarDelegate(this.tabBar);

  @override
  double get minExtent => tabBar.preferredSize.height;
  @override
  double get maxExtent => tabBar.preferredSize.height;

  @override
  Widget build(_, __, ___) => Container(color: PBTheme.bg, child: tabBar);

  @override
  bool shouldRebuild(_TabBarDelegate old) => tabBar != old.tabBar;
}
