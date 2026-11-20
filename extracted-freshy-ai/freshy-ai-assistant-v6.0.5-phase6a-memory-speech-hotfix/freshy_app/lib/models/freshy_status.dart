import 'package:flutter/material.dart';

enum FreshyStatus { idle, listening, thinking, speaking }

extension FreshyStatusExtension on FreshyStatus {
  String get label {
    switch (this) {
      case FreshyStatus.idle:
        return 'IDLE';
      case FreshyStatus.listening:
        return 'LISTENING...';
      case FreshyStatus.thinking:
        return 'THINKING...';
      case FreshyStatus.speaking:
        return 'SPEAKING';
    }
  }

  Color get color {
    switch (this) {
      case FreshyStatus.idle:
        return const Color(0xFF00F2FE); // Vibrant cyan
      case FreshyStatus.listening:
        return const Color(0xFFFF416C); // Energetic rose/pink
      case FreshyStatus.thinking:
        return const Color(0xFFFFB703); // Golden amber
      case FreshyStatus.speaking:
        return const Color(0xFF38EF7D); // Neon emerald green
    }
  }

  IconData get icon {
    switch (this) {
      case FreshyStatus.idle:
        return Icons.blur_on_rounded;
      case FreshyStatus.listening:
        return Icons.mic_rounded;
      case FreshyStatus.thinking:
        return Icons.psychology_rounded;
      case FreshyStatus.speaking:
        return Icons.graphic_eq_rounded;
    }
  }
}
