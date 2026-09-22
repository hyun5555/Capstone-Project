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
  bool _isPreparing = false;
  bool _isAnalyzing = false;

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
    if (_isPreparing || _isAnalyzing) return;
    if (selectedAddressData == null) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text("주소를 먼저 선택해 주세요.")));
      return;
    }

    setState(() => _isPreparing = true);
    final buildingUrl = ApiService.endpoint('/building/title-info');
    final requestBody = {
      'fullAddress': selectedAddressData!['fullAddress'],
      'roadName': selectedAddressData!['roadName'],
      'bcode': selectedAddressData!['bcode'],
      'mainAddressNo': selectedAddressData!['mainAddressNo'],
      'subAddressNo': selectedAddressData!['subAddressNo'] ?? '0',
      'price': int.tryParse(priceController.text.replaceAll(',', '')) ?? 0,
    };

    Map<String, dynamic>? buildingData;
    try {
      final buildingResp = await http.post(
        buildingUrl,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(requestBody),
      );
      if (!mounted) return;

      if (buildingResp.statusCode != 200) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text("건축물 정보 조회 실패")));
        return;
      }

      final decoded = jsonDecode(utf8.decode(buildingResp.bodyBytes));
      if (decoded is! Map) throw const FormatException();
      buildingData = Map<String, dynamic>.from(decoded);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text("통신 오류: $e")));
    } finally {
      if (mounted) setState(() => _isPreparing = false);
    }

    if (buildingData == null || !mounted) return;
    final confirmed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => _BuildingInfoDialog(data: buildingData!),
    );
    if (confirmed != true || !mounted) return;

    setState(() => _isAnalyzing = true);
    await _runRiskAnalysis();
  }

  Future<void> _runRiskAnalysis() async {
    final deposit = int.tryParse(priceController.text.replaceAll(',', '')) ?? 0;

    try {
      final analysisResp = await ApiService.analyzeJeonseRisk(
        address: selectedAddressData!['fullAddress'],
        deposit: deposit,
        roadName: selectedAddressData!['roadName'],
        mainAddressNo: selectedAddressData!['mainAddressNo'],
        subAddressNo: selectedAddressData!['subAddressNo'] ?? '0',
      );
      if (!mounted) return;

      final resultData = analysisResp['data'];
      final innerData = resultData is Map ? resultData['data'] : null;
      if (analysisResp['success'] != true || innerData is! Map) {
        setState(() => _isAnalyzing = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              "위험도 분석 실패: ${analysisResp['message'] ?? '응답 형식 오류'}",
            ),
          ),
        );
        return;
      }

      await Navigator.push(
        context,
        MaterialPageRoute(
          builder:
              (_) => RiskResultPage(
                address: selectedAddressData!['fullAddress'],
                deposit: deposit,
                marketPrice:
                    (innerData['market_price'] is Map &&
                            innerData['market_price']['value_won'] is num)
                        ? (innerData['market_price']['value_won'] as num)
                            .toInt()
                        : null,
                riskScore:
                    (innerData['risk_score'] is num)
                        ? (innerData['risk_score'] as num).round()
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
                            .map((item) => Map<String, dynamic>.from(item))
                            .toList()
                        : const [],
              ),
        ),
      );
      if (mounted) setState(() => _isAnalyzing = false);
    } catch (e) {
      if (!mounted) return;
      setState(() => _isAnalyzing = false);
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text("분석 중 오류 발생: $e")));
    }
  }

  void _onAnalyzePressed() {
    sendAddressAndPrice();
  }

  @override
  Widget build(BuildContext context) {
    if (_isAnalyzing) return const _AnalysisLoadingScreen();

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
                onPressed: _isPreparing ? null : _onAnalyzePressed,
                icon:
                    _isPreparing
                        ? const SizedBox(
                          width: 19,
                          height: 19,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                        : const Icon(Icons.analytics_outlined),
                label: Text(_isPreparing ? '건축물 정보 확인 중' : '전세 위험도 분석하기'),
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

class _BuildingInfoDialog extends StatelessWidget {
  const _BuildingInfoDialog({required this.data});

  final Map<String, dynamic> data;

  String _text(String key, [String fallback = '확인 불가']) {
    final value = data[key]?.toString().replaceAll('+', ' ').trim();
    return value == null || value.isEmpty ? fallback : value;
  }

  List<Map<String, dynamic>> _items(String key) {
    final value = data[key];
    if (value is! List) return const [];
    return value
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList();
  }

  @override
  Widget build(BuildContext context) {
    final details = _items('resDetailList');
    final floors = _items('resBuildingStatusList');
    final owners = _items('resOwnerList');

    return AlertDialog(
      scrollable: true,
      insetPadding: const EdgeInsets.symmetric(horizontal: 22, vertical: 30),
      icon: Container(
        width: 52,
        height: 52,
        decoration: BoxDecoration(
          color: AppColors.softBlue,
          borderRadius: BorderRadius.circular(16),
        ),
        child: const Icon(
          Icons.apartment_rounded,
          color: AppColors.primary,
          size: 28,
        ),
      ),
      title: const Text(
        '건축물 정보 확인',
        style: TextStyle(fontWeight: FontWeight.w800),
      ),
      content: SizedBox(
        width: 430,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              '분석에 사용할 공공문서 정보입니다.',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.muted, fontSize: 13),
            ),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(15),
              decoration: BoxDecoration(
                color: AppColors.softBlue,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Column(
                children: [
                  _DocumentInfoRow(label: '문서번호', value: _text('resDocNo')),
                  const SizedBox(height: 10),
                  _DocumentInfoRow(label: '주소', value: _text('resUserAddr')),
                  const SizedBox(height: 10),
                  _DocumentInfoRow(label: '발급일자', value: _text('resIssueDate')),
                ],
              ),
            ),
            const SizedBox(height: 12),
            _DocumentSection(
              icon: Icons.description_outlined,
              title: '상세 정보',
              count: details.length,
              children:
                  details
                      .map(
                        (item) => _sectionText(
                          '${item['resType'] ?? '항목'} · ${item['resContents'] ?? '확인 불가'}',
                        ),
                      )
                      .toList(),
            ),
            const SizedBox(height: 8),
            _DocumentSection(
              icon: Icons.layers_outlined,
              title: '층별 현황',
              count: floors.length,
              children:
                  floors
                      .map(
                        (item) => _sectionText(
                          '${item['resFloor'] ?? '-'} · ${item['resUseType'] ?? '용도 확인 불가'}'
                          '${item['resArea'] == null ? '' : ' · ${item['resArea']}㎡'}',
                        ),
                      )
                      .toList(),
            ),
            const SizedBox(height: 8),
            _DocumentSection(
              icon: Icons.person_outline_rounded,
              title: '소유자 정보',
              count: owners.length,
              children:
                  owners
                      .map(
                        (item) => _sectionText(
                          '${item['resOwner'] ?? '소유자 확인 불가'} · 지분 ${item['resOwnershipStake'] ?? '확인 불가'}\n'
                          '${item['resUserAddr']?.toString().replaceAll('+', ' ') ?? ''}',
                        ),
                      )
                      .toList(),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context, false),
          child: const Text('닫기'),
        ),
        FilledButton.icon(
          onPressed: () => Navigator.pop(context, true),
          icon: const Icon(Icons.analytics_outlined, size: 19),
          label: const Text('확인 및 분석 시작'),
        ),
      ],
    );
  }

  Widget _sectionText(String text) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
      child: Align(
        alignment: Alignment.centerLeft,
        child: Text(text, style: const TextStyle(height: 1.45)),
      ),
    );
  }
}

