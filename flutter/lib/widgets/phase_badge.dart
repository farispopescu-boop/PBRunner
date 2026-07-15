// lib/widgets/phase_badge.dart
import 'package:flutter/material.dart';
import '../theme.dart';

class PhaseBadge extends StatelessWidget {
  final String phase;
  final int frames;

  const PhaseBadge({super.key, required this.phase, required this.frames});

  Color get color {
    switch (phase) {
      case 'BLOCKSTART':
        return const Color(0xFFFF8C00);
      case 'SET':
        return const Color(0xFFFF6600);
      case 'ACCELERATIE':
        return const Color(0xFF00D4FF);
      case 'VITEZA MAX':
        return const Color(0xFF00DC00);
      default:
        return PBTheme.textDim;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        // ignore: deprecated_member_use
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(20),
        // ignore: deprecated_member_use
        border: Border.all(color: color.withOpacity(0.4)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 6),
          Text(
            phase,
            style: TextStyle(
              color: color,
              fontSize: 11,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(width: 4),
          Text(
            '$frames f',
            style: TextStyle(color: color.withOpacity(0.7), fontSize: 10),
          ),
        ],
      ),
    );
  }
}
