import 'package:flutter/material.dart';
import '../models/freshy_status.dart';

class StatusIndicator extends StatelessWidget {
  final FreshyStatus status;
  final bool isConnected;

  const StatusIndicator({
    Key? key,
    required this.status,
    required this.isConnected,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final statusColor = isConnected ? status.color : const Color(0xFFFF4B4B);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(
        color: const Color(0xFF131C2E),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(
          color: statusColor.withOpacity(0.4),
          width: 1.5,
        ),
        boxShadow: [
          BoxShadow(
            color: statusColor.withOpacity(0.2),
            blurRadius: 12,
            spreadRadius: 2,
          ),
        ],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 10,
            height: 10,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: statusColor,
              boxShadow: [
                BoxShadow(
                  color: statusColor,
                  blurRadius: 6,
                  spreadRadius: 1,
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Icon(status.icon, size: 16, color: statusColor),
          const SizedBox(width: 6),
          Text(
            isConnected ? status.label : 'CORE OFFLINE',
            style: TextStyle(
              color: statusColor,
              fontSize: 12,
              fontWeight: FontWeight.bold,
              letterSpacing: 1.1,
            ),
          ),
        ],
      ),
    );
  }
}
