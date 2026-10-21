import 'package:capstone_project/screens/address_search.dart';
import 'package:capstone_project/screens/risk_detail.dart';
import 'package:capstone_project/services/api_service.dart';
import 'package:capstone_project/screens/splash.dart';
import 'package:capstone_project/screens/risk_analysis.dart';
import 'package:capstone_project/screens/risk_result.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('maps an address API item to the risk-analysis input', () {
    final result = addressResultFromApi({
      'roadAddr': '서울 강남구 테헤란로 152',
      'roadName': '테헤란로',
      'bcode': '1168010100',
      'mainAddressNo': '152',
      'subAddressNo': '0',
    });

    expect(result?['fullAddress'], '서울 강남구 테헤란로 152');
    expect(result?['mainAddressNo'], '152');
    expect(result?['subAddressNo'], '0');
  });

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

  testWidgets('shows both PDF upload inputs', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: RiskAnalysisPage()));

    expect(find.text('등기부등본 PDF'), findsOneWidget);
    expect(find.text('건축물대장 PDF'), findsOneWidget);
    expect(find.text('PDF 위험도 분석하기'), findsOneWidget);
  });

  testWidgets('shows PDF processing results', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: RiskResultPage(
          address: '서울특별시 강남구 테스트로 100',
          deposit: 300000000,
          marketPrice: 500000000,
          riskScore: 10,
          riskItems: [],
          documentProcessing: {
            'registry': {
              'pages': 2,
              'ocr_pages': [2],
            },
            'building': {'pages': 1, 'ocr_pages': []},
          },
        ),
      ),
    );

    expect(find.textContaining('등기부 2쪽 · OCR 1쪽'), findsOneWidget);
    expect(find.textContaining('건축물대장 1쪽'), findsOneWidget);
  });

  testWidgets('shows the RAG evidence page in the detail report', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: RiskDetailPage(
          title: '권리사항',
          score: 10,
          explanation: '유효한 권리를 확인했습니다.',
          evidence: [
            {
              'doc_type': 'registry',
              'section': '을구',
              'page_no': 4,
              'text': '근저당권 채권최고액 80,000,000원',
            },
          ],
          themeColor: Colors.green,
        ),
      ),
    );

    expect(find.text('등기부 · 을구 · 4페이지'), findsOneWidget);
    expect(find.textContaining('80,000,000원'), findsOneWidget);
  });
}
