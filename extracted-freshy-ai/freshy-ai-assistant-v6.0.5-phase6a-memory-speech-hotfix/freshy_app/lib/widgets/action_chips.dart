import 'package:flutter/material.dart';

class ActionChips extends StatelessWidget {
  final Function(String) onChipTap;

  const ActionChips({Key? key, required this.onChipTap}) : super(key: key);

  static const List<Map<String, dynamic>> presetActions = [
    {'label': '👋 Hello Freshy', 'command': 'Hello Freshy'},
    {'label': '⏰ What time is it?', 'command': 'What time is it?'},
    {'label': '📝 Open Notepad', 'command': 'Open Notepad'},
    {'label': '🧮 Open Calculator', 'command': 'Open Calculator'},
    {'label': '🌐 Open Google', 'command': 'Open Google'},
  ];

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
      child: Row(
        children: presetActions.map((action) {
          return Padding(
            padding: const EdgeInsets.only(right: 8.0),
            child: ActionChip(
              backgroundColor: const Color(0xFF131C2E),
              side: BorderSide(
                color: const Color(0xFF00F2FE).withOpacity(0.3),
                width: 1,
              ),
              label: Text(
                action['label'],
                style: const TextStyle(
                  color: Color(0xFF90E0EF),
                  fontSize: 12,
                ),
              ),
              onPressed: () => onChipTap(action['command']),
            ),
          );
        }).toList(),
      ),
    );
  }
}
