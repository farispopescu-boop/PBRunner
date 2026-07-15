// lib/models/athlete_model.dart

class Athlete {
  final String id;
  final String name;
  final double heightCm;
  final double weightKg;
  final int age;
  final String sport;
  final String notes;
  final String createdAt;

  Athlete({
    this.id = '',
    required this.name,
    required this.heightCm,
    required this.weightKg,
    required this.age,
    this.sport = 'sprint_100m',
    this.notes = '',
    this.createdAt = '',
  });

  factory Athlete.fromJson(Map<String, dynamic> j) => Athlete(
    id: j['id'] ?? '',
    name: j['name'] ?? '',
    heightCm: (j['height_cm'] ?? 184).toDouble(),
    weightKg: (j['weight_kg'] ?? 82).toDouble(),
    age: (j['age'] ?? 21).toInt(),
    sport: j['sport'] ?? 'sprint_100m',
    notes: j['notes'] ?? '',
    createdAt: j['created_at'] ?? '',
  );

  Map<String, dynamic> toJson() => {
    'name': name,
    'height_cm': heightCm,
    'weight_kg': weightKg,
    'age': age,
    'sport': sport,
    'notes': notes,
  };

  Athlete copyWith({
    String? id,
    String? name,
    double? heightCm,
    double? weightKg,
    int? age,
    String? sport,
    String? notes,
  }) => Athlete(
    id: id ?? this.id,
    name: name ?? this.name,
    heightCm: heightCm ?? this.heightCm,
    weightKg: weightKg ?? this.weightKg,
    age: age ?? this.age,
    sport: sport ?? this.sport,
    notes: notes ?? this.notes,
  );

  String get bmiStr {
    final bmi = weightKg / ((heightCm / 100) * (heightCm / 100));
    return bmi.toStringAsFixed(1);
  }

  String get initials => name.isNotEmpty
      ? name.trim().split(' ').map((w) => w[0]).take(2).join().toUpperCase()
      : '?';
}
