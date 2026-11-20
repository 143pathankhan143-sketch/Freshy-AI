import 'package:flutter_test/flutter_test.dart';
import 'package:freshy_app/main.dart';

void main() {
  testWidgets('Freshy UI initial render test', (WidgetTester tester) async {
    // Build FreshyApp and trigger a frame.
    await tester.pumpWidget(const FreshyApp());

    // Verify Freshy AI header title is rendered.
    expect(find.text('FRESHY AI'), findsOneWidget);

    // Verify initial welcome greeting is shown in chat area.
    expect(find.textContaining('Freshy Phase 4.3 is ready'), findsOneWidget);
  });
}