class _DocumentInfoRow extends StatelessWidget {
  const _DocumentInfoRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 66,
          child: Text(
            label,
            style: const TextStyle(color: AppColors.muted, fontSize: 12),
          ),
        ),
        Expanded(
          child: Text(
            value,
            style: const TextStyle(fontWeight: FontWeight.w700, height: 1.35),
          ),
        ),
      ],
    );
  }
}

class _DocumentSection extends StatelessWidget {
  const _DocumentSection({
    required this.icon,
    required this.title,
    required this.count,
    required this.children,
  });

  final IconData icon;
  final String title;
  final int count;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        border: Border.all(color: AppColors.border),
        borderRadius: BorderRadius.circular(14),
      ),
      child: ExpansionTile(
        shape: const Border(),
        collapsedShape: const Border(),
        leading: Icon(icon, color: AppColors.primary),
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
        subtitle: Text(count == 0 ? '정보 없음' : '$count개 항목'),
        children:
            children.isEmpty
                ? const [
                  Padding(
                    padding: EdgeInsets.only(bottom: 14),
                    child: Text(
                      '확인된 정보가 없습니다.',
                      style: TextStyle(color: AppColors.muted),
                    ),
                  ),
                ]
                : children,
      ),
    );
  }
}

class _AnalysisLoadingScreen extends StatelessWidget {
  const _AnalysisLoadingScreen();

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      child: Scaffold(
        body: SafeArea(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 32),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  SizedBox(
                    width: 112,
                    height: 112,
                    child: Stack(
                      alignment: Alignment.center,
                      children: [
                        const SizedBox.expand(
                          child: CircularProgressIndicator(
                            strokeWidth: 7,
                            color: AppColors.primary,
                            backgroundColor: AppColors.softBlue,
                          ),
                        ),
                        Container(
                          width: 72,
                          height: 72,
                          decoration: const BoxDecoration(
                            color: AppColors.softBlue,
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(
                            Icons.shield_outlined,
                            color: AppColors.primary,
                            size: 35,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 30),
                  const Text(
                    '전세 위험도 분석 중...',
                    style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    '등기부와 건축물 정보를 비교하고 있어요.\n리포트가 완성되면 자동으로 이동합니다.',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: AppColors.muted,
                      fontSize: 14,
                      height: 1.55,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
