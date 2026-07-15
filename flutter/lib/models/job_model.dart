// lib/models/job_model.dart

class AnalysisJob {
  final String jobId;
  final String status;
  final String message;
  final String pollUrl;

  AnalysisJob({
    required this.jobId,
    required this.status,
    required this.message,
    required this.pollUrl,
  });

  factory AnalysisJob.fromJson(Map<String, dynamic> j) => AnalysisJob(
    jobId: j['job_id'] ?? '',
    status: j['status'] ?? '',
    message: j['message'] ?? '',
    pollUrl: j['poll_url'] ?? '',
  );
}

class JobStatus {
  final String jobId;
  final String status; // queued | processing | done | error
  final int progress; // 0-100
  final String message;
  final String createdAt;
  final String finishedAt;

  JobStatus({
    required this.jobId,
    required this.status,
    required this.progress,
    required this.message,
    required this.createdAt,
    required this.finishedAt,
  });

  factory JobStatus.fromJson(Map<String, dynamic> j) => JobStatus(
    jobId: j['job_id'] ?? '',
    status: j['status'] ?? 'unknown',
    progress: j['progress'] ?? 0,
    message: j['message'] ?? '',
    createdAt: j['created_at'] ?? '',
    finishedAt: j['finished_at'] ?? '',
  );

  bool get isQueued => status == 'queued';
  bool get isProcessing => status == 'processing';
  bool get isDone => status == 'done';
  bool get isError => status == 'error';
  bool get isActive => isQueued || isProcessing;
}

class AnalysisResult {
  final String jobId;
  final Map<String, String> downloadUrls;
  final Map<String, AngleMetric> metrics;
  final Map<String, PhaseStats> phaseStats;
  final Map<String, dynamic> mlProfile;
  final int totalFrames;
  final List<Map<String, dynamic>> framesSample;
  final Map<String, dynamic> params;
  final String createdAt;
  final String finishedAt;

  AnalysisResult({
    required this.jobId,
    required this.downloadUrls,
    required this.metrics,
    required this.phaseStats,
    required this.mlProfile,
    required this.totalFrames,
    required this.framesSample,
    required this.params,
    required this.createdAt,
    required this.finishedAt,
  });

  factory AnalysisResult.fromJson(Map<String, dynamic> j) {
    final rawMetrics = j['metrics'] as Map<String, dynamic>? ?? {};
    final rawPhases = j['phase_stats'] as Map<String, dynamic>? ?? {};
    final rawUrls = j['download_urls'] as Map<String, dynamic>? ?? {};
    final rawFrames = j['frames_sample'] as List<dynamic>? ?? [];

    return AnalysisResult(
      jobId: j['job_id'] ?? '',
      createdAt: j['created_at'] ?? '',
      finishedAt: j['finished_at'] ?? '',
      totalFrames: j['total_frames'] ?? 0,
      framesSample: rawFrames
      .map((e) => Map<String, dynamic>.from(e as Map))
      .toList(),
      params: j['params'] ?? {},
      mlProfile: j['ml_profile'] ?? {},
      downloadUrls: rawUrls.map((k, v) => MapEntry(k, v.toString())),
      metrics: rawMetrics.map(
        (k, v) => MapEntry(k, AngleMetric.fromJson(v as Map<String, dynamic>)),
      ),
      phaseStats: rawPhases.map(
        (k, v) => MapEntry(k, PhaseStats.fromJson(v as Map<String, dynamic>)),
      ),
    );
  }

  String get athleteName => params['athlete_name'] ?? 'Atlet';
  double get heightCm => (params['height_cm'] ?? 184).toDouble();
  double get weightKg => (params['weight_kg'] ?? 82).toDouble();
  int get age => (params['age'] ?? 21).toInt();

  bool get hasVideo => downloadUrls.containsKey('video');
  bool get hasPdf => downloadUrls.containsKey('pdf');
  bool get hasDashboard => downloadUrls.containsKey('html');
  bool get hasChart => downloadUrls.containsKey('chart');
  bool get hasSymmetry => downloadUrls.containsKey('symmetry');
}

class AngleMetric {
  final double mean;
  final double min;
  final double max;
  final double std;

  AngleMetric({
    required this.mean,
    required this.min,
    required this.max,
    required this.std,
  });

  factory AngleMetric.fromJson(Map<String, dynamic> j) => AngleMetric(
    mean: (j['mean'] ?? 0).toDouble(),
    min: (j['min'] ?? 0).toDouble(),
    max: (j['max'] ?? 0).toDouble(),
    std: (j['std'] ?? 0).toDouble(),
  );
}

class PhaseStats {
  final int frameCount;

  PhaseStats({required this.frameCount});

  factory PhaseStats.fromJson(Map<String, dynamic> j) =>
      PhaseStats(frameCount: j['frame_count'] ?? 0);
}
