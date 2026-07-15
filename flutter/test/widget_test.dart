import 'package:flutter_test/flutter_test.dart';
import 'package:pbrunner/main.dart';

void main() {
  testWidgets('App smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const PBRunnerApp());
    expect(find.byType(PBRunnerApp), findsOneWidget);
  });
}
