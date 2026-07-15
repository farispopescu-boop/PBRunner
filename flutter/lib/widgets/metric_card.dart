// lib/widgets/metric_card.dart
import 'package:flutter/material.dart';
import 'package:percent_indicator/percent_indicator.dart';
import '../theme.dart';
import '../models/job_model.dart';

class MetricCard extends StatelessWidget {
  final String label;
  final AngleMetric metric;
  final Map<double, double>? idealRange; // {min: max}

  const MetricCard({
    super.key,
    required this.label,
    required this.metric,
    this.idealRange,
  });

  bool get inIdeal {
    if (idealRange == null) return true;
    final min = idealRange!.keys.first;
    final max = idealRange!.values.first;
    return metric.mean >= min && metric.mean <= max;
  }

  Color get statusColor {
    if (idealRange == null) return PBTheme.textSecondary;
    return inIdeal ? PBTheme.green : PBTheme.orange;
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: PBTheme.cardDecor(),
      child: Row(
        children: [
          // Indicator circular
          CircularPercentIndicator(
            radius: 28,
            lineWidth: 4,
            percent: (metric.mean / 180).clamp(0.0, 1.0),
            center: Text(
              metric.mean.toStringAsFixed(0),
              style: TextStyle(
                color: statusColor,
                fontWeight: FontWeight.w800,
                fontSize: 13,
              ),
            ),
            progressColor: statusColor,
            backgroundColor: PBTheme.border,
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: const TextStyle(
                    color: PBTheme.textPrimary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    _stat('min ${metric.min.toStringAsFixed(0)}°'),
                    const SizedBox(width: 10),
                    _stat('max ${metric.max.toStringAsFixed(0)}°'),
                    const SizedBox(width: 10),
                    _stat('±${metric.std.toStringAsFixed(1)}°'),
                  ],
                ),
                if (idealRange != null) ...[
                  const SizedBox(height: 4),
                  Text(
                    inIdeal
                        ? '✓ În intervalul IAAF'
                        : '⚠ Interval IAAF: ${idealRange!.keys.first.toStringAsFixed(0)}-${idealRange!.values.first.toStringAsFixed(0)}°',
                    style: TextStyle(color: statusColor, fontSize: 11),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _stat(String text) =>
      Text(text, style: const TextStyle(color: PBTheme.textDim, fontSize: 11));
}
