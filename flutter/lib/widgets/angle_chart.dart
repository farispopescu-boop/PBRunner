// lib/widgets/angle_chart.dart
import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import '../theme.dart';

class AngleChart extends StatelessWidget {
  final String title;
  final String leftKey;
  final String rightKey;
  final List<Map<String, dynamic>> frames;

  const AngleChart({
    super.key,
    required this.title,
    required this.leftKey,
    required this.rightKey,
    required this.frames,
  });

  @override
  Widget build(BuildContext context) {
    if (frames.isEmpty) {
      return Container(
        height: 140,
        padding: const EdgeInsets.all(16),
        decoration: PBTheme.cardDecor(),
        child: Center(
          child: Text(title, style: const TextStyle(color: PBTheme.textDim)),
        ),
      );
    }

    // Subsample la max 60 puncte pentru performanta
    final step = (frames.length / 60).ceil().clamp(1, 999);
    final sample = <Map<String, dynamic>>[];
    for (int i = 0; i < frames.length; i += step) {
      sample.add(frames[i]);
    }

    final leftSpots = <FlSpot>[];
    final rightSpots = <FlSpot>[];

    for (int i = 0; i < sample.length; i++) {
      final f = sample[i];
      final t = (f['time_s'] as num?)?.toDouble() ?? i.toDouble();
      final l = (f[leftKey] as num?)?.toDouble();
      final r = (f[rightKey] as num?)?.toDouble();
      if (l != null) leftSpots.add(FlSpot(t, l));
      if (r != null) rightSpots.add(FlSpot(t, r));
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: PBTheme.cardDecor(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                title,
                style: const TextStyle(
                  color: PBTheme.textPrimary,
                  fontWeight: FontWeight.w600,
                  fontSize: 13,
                ),
              ),
              Row(
                children: [
                  _legend('STG', const Color(0xFF00D4FF)),
                  const SizedBox(width: 12),
                  _legend('DRP', const Color(0xFFFF8C00)),
                ],
              ),
            ],
          ),
          const SizedBox(height: 12),
          SizedBox(
            height: 120,
            child: LineChart(
              LineChartData(
                backgroundColor: Colors.transparent,
                gridData: FlGridData(
                  show: true,
                  drawVerticalLine: false,
                  getDrawingHorizontalLine: (_) =>
                      const FlLine(color: PBTheme.border, strokeWidth: 1),
                ),
                titlesData: FlTitlesData(
                  leftTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      reservedSize: 32,
                      getTitlesWidget: (v, _) => Text(
                        v.toStringAsFixed(0),
                        style: const TextStyle(
                          color: PBTheme.textDim,
                          fontSize: 9,
                        ),
                      ),
                    ),
                  ),
                  bottomTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      reservedSize: 18,
                      getTitlesWidget: (v, _) => Text(
                        '${v.toStringAsFixed(1)}s',
                        style: const TextStyle(
                          color: PBTheme.textDim,
                          fontSize: 9,
                        ),
                      ),
                    ),
                  ),
                  topTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false),
                  ),
                  rightTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false),
                  ),
                ),
                borderData: FlBorderData(show: false),
                lineBarsData: [
                  if (leftSpots.isNotEmpty)
                    LineChartBarData(
                      spots: leftSpots,
                      isCurved: true,
                      color: const Color(0xFF00D4FF),
                      barWidth: 1.8,
                      dotData: const FlDotData(show: false),
                    ),
                  if (rightSpots.isNotEmpty)
                    LineChartBarData(
                      spots: rightSpots,
                      isCurved: true,
                      color: const Color(0xFFFF8C00),
                      barWidth: 1.8,
                      dotData: const FlDotData(show: false),
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _legend(String label, Color color) => Row(
    children: [
      Container(
        width: 12,
        height: 3,
        decoration: BoxDecoration(
          color: color,
          borderRadius: BorderRadius.circular(2),
        ),
      ),
      const SizedBox(width: 4),
      Text(label, style: TextStyle(color: color, fontSize: 11)),
    ],
  );
}
