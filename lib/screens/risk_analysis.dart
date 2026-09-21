// lib/screens/risk_analysis.dart
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:capstone_project/screens/address_search.dart';
import 'package:capstone_project/screens/risk_result.dart';
import 'package:capstone_project/services/api_service.dart';
import 'package:capstone_project/theme/app_theme.dart';
import 'package:capstone_project/widgets/app_bottom_navigation.dart';

class RiskAnalysisPage extends StatefulWidget {
  const RiskAnalysisPage({super.key});

  @override
  State<RiskAnalysisPage> createState() => _RiskAnalysisPageState();
}

class _RiskAnalysisPageState extends State<RiskAnalysisPage> {
  final TextEditingController priceController = TextEditingController();
  final TextEditingController durationController = TextEditingController();
  final TextEditingController addressController = TextEditingController();
  final TextEditingController detailAddressController = TextEditingController();

  bool isDurationUnknown = false;
  bool isDetailAddressUnknown = false;

  Map<String, dynamic>? selectedAddressData;

  @override
  void dispose() {
    priceController.dispose();
    durationController.dispose();
    addressController.dispose();
    detailAddressController.dispose();
    super.dispose();
  }

  Future<void> sendAddressAndPrice() async {
    if (selectedAddressData == null) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text("주소를 먼저 선택해 주세요.")));
      return;
    }

    final buildingUrl = ApiService.endpoint('/building/title-info');
    final requestBody = {
      'fullAddress': selectedAddressData!['fullAddress'],
      'roadName': selectedAddressData!['roadName'],
      'bcode': selectedAddressData!['bcode'],
      'mainAddressNo': selectedAddressData!['mainAddressNo'],
      'subAddressNo': selectedAddressData!['subAddressNo'] ?? '0',
      'price': int.tryParse(priceController.text.replaceAll(',', '')) ?? 0,
    };

    try {
      final buildingResp = await http.post(
        buildingUrl,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(requestBody),
      );

      if (buildingResp.statusCode == 200) {
        final buildingData = jsonDecode(utf8.decode(buildingResp.bodyBytes));

        showDialog(
          context: context,
          builder:
              (_) => AlertDialog(
                title: const Text("건축물 표제부 상세정보"),
                content: SingleChildScrollView(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text("문서번호: ${buildingData['resDocNo'] ?? '없음'}"),
                      Text(
                        "주소: ${(buildingData['resUserAddr'] ?? '없음').toString().replaceAll('+', ' ')}",
                      ),
                      Text("발급일자: ${buildingData['resIssueDate'] ?? '없음'}"),
                      const SizedBox(height: 12),
                      const Text(
                        "▶ 상세정보",
                        style: TextStyle(fontWeight: FontWeight.bold),
                      ),
                      if (buildingData['resDetailList'] != null)
                        ...List<Widget>.from(
                          (buildingData['resDetailList'] as List).map(
                            (item) => Text(
                              "${item['resType']}: ${item['resContents'].toString().replaceAll('+', ' ')}",
                            ),
                          ),
                        ),
                      const SizedBox(height: 12),
                      const Text(
                        "▶ 층별현황",
                        style: TextStyle(fontWeight: FontWeight.bold),
                      ),
                      if (buildingData['resBuildingStatusList'] != null)
                        ...List<Widget>.from(
                          (buildingData['resBuildingStatusList'] as List).map(
                            (item) => Text(
                              "${item['resFloor']}: ${item['resUseType']} (${item['resArea']}㎡)",
                            ),
                          ),
                        ),
                      const SizedBox(height: 12),
                      const Text(
                        "▶ 소유자 정보",
                        style: TextStyle(fontWeight: FontWeight.bold),
                      ),
                      if (buildingData['resOwnerList'] != null)
                        ...List<Widget>.from(
                          (buildingData['resOwnerList'] as List).map(
                            (item) => Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text("소유자: ${item['resOwner']}"),
                                Text(
                                  "주소: ${item['resUserAddr'].toString().replaceAll('+', ' ')}",
                                ),
                                Text("지분: ${item['resOwnershipStake']}"),
                                const SizedBox(height: 6),
                              ],
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
                actions: [
                  TextButton(
                    child: const Text("확인"),
                    onPressed: () async {
                      Navigator.pop(context); // 다이얼로그 닫기

                      final deposit =
                          int.tryParse(
                            priceController.text.replaceAll(',', ''),
                          ) ??
                          0;

                      try {
                        final analysisResp = await ApiService.analyzeJeonseRisk(
                          address: selectedAddressData!['fullAddress'],
                          deposit: deposit,
                          roadName: selectedAddressData!['roadName'],
                          mainAddressNo: selectedAddressData!['mainAddressNo'],
                          subAddressNo:
                              selectedAddressData!['subAddressNo'] ?? '0',
                        );

                        print("✅ API 응답: $analysisResp");

                        if (analysisResp['success']) {
                          final resultData = analysisResp['data'];
                          print("✅ resultData: $resultData");

                          // ⚠️ 중첩된 'data' 안에 실제 정보 존재
                          final innerData = resultData['data'];

                          print("✅ risk_score: ${innerData['risk_score']}");
                          print("✅ risk_items: ${innerData['risk_items']}");

                          Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder:
                                  (_) => RiskResultPage(
                                    address:
                                        selectedAddressData!['fullAddress'],
                                    deposit: deposit,
                                    marketPrice:
                                        (innerData['market_price'] is Map &&
                                                innerData['market_price']['value_won']
                                                    is num)
                                            ? (innerData['market_price']['value_won']
                                                    as num)
                                                .toInt()
                                            : null,
                                    // 서버 점수는 이미 0~100 이다 (높을수록 위험)
                                    riskScore:
                                        (innerData['risk_score'] is num)
                                            ? (innerData['risk_score'] as num)
                                                .round()
                                            : 0,
                                    notices:
                                        (innerData['notes'] is List)
                                            ? (innerData['notes'] as List)
                                                .map((e) => e.toString())
                                                .toList()
                                            : const [],
                                    riskItems:
                                        (innerData['risk_items'] is List)
                                            ? (innerData['risk_items'] as List)
                                                .map(
                                                  (item) =>
                                                      Map<String, dynamic>.from(
                                                        item,
                                                      ),
                                                )
                                                .toList()
                                            : [],
                                  ),
                            ),
                          );
                        } else {
                          print("❌ 분석 실패: ${analysisResp['message']}");
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text(
                                "위험도 분석 실패: ${analysisResp['message']}",
                              ),
                            ),
                          );
                        }
                      } catch (e, stack) {
                        print("❌ 예외 발생: $e");
                        print("📌 Stack: $stack");
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text("분석 중 오류 발생: $e")),
                        );
                      }
                    },
                  ),
                ],
              ),
        );
      } else {
        print("❌ 서버 오류 (건축물): ${buildingResp.statusCode}");
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text("건축물 정보 조회 실패")));
      }
    } catch (e) {
      print("❌ 통신 오류: $e");
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text("통신 오류: $e")));
    }
  }

  void _onAnalyzePressed() {
    sendAddressAndPrice();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          '전세 위험도 분석',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
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
                    child: const Icon(
                      Icons.shield_outlined,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          '계약 전 위험 요소 확인',
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 17,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        const SizedBox(height: 5),
                        Text(
                          '보증금과 주소를 입력하면 문서 근거를 바탕으로 위험 항목을 분석합니다.',
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
            ),
            const SizedBox(height: 18),
            _buildInputSection(
              step: '01',
              icon: Icons.payments_outlined,
              label: '전세 보증금',
              controller: priceController,
              hint: '보증금 입력',
              unit: '원',
            ),
            const SizedBox(height: 12),
            _buildInputSection(
              step: '02',
              icon: Icons.calendar_month_outlined,
              label: '계약 기간',
              controller: durationController,
              hint: '계약 기간 입력',
              unit: '개월',
              showCheckbox: true,
              checkboxValue: isDurationUnknown,
              onCheckboxChanged: (val) {
                setState(() {
                  isDurationUnknown = val ?? false;
                });
              },
              enabled: !isDurationUnknown,
            ),
            const SizedBox(height: 12),
            _buildInputSection(
              step: '03',
              icon: Icons.location_on_outlined,
              label: '분석할 주소',
              controller: addressController,
              hint: '주소를 선택해 주세요',
              enabled: false,
              onTap: () async {
                final selected = await Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const AddressSearchPage()),
                );
                if (selected != null) {
                  setState(() {
                    selectedAddressData = selected;
                    addressController.text = selected['fullAddress'];
                  });
                }
              },
            ),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.surface,
                border: Border.all(color: AppColors.border),
                borderRadius: BorderRadius.circular(18),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Row(
                    children: [
                      Icon(
                        Icons.door_front_door_outlined,
                        color: AppColors.primary,
                      ),
                      SizedBox(width: 8),
                      Text(
                        '상세 주소',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 14),
                  _buildInputField(
                    controller: detailAddressController,
                    hint: '동, 호수를 입력해 주세요',
                    enabled: !isDetailAddressUnknown,
                  ),
                  InkWell(
                    onTap: () {
                      setState(
                        () => isDetailAddressUnknown = !isDetailAddressUnknown,
                      );
                    },
                    child: Row(
                      children: [
                        Checkbox(
                          value: isDetailAddressUnknown,
                          onChanged: (value) {
                            setState(
                              () => isDetailAddressUnknown = value ?? false,
                            );
                          },
                        ),
                        const Text('상세 주소를 잘 모르겠어요'),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              height: 54,
              child: ElevatedButton.icon(
                onPressed: _onAnalyzePressed,
                icon: const Icon(Icons.analytics_outlined),
                label: const Text('전세 위험도 분석하기'),
              ),
            ),
          ],
        ),
      ),
      bottomNavigationBar: const AppBottomNavigation(currentIndex: 1),
    );
  }

  Widget _buildInputSection({
    required String step,
    required IconData icon,
    required String label,
    required TextEditingController controller,
    required String hint,
    String? unit,
    bool showCheckbox = false,
    bool checkboxValue = false,
    ValueChanged<bool?>? onCheckboxChanged,
    bool enabled = true,
    VoidCallback? onTap,
  }) {
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
                label,
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: _buildInputField(
                  controller: controller,
                  hint: hint,
                  enabled: enabled,
                  onTap: onTap,
                ),
              ),
              if (unit != null) ...[
                const SizedBox(width: 8),
                Text(unit, style: const TextStyle(color: AppColors.muted)),
              ],
            ],
          ),
          if (showCheckbox)
            InkWell(
              onTap: () => onCheckboxChanged?.call(!checkboxValue),
              child: Row(
                children: [
                  Checkbox(value: checkboxValue, onChanged: onCheckboxChanged),
                  const Text('계약 기간을 잘 모르겠어요'),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildInputField({
    required TextEditingController controller,
    required String hint,
    bool enabled = true,
    VoidCallback? onTap,
  }) {
    return TextField(
      controller: controller,
      readOnly: !enabled,
      onTap: onTap,
      keyboardType:
          controller == priceController || controller == durationController
              ? TextInputType.number
              : TextInputType.text,
      decoration: InputDecoration(
        hintText: hint,
        suffixIcon:
            onTap == null
                ? null
                : const Icon(
                  Icons.chevron_right_rounded,
                  color: AppColors.muted,
                ),
      ),
    );
  }
}
