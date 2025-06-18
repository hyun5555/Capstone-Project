// lib/screens/risk_analysis.dart
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:capstone_project/screens/address_search.dart';
import 'package:capstone_project/screens/risk_result.dart';
import 'package:capstone_project/services/api_service.dart';

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
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("주소를 먼저 선택해 주세요.")),
      );
      return;
    }

    final buildingUrl = Uri.parse('http://10.0.2.2:8000/building/title-info');
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
          builder: (_) => AlertDialog(
            title: const Text("건축물 표제부 상세정보"),
            content: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text("문서번호: ${buildingData['resDocNo'] ?? '없음'}"),
                  Text("주소: ${(buildingData['resUserAddr'] ?? '없음').toString().replaceAll('+', ' ')}"),
                  Text("발급일자: ${buildingData['resIssueDate'] ?? '없음'}"),
                  const SizedBox(height: 12),
                  const Text("▶ 상세정보", style: TextStyle(fontWeight: FontWeight.bold)),
                  if (buildingData['resDetailList'] != null)
                    ...List<Widget>.from(
                      (buildingData['resDetailList'] as List).map((item) => Text(
                        "${item['resType']}: ${item['resContents'].toString().replaceAll('+', ' ')}",
                      )),
                    ),
                  const SizedBox(height: 12),
                  const Text("▶ 층별현황", style: TextStyle(fontWeight: FontWeight.bold)),
                  if (buildingData['resBuildingStatusList'] != null)
                    ...List<Widget>.from(
                      (buildingData['resBuildingStatusList'] as List).map((item) => Text(
                        "${item['resFloor']}: ${item['resUseType']} (${item['resArea']}㎡)",
                      )),
                    ),
                  const SizedBox(height: 12),
                  const Text("▶ 소유자 정보", style: TextStyle(fontWeight: FontWeight.bold)),
                  if (buildingData['resOwnerList'] != null)
                    ...List<Widget>.from(
                      (buildingData['resOwnerList'] as List).map((item) => Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text("소유자: ${item['resOwner']}"),
                          Text("주소: ${item['resUserAddr'].toString().replaceAll('+', ' ')}"),
                          Text("지분: ${item['resOwnershipStake']}"),
                          const SizedBox(height: 6),
                        ],
                      )),
                    ),
                ],
              ),
            ),
            actions: [
              TextButton(
                child: const Text("확인"),
                onPressed: () async {
                  Navigator.pop(context); // 다이얼로그 닫기

                  final deposit = int.tryParse(priceController.text.replaceAll(',', '')) ?? 0;

                  try {
                    final analysisResp = await ApiService.analyzeJeonseRisk(
                      address: selectedAddressData!['fullAddress'],
                      deposit: deposit,
                      marketPrice: 1000000000,
                    );

                    print("✅ API 응답: $analysisResp");

                    if (analysisResp['success']) {
                      final resultData = analysisResp['data'];
                      print("✅ risk_score: ${resultData['risk_score']}");
                      print("✅ risk_items: ${resultData['risk_items']}");

                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => RiskResultPage(
                            address: selectedAddressData!['fullAddress'],
                            deposit: deposit,
                            marketPrice: 1000000000,
                            riskScore: (resultData['risk_score'] is num)
                                ? (resultData['risk_score'] as num).toInt()
                                : 0,
                            riskItems: (resultData['risk_items'] is List)
                                ? (resultData['risk_items'] as List)
                                .map((item) => Map<String, dynamic>.from(item))
                                .toList()
                                : [],
                          ),
                        ),
                      );
                    } else {
                      print("❌ 분석 실패: ${analysisResp['message']}");
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(content: Text("위험도 분석 실패: ${analysisResp['message']}")),
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
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("건축물 정보 조회 실패")),
        );
      }
    } catch (e) {
      print("❌ 통신 오류: $e");
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("통신 오류: $e")),
      );
    }
  }



  void _onAnalyzePressed() {
    sendAddressAndPrice();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: Colors.white,
        foregroundColor: Colors.black,
        elevation: 0,
        centerTitle: true,
        title: const Text('전세 위험도 분석', style: TextStyle(fontWeight: FontWeight.bold)),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildInputSection(
              imagePath: 'assets/Money.png',
              label: '전세 금액을 입력해주세요',
              controller: priceController,
              hint: '',
              unit: '원',
            ),
            const SizedBox(height: 20),
            _buildInputSection(
              imagePath: 'assets/Calendar.png',
              label: '계약기간을 입력해주세요',
              controller: durationController,
              hint: '',
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
            const SizedBox(height: 20),
            _buildInputSection(
              imagePath: 'assets/Location.png',
              label: '분석할 주소를 입력해주세요',
              controller: addressController,
              hint: '주소를 선택해주세요',
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
            const SizedBox(height: 16),
            const Text(
              '상세 주소를 입력해주세요',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 10),
            _buildInputField(
              controller: detailAddressController,
              hint: '동, 호수를 입력해주세요',
              enabled: !isDetailAddressUnknown,
            ),
            Row(
              children: [
                Checkbox(
                  value: isDetailAddressUnknown,
                  onChanged: (val) {
                    setState(() {
                      isDetailAddressUnknown = val ?? false;
                    });
                  },
                ),
                const Text('잘 모르겠어요'),
              ],
            ),
            const SizedBox(height: 30),
            Center(
              child: ElevatedButton(
                onPressed: _onAnalyzePressed,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF010186),
                  padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 20),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: const Text(
                  '전세 사기 위험도 분석하기',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildInputSection({
    required String imagePath,
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
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Image.asset(imagePath, width: 24, height: 24),
            const SizedBox(width: 8),
            Text(label, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
          ],
        ),
        const SizedBox(height: 10),
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
              Text(unit, style: const TextStyle(fontSize: 16)),
            ],
          ],
        ),
        if (showCheckbox)
          Row(
            children: [
              Checkbox(value: checkboxValue, onChanged: onCheckboxChanged),
              const Text('잘 모르겠어요'),
            ],
          ),
      ],
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
      decoration: InputDecoration(
        hintText: hint,
        filled: true,
        fillColor: Colors.white,
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Color(0xFFE0E0E0)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Color(0xFF010186)),
        ),
      ),
    );
  }
}
