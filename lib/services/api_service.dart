// lib/services/api_service.dart
import 'dart:convert';
import 'package:file_picker/file_picker.dart';
import 'package:http/http.dart' as http;

class ApiService {
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://127.0.0.1:8000',
  );

  static Uri endpoint(String path) => Uri.parse('$baseUrl$path');

  static Map<String, dynamic> _jsonObject(http.Response response) {
    try {
      final decoded = jsonDecode(utf8.decode(response.bodyBytes));
      return decoded is Map<String, dynamic> ? decoded : {};
    } on FormatException {
      return {};
    }
  }

  /// 이메일 회원가입
  static Future<Map<String, dynamic>> signUpEmail({
    required String email,
    required String username,
    required String password,
    required String phone, // ✅ phone 파라미터 추가
  }) async {
    final uri = endpoint('/auth/signup/email');
    final resp = await http.post(
      uri,
      headers: {"Content-Type": "application/json"},
      body: jsonEncode({
        "email": email,
        "username": username,
        "password": password,
        "phone": phone, // ✅ 요청 바디에 포함
      }),
    );

    final body = _jsonObject(resp);
    if (resp.statusCode == 201 || resp.statusCode == 200) {
      return {"success": true, "data": body};
    } else {
      return {
        "success": false,
        "message": body["detail"] ?? "회원가입 실패 (${resp.statusCode})",
      };
    }
  }

  /// 로그인
  static Future<Map<String, dynamic>> login({
    required String email,
    required String password,
  }) async {
    final uri = endpoint('/auth/login/email');
    final resp = await http.post(
      uri,
      headers: {"Content-Type": "application/json"},
      body: jsonEncode({"email": email, "password": password}),
    );

    final body = _jsonObject(resp);
    if (resp.statusCode == 200) {
      return {"success": true, "data": body};
    } else {
      return {
        "success": false,
        "message": body["detail"] ?? "Invalid credentials",
      };
    }
  }

  //  챗봇 메시지 요청 함수
  static Future<Map<String, dynamic>> fetchChatbotAnswer(
    String userMessage, {
    String? stage,
  }) async {
    try {
      final response = await http.post(
        endpoint('/chatbot/chat'),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({
          "message": userMessage,
          if (stage != null) "stage": stage,
        }),
      );
      final data = _jsonObject(response);
      if (response.statusCode == 200) {
        return {
          'answer': data['answer'] ?? '답변을 찾을 수 없습니다.',
          'sources': data['sources'] is List ? data['sources'] : [],
          'mode': data['mode'] ?? 'unknown',
        };
      }
      return {
        'answer': data['detail'] ?? '서버 오류: ${response.statusCode}',
        'sources': [],
        'mode': 'error',
      };
    } catch (_) {
      return {
        'answer': '서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.',
        'sources': [],
        'mode': 'error',
      };
    }
  }

  // 로그인된 유저의 email 기반으로 정보 조회
  static Future<Map<String, dynamic>> getUserByEmail(
    String email,
    String token,
  ) async {
    final uri = endpoint(
      '/users/by-email',
    ).replace(queryParameters: {'email': email});
    final resp = await http.get(
      uri,
      headers: {"Authorization": "Bearer $token"},
    );

    if (resp.statusCode == 200) {
      final data = jsonDecode(utf8.decode(resp.bodyBytes));
      return {"success": true, "data": data};
    } else {
      return {"success": false, "message": "사용자 정보 조회 실패 (${resp.statusCode})"};
    }
  }

  // ✅ 회원정보 수정 API 호출
  static Future<Map<String, dynamic>> updateUser({
    required String userId,
    required String token,
    String? password,
    String? phone,
  }) async {
    final uri = endpoint('/users/$userId');

    // 전송할 필드만 포함
    final Map<String, dynamic> body = {};
    if (password != null && password.isNotEmpty) body['password'] = password;
    if (phone != null && phone.isNotEmpty) body['phone'] = phone;

    final resp = await http.put(
      uri,
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer $token",
      },
      body: jsonEncode(body),
    );

    if (resp.statusCode == 200) {
      final data = jsonDecode(utf8.decode(resp.bodyBytes));
      return {"success": true, "data": data};
    } else {
      final msg = jsonDecode(resp.body)['detail'] ?? '오류 발생';
      return {"success": false, "message": msg};
    }
  }

  // ✅ lib/services/api_service.dart 수정
  static Future<Map<String, dynamic>> analyzeJeonseRisk({
    required String address,
    required int deposit,
    int? marketPrice, // 없으면 서버가 같은 동 최근 매매 실거래가 중앙값으로 추정하고, 못 구하면 '판단불가'로 처리
    String? roadName,
    String? mainAddressNo,
    String? subAddressNo,
  }) async {
    final url = endpoint('/analyze/');
    final response = await http.post(
      url,
      headers: {"Content-Type": "application/json"},
      body: jsonEncode({
        "address": address,
        "deposit": deposit,
        if (marketPrice != null) "marketPrice": marketPrice,
        // 건축물대장 조회에 필요한 주소 정보 (주소 검색 결과 그대로)
        "roadName": roadName,
        "mainAddressNo": mainAddressNo,
        "subAddressNo": subAddressNo ?? '0',
      }),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(utf8.decode(response.bodyBytes));
      return {"success": true, "data": data};
    } else {
      return {"success": false, "message": "분석 실패 (${response.statusCode})"};
    }
  }

  static Future<Map<String, dynamic>> analyzeJeonsePdf({
    required PlatformFile registryPdf,
    required PlatformFile buildingPdf,
    required String address,
    required int deposit,
    int? marketPrice,
  }) async {
    final request =
        http.MultipartRequest('POST', endpoint('/analyze/pdf'))
          ..fields['address'] = address
          ..fields['deposit'] = deposit.toString();
    if (marketPrice != null) {
      request.fields['marketPrice'] = marketPrice.toString();
    }

    request.files.addAll([
      http.MultipartFile.fromBytes(
        'registry_pdf',
        await registryPdf.xFile.readAsBytes(),
        filename: registryPdf.name,
      ),
      http.MultipartFile.fromBytes(
        'building_pdf',
        await buildingPdf.xFile.readAsBytes(),
        filename: buildingPdf.name,
      ),
    ]);

    try {
      final response = await http.Response.fromStream(await request.send());
      final body = _jsonObject(response);
      if (response.statusCode == 200) {
        return {'success': true, 'data': body};
      }
      return {
        'success': false,
        'message': body['detail'] ?? '분석 실패 (${response.statusCode})',
      };
    } catch (_) {
      return {'success': false, 'message': '서버에 연결할 수 없습니다.'};
    }
  }
}
