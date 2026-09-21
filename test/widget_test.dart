import 'package:capstone_project/services/api_service.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('builds endpoints from the local API base URL', () {
    expect(
      ApiService.endpoint('/analyze/').toString(),
      'http://127.0.0.1:8000/analyze/',
    );
  });
}
