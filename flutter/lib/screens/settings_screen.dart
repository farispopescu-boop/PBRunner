// lib/screens/settings_screen.dart
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../theme.dart';
import '../services/api_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _urlController = TextEditingController();
  bool _testing = false;
  bool? _online;

  @override
  void initState() {
    super.initState();
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    final prefs = await SharedPreferences.getInstance();
    final url = prefs.getString('api_url') ?? 'http://localhost:8000';
    setState(() {
      _urlController.text = url;
      ApiService.baseUrl = url;
    });
  }

  Future<void> _saveUrl() async {
    final url = _urlController.text.trim();
    if (url.isEmpty) return;
    ApiService.baseUrl = url;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('api_url', url);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('URL salvat'),
          backgroundColor: PBTheme.surface,
        ),
      );
    }
  }

  Future<void> _testConnection() async {
    setState(() {
      _testing = true;
      _online = null;
    });
    final ok = await ApiService().isOnline();
    setState(() {
      _testing = false;
      _online = ok;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: PBTheme.bg,
      appBar: AppBar(title: const Text('Setări')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Server URL
          Container(
            padding: const EdgeInsets.all(16),
            decoration: PBTheme.cardDecor(),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Row(
                  children: [
                    Icon(Icons.dns_outlined, color: PBTheme.accent, size: 18),
                    SizedBox(width: 8),
                    Text(
                      'Server API',
                      style: TextStyle(
                        color: PBTheme.textPrimary,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                const Text(
                  'Introdu URL-ul serverului PBRunner. Exemplu:\n'
                  'https://pbrunner.railway.app',
                  style: TextStyle(color: PBTheme.textSecondary, fontSize: 12),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _urlController,
                  style: const TextStyle(color: PBTheme.textPrimary),
                  decoration: const InputDecoration(
                    labelText: 'URL server',
                    hintText: 'https://...',
                    prefixIcon: Icon(Icons.link, color: PBTheme.textDim),
                  ),
                  onSubmitted: (_) => _saveUrl(),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: _testing ? null : _testConnection,
                        style: OutlinedButton.styleFrom(
                          foregroundColor: PBTheme.accent,
                          side: const BorderSide(color: PBTheme.accent),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(10),
                          ),
                        ),
                        child: _testing
                            ? const SizedBox(
                                height: 18,
                                width: 18,
                                child: CircularProgressIndicator(
                                  color: PBTheme.accent,
                                  strokeWidth: 2,
                                ),
                              )
                            : const Text('Testează'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: ElevatedButton(
                        onPressed: _saveUrl,
                        child: const Text('Salvează'),
                      ),
                    ),
                  ],
                ),
                if (_online != null) ...[
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      Icon(
                        _online! ? Icons.check_circle : Icons.cancel,
                        color: _online! ? PBTheme.green : PBTheme.red,
                        size: 18,
                      ),
                      const SizedBox(width: 8),
                      Text(
                        _online!
                            ? 'Server online ✓'
                            : 'Server offline sau URL greșit',
                        style: TextStyle(
                          color: _online! ? PBTheme.green : PBTheme.red,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(height: 16),

          // Info app
          Container(
            padding: const EdgeInsets.all(16),
            decoration: PBTheme.cardDecor(),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Row(
                  children: [
                    Icon(Icons.info_outline, color: PBTheme.accent, size: 18),
                    SizedBox(width: 8),
                    Text(
                      'Despre PBRunner',
                      style: TextStyle(
                        color: PBTheme.textPrimary,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                _infoRow('Versiune', '1.0.0'),
                _infoRow('Template', 'IAAF London 2017'),
                _infoRow('Referință', 'Simbine / Prescod / Blake'),
                _infoRow('Limbă analiză', 'Română / English'),
              ],
            ),
          ),

          const SizedBox(height: 16),
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 8),
            child: Text(
              'Sursa datelor: IAAF Biomechanics Research Project\n'
              '100m Men Final, World Championships London 2017\n'
              'Carnegie School of Sport',
              style: TextStyle(color: PBTheme.textDim, fontSize: 11),
              textAlign: TextAlign.center,
            ),
          ),
        ],
      ),
    );
  }

  Widget _infoRow(String label, String value) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 4),
    child: Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: const TextStyle(color: PBTheme.textSecondary, fontSize: 13),
        ),
        Text(
          value,
          style: const TextStyle(
            color: PBTheme.textPrimary,
            fontSize: 13,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    ),
  );
}
