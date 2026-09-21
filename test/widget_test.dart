import 'package:capstone_project/services/api_service.dart';
import 'package:capstone_project/screens/splash.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('builds endpoints from the local API base URL', () {
    expect(
      ApiService.endpoint('/analyze/').toString(),
      'http://127.0.0.1:8000/analyze/',
    );
  });

  testWidgets('shows the landing screen before login', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        initialRoute: '/splash',
        routes: {
          '/splash': (_) => const SplashPage(),
          '/login': (_) => const Scaffold(body: Text('login')),
        },
      ),
    );

    expect(find.text('전세 안심'), findsOneWidget);

    await tester.pump(const Duration(milliseconds: 1400));
    await tester.pumpAndSettle();

    expect(find.text('login'), findsOneWidget);
  });
}
