import 'dart:convert';

import 'package:capstone_project/services/api_service.dart';
import 'package:capstone_project/theme/app_theme.dart';
import 'package:capstone_project/widgets/app_bottom_navigation.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

class RealTransactionAnalysisPage extends StatefulWidget {
  const RealTransactionAnalysisPage({super.key});

  @override
  State<RealTransactionAnalysisPage> createState() =>
      _RealTransactionAnalysisPageState();
}

class _RealTransactionAnalysisPageState
    extends State<RealTransactionAnalysisPage> {
  final TextEditingController locationController = TextEditingController();
  final TextEditingController priceController = TextEditingController();
  final List<String> _propertyTypes = ['아파트', '연립다세대'];
  String selectedPropertyType = '아파트';
  bool isPriceUnknown = false;
  bool _isLoading = false;

  @override
  void dispose() {
    locationController.dispose();
    priceController.dispose();
    super.dispose();
  }

  Future<void> _onAnalyzePressed() async {
    final location = locationController.text.trim();
    final price = isPriceUnknown ? '모름' : priceController.text;
    if (location.isEmpty) {
      _showErrorDialog('분석할 동네를 입력해 주세요.');
      return;
    }
    if (!isPriceUnknown &&
        (int.tryParse(price.replaceAll(',', '')) ?? 0) <= 0) {
      _showErrorDialog('전세 금액을 숫자로 입력해 주세요.');
      return;
    }

    setState(() => _isLoading = true);
    try {
      final response = await http.post(
        ApiService.endpoint('/transaction/summary'),
        headers: await ApiService.authHeaders(),
        body: jsonEncode({
          'address': location,
          'house_type': selectedPropertyType,
        }),
      );
      if (!mounted) return;
      if (response.statusCode != 200) {
        _showErrorDialog('서버 응답 오류: ${response.statusCode}');
        return;
      }

      final result = jsonDecode(utf8.decode(response.bodyBytes));
      if (result['status'] != 'ok') {
        _showErrorDialog(result['message'] ?? '분석 가능한 실거래 데이터가 없습니다.');
        return;
      }
      Navigator.pushNamed(
        context,
        '/real_transaction_report',
        arguments: {
          'result': result,
          'entered_price': price,
          'selectedPropertyType': selectedPropertyType,
        },
      );
    } catch (_) {
      if (mounted) _showErrorDialog('서버 요청 중 오류가 발생했습니다.');
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('실거래가 분석'),
        leading: IconButton(
          tooltip: '뒤로 가기',
          icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const _AnalysisIntro(
              icon: Icons.query_stats_rounded,
              title: '우리 동네 전세가율 확인',
              description: '최근 실거래 데이터를 기준으로 매매가와 전세 보증금을 비교합니다.',
            ),
            const SizedBox(height: 18),
            _FormCard(
              step: '01',
              title: '분석할 지역',
              icon: Icons.location_on_outlined,
              child: TextField(
                controller: locationController,
                decoration: const InputDecoration(hintText: '예: 서울특별시 송파구 잠실동'),
              ),
            ),
            const SizedBox(height: 12),
            _FormCard(
              step: '02',
              title: '주택 유형',
              icon: Icons.apartment_rounded,
              child: DropdownButtonFormField<String>(
                value: selectedPropertyType,
                items:
                    _propertyTypes
                        .map(
                          (type) =>
                              DropdownMenuItem(value: type, child: Text(type)),
                        )
                        .toList(),
                onChanged: (value) {
                  if (value != null) {
                    setState(() => selectedPropertyType = value);
                  }
                },
              ),
            ),
            const SizedBox(height: 12),
            _FormCard(
              step: '03',
              title: '전세 보증금',
              icon: Icons.payments_outlined,
              child: Column(
                children: [
                  TextField(
                    controller: priceController,
                    enabled: !isPriceUnknown,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(
                      hintText: '보증금 입력',
                      suffixText: '원',
                    ),
                  ),
                  _UnknownCheck(
                    value: isPriceUnknown,
                    onChanged: (value) {
                      setState(() => isPriceUnknown = value ?? false);
                    },
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              height: 54,
              child: ElevatedButton.icon(
                onPressed: _isLoading ? null : _onAnalyzePressed,
                icon:
                    _isLoading
                        ? const SizedBox(
                          width: 19,
                          height: 19,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                        : const Icon(Icons.analytics_outlined),
                label: Text(_isLoading ? '분석 중' : '실거래가 분석하기'),
              ),
            ),
          ],
        ),
      ),
      bottomNavigationBar: const AppBottomNavigation(currentIndex: 1),
    );
  }

  void _showErrorDialog(String message) {
    showDialog<void>(
      context: context,
      builder:
          (context) => AlertDialog(
            icon: const Icon(Icons.info_outline_rounded),
            title: const Text('확인해 주세요'),
            content: Text(message),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('확인'),
              ),
            ],
          ),
    );
  }
}

class _AnalysisIntro extends StatelessWidget {
  const _AnalysisIntro({
    required this.icon,
    required this.title,
    required this.description,
  });

  final IconData icon;
  final String title;
  final String description;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppColors.primary,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(15),
            ),
            child: Icon(icon, color: Colors.white),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 17,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 5),
                Text(
                  description,
                  style: TextStyle(
                    color: Colors.white.withValues(alpha: 0.72),
                    fontSize: 12.5,
                    height: 1.4,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _FormCard extends StatelessWidget {
  const _FormCard({
    required this.step,
    required this.title,
    required this.icon,
    required this.child,
  });

  final String step;
  final String title;
  final IconData icon;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        border: Border.all(color: AppColors.border),
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
                decoration: BoxDecoration(
                  color: AppColors.softBlue,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  step,
                  style: const TextStyle(
                    color: AppColors.primary,
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              const SizedBox(width: 9),
              Icon(icon, color: AppColors.primary, size: 20),
              const SizedBox(width: 7),
              Text(
                title,
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          child,
        ],
      ),
    );
  }
}

class _UnknownCheck extends StatelessWidget {
  const _UnknownCheck({required this.value, required this.onChanged});

  final bool value;
  final ValueChanged<bool?> onChanged;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: () => onChanged(!value),
      child: Row(
        children: [
          Checkbox(value: value, onChanged: onChanged),
          const Text('금액을 잘 모르겠어요'),
        ],
      ),
    );
  }
}
