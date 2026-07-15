// lib/screens/athletes_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../main.dart' show athletesRefreshBus;
import '../theme.dart';
import '../models/athlete_model.dart';
import '../services/api_service.dart';

class AthletesScreen extends StatefulWidget {
  final bool selectionMode;
  const AthletesScreen({super.key, this.selectionMode = false});

  @override
  State<AthletesScreen> createState() => _AthletesScreenState();
}

class _AthletesScreenState extends State<AthletesScreen> {
  List<Athlete> _athletes = [];
  bool _loading = true;
  final _api = ApiService();

  @override
  void initState() {
    super.initState();
    _loadAthletes();
    athletesRefreshBus.addListener(_onRefreshSignal);
  }

  @override
  void dispose() {
    athletesRefreshBus.removeListener(_onRefreshSignal);
    super.dispose();
  }

  void _onRefreshSignal() {
    if (mounted) _loadAthletes();
  }

  Future<void> _loadAthletes() async {
    try {
      final list = await _api.getAthletes();
      setState(() {
        _athletes = list;
        _loading = false;
      });
    } catch (e) {
      setState(() => _loading = false);
    }
  }

  Future<void> _showAthleteDialog({Athlete? athlete}) async {
    final nameC = TextEditingController(text: athlete?.name ?? '');
    final heightC = TextEditingController(
        text: athlete?.heightCm.toStringAsFixed(0) ?? '184');
    final weightC = TextEditingController(
        text: athlete?.weightKg.toStringAsFixed(0) ?? '82');
    final ageC = TextEditingController(text: athlete?.age.toString() ?? '21');
    final notesC = TextEditingController(text: athlete?.notes ?? '');

    final saved = await showModalBottomSheet<Athlete>(
      context: context,
      isScrollControlled: true,
      backgroundColor: PBTheme.surface,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(24))),
      builder: (ctx) => Padding(
        padding: EdgeInsets.fromLTRB(
            20, 20, 20, MediaQuery.of(ctx).viewInsets.bottom + 20),
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: PBTheme.border,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 20),
              Text(
                athlete == null ? 'Atlet nou' : 'Editează atlet',
                style: const TextStyle(
                    color: PBTheme.textPrimary,
                    fontWeight: FontWeight.w800,
                    fontSize: 20),
              ),
              const SizedBox(height: 20),
              _field(nameC, 'Nume atlet', Icons.person_outline),
              const SizedBox(height: 12),
              Row(children: [
                Expanded(child: _field(heightC, 'Înălțime (cm)', Icons.height)),
                const SizedBox(width: 12),
                Expanded(
                    child:
                        _field(weightC, 'Greutate (kg)', Icons.fitness_center)),
              ]),
              const SizedBox(height: 12),
              _field(ageC, 'Vârstă (ani)', Icons.cake_outlined),
              const SizedBox(height: 12),
              _field(notesC, 'Note (opțional)', Icons.notes_outlined,
                  maxLines: 2),
              const SizedBox(height: 20),
              ElevatedButton(
                onPressed: () {
                  if (nameC.text.trim().isEmpty) return;
                  Navigator.pop(
                    ctx,
                    Athlete(
                      id: athlete?.id ?? '',
                      name: nameC.text.trim(),
                      heightCm: double.tryParse(heightC.text) ?? 184,
                      weightKg: double.tryParse(weightC.text) ?? 82,
                      age: int.tryParse(ageC.text) ?? 21,
                      notes: notesC.text.trim(),
                    ),
                  );
                },
                child:
                    Text(athlete == null ? 'Salvează atlet' : 'Actualizează'),
              ),
            ],
          ),
        ),
      ),
    );

    if (saved == null) return;

    try {
      Athlete result;
      if (athlete == null || athlete.id.isEmpty) {
        result = await _api.createAthlete(saved);
      } else {
        result = await _api.updateAthlete(athlete.id, saved);
      }

      if (widget.selectionMode && mounted) {
        Navigator.pop(context, result);
        return;
      }

      await _loadAthletes();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Eroare: $e'), backgroundColor: PBTheme.red),
        );
      }
    }
  }

  Widget _field(TextEditingController c, String label, IconData icon,
          {int maxLines = 1}) =>
      TextField(
        controller: c,
        maxLines: maxLines,
        keyboardType: maxLines == 1 ? TextInputType.text : null,
        style: const TextStyle(color: PBTheme.textPrimary),
        decoration: InputDecoration(
          labelText: label,
          prefixIcon: Icon(icon, color: PBTheme.textDim, size: 20),
        ),
      );

  Future<void> _deleteAthlete(Athlete a) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: PBTheme.surface,
        title: const Text('Șterge atlet',
            style: TextStyle(color: PBTheme.textPrimary)),
        content: Text('Ștergi ${a.name}?',
            style: const TextStyle(color: PBTheme.textSecondary)),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Anulează')),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Șterge', style: TextStyle(color: PBTheme.red)),
          ),
        ],
      ),
    );
    if (confirm != true) return;
    try {
      await _api.deleteAthlete(a.id);
      await _loadAthletes();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Eroare: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: PBTheme.bg,
      appBar: AppBar(
        title: Text(widget.selectionMode ? 'Alege atlet' : 'Atleți'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_outlined),
            onPressed: _loadAthletes,
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _showAthleteDialog(),
        backgroundColor: PBTheme.accent,
        foregroundColor: Colors.black,
        icon: const Icon(Icons.add),
        label: const Text('Atlet nou',
            style: TextStyle(fontWeight: FontWeight.w700)),
      ),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: PBTheme.accent))
          : RefreshIndicator(
              color: PBTheme.accent,
              backgroundColor: PBTheme.surface,
              onRefresh: _loadAthletes,
              child: _athletes.isEmpty
                  ? ListView(
                      physics: const AlwaysScrollableScrollPhysics(),
                      children: [
                        SizedBox(
                            height: MediaQuery.of(context).size.height * 0.15),
                        _buildEmpty(),
                      ],
                    )
                  : ListView.separated(
                      padding: const EdgeInsets.fromLTRB(16, 16, 16, 100),
                      physics: const AlwaysScrollableScrollPhysics(),
                      itemCount: _athletes.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 10),
                      itemBuilder: (_, i) => _buildAthleteCard(_athletes[i], i),
                    ),
            ),
    );
  }

  Widget _buildEmpty() => Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: PBTheme.accentGlow,
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.directions_run,
                  color: PBTheme.accent, size: 48),
            ),
            const SizedBox(height: 20),
            const Text('Niciun atlet salvat',
                style: TextStyle(
                    color: PBTheme.textPrimary,
                    fontWeight: FontWeight.w700,
                    fontSize: 18)),
            const SizedBox(height: 8),
            const Text('Apasă + pentru a adăuga primul atlet',
                style: TextStyle(color: PBTheme.textSecondary)),
          ],
        ),
      );

  Widget _buildAthleteCard(Athlete a, int index) {
    return GestureDetector(
      onTap: () {
        if (widget.selectionMode) {
          Navigator.pop(context, a);
        } else {
          _showAthleteDialog(athlete: a);
        }
      },
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: PBTheme.cardDecor(),
        child: Row(children: [
          CircleAvatar(
            radius: 26,
            backgroundColor: PBTheme.accentGlow,
            child: Text(a.initials,
                style: const TextStyle(
                    color: PBTheme.accent, fontWeight: FontWeight.bold)),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(a.name,
                    style: const TextStyle(
                        color: PBTheme.textPrimary,
                        fontWeight: FontWeight.w700,
                        fontSize: 15)),
                const SizedBox(height: 4),
                Row(children: [
                  _stat('${a.heightCm.toStringAsFixed(0)}cm'),
                  _dot(),
                  _stat('${a.weightKg.toStringAsFixed(0)}kg'),
                  _dot(),
                  _stat('${a.age} ani'),
                  _dot(),
                  _stat('BMI ${a.bmiStr}'),
                ]),
                if (a.notes.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text(a.notes,
                      style:
                          const TextStyle(color: PBTheme.textDim, fontSize: 11),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis),
                ],
              ],
            ),
          ),
          if (!widget.selectionMode)
            PopupMenuButton<String>(
              color: PBTheme.surface,
              icon: const Icon(Icons.more_vert, color: PBTheme.textDim),
              onSelected: (v) {
                if (v == 'edit') _showAthleteDialog(athlete: a);
                if (v == 'delete') _deleteAthlete(a);
              },
              itemBuilder: (_) => [
                const PopupMenuItem(
                    value: 'edit',
                    child: Text('Editează',
                        style: TextStyle(color: PBTheme.textPrimary))),
                const PopupMenuItem(
                    value: 'delete',
                    child:
                        Text('Șterge', style: TextStyle(color: PBTheme.red))),
              ],
            ),
          if (widget.selectionMode)
            const Icon(Icons.chevron_right, color: PBTheme.accent),
        ]),
      ),
    ).animate(delay: (index * 60).ms).fadeIn().slideX(begin: 0.1);
  }

  Widget _stat(String text) => Text(text,
      style: const TextStyle(color: PBTheme.textSecondary, fontSize: 12));

  Widget _dot() => const Padding(
        padding: EdgeInsets.symmetric(horizontal: 4),
        child: Text('·', style: TextStyle(color: PBTheme.textDim)),
      );
}
