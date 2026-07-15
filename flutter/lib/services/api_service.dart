// lib/services/api_service.dart
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import '../models/job_model.dart';
import '../models/athlete_model.dart';

class ApiService {
  // Schimba cu URL-ul serverului tau cand faci deploy
  static String baseUrl = const String.fromEnvironment(
    'API_URL',
    defaultValue: 'http://10.103.86.146:8000',
  );

  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;
  ApiService._internal();

  // ─── Health check ───────────────────────────────────────────────────────
  Future<bool> isOnline() async {
    try {
      final r = await http
          .get(Uri.parse('$baseUrl/health'))
          .timeout(const Duration(seconds: 10));
      return r.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  // ─── Analiza video ──────────────────────────────────────────────────────
  Future<AnalysisJob> submitVideo({
    required File videoFile,
    required String athleteName,
    required double heightCm,
    required double weightKg,
    required int age,
    String lang = 'ro',
    double slowmoFps = 0.0,
    void Function(double)? onProgress,
  }) async {
    final uri = Uri.parse('$baseUrl/analyze');
    final req = http.MultipartRequest('POST', uri);

    req.fields['athlete_name'] = athleteName;
    req.fields['height_cm'] = heightCm.toString();
    req.fields['weight_kg'] = weightKg.toString();
    req.fields['age'] = age.toString();
    req.fields['lang'] = lang;
    req.fields['slowmo_fps'] = slowmoFps.toString();

    req.files.add(await http.MultipartFile.fromPath('video', videoFile.path));

    final streamed = await req.send().timeout(const Duration(minutes: 5));
    final body = await http.Response.fromStream(streamed);

    if (body.statusCode != 200) {
      final err = jsonDecode(body.body);
      throw ApiException(err['detail'] ?? 'Eroare upload video');
    }

    final data = jsonDecode(body.body);
    return AnalysisJob.fromJson(data);
  }

  // ─── Poll status ────────────────────────────────────────────────────────
  Future<JobStatus> getJobStatus(String jobId) async {
    final r = await http
        .get(Uri.parse('$baseUrl/status/$jobId'))
        .timeout(const Duration(seconds: 30));
    if (r.statusCode == 404) throw ApiException('Job negasit: $jobId');
    if (r.statusCode != 200)
      throw ApiException('Eroare server: ${r.statusCode}');
    return JobStatus.fromJson(jsonDecode(r.body));
  }

  // ─── Rezultate complete ─────────────────────────────────────────────────
  Future<AnalysisResult> getResult(String jobId) async {
    final r = await http
        .get(Uri.parse('$baseUrl/result/$jobId'))
        .timeout(const Duration(seconds: 30));
    if (r.statusCode != 200) {
      final err = jsonDecode(r.body);
      throw ApiException(err['detail'] ?? 'Eroare la rezultate');
    }
    return AnalysisResult.fromJson(jsonDecode(r.body));
  }

  // ─── Download fisier ────────────────────────────────────────────────────
  Future<File> downloadFile(
    String jobId,
    String fileKey,
    String savePath,
  ) async {
    final uri = Uri.parse('$baseUrl/download/$jobId/$fileKey');
    final r = await http.get(uri).timeout(const Duration(minutes: 5));
    if (r.statusCode != 200) throw ApiException('Fisier indisponibil');
    final file = File(savePath);
    await file.writeAsBytes(r.bodyBytes);
    return file;
  }

  // ─── Atleti ─────────────────────────────────────────────────────────────
  Future<List<Athlete>> getAthletes() async {
    final r = await http
        .get(Uri.parse('$baseUrl/athletes'))
        .timeout(const Duration(seconds: 15));
    if (r.statusCode != 200) throw ApiException('Eroare la lista atleți');
    final data = jsonDecode(r.body);
    return (data['athletes'] as List).map((a) => Athlete.fromJson(a)).toList();
  }

  Future<Athlete> createAthlete(Athlete athlete) async {
    final r = await http
        .post(
          Uri.parse('$baseUrl/athletes'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode(athlete.toJson()),
        )
        .timeout(const Duration(seconds: 15));
    if (r.statusCode != 200) throw ApiException('Eroare la salvare atlet');
    return Athlete.fromJson(jsonDecode(r.body));
  }

  Future<Athlete> updateAthlete(String id, Athlete athlete) async {
    final r = await http
        .put(
          Uri.parse('$baseUrl/athletes/$id'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode(athlete.toJson()),
        )
        .timeout(const Duration(seconds: 15));
    if (r.statusCode != 200) throw ApiException('Eroare la update atlet');
    return Athlete.fromJson(jsonDecode(r.body));
  }

  Future<void> deleteAthlete(String id) async {
    await http
        .delete(Uri.parse('$baseUrl/athletes/$id'))
        .timeout(const Duration(seconds: 15));
  }

  // ─── URL direct pentru video (pentru VideoPlayer) ───────────────────────
  String videoUrl(String jobId) => '$baseUrl/download/$jobId/video';
  String pdfUrl(String jobId) => '$baseUrl/download/$jobId/pdf';
  String htmlUrl(String jobId) => '$baseUrl/download/$jobId/html';
}

class ApiException implements Exception {
  final String message;
  ApiException(this.message);
  @override
  String toString() => message;
}
