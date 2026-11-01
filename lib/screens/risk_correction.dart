import 'package:capstone_project/services/api_service.dart';
import 'package:flutter/material.dart';

class RiskCorrectionPage extends StatefulWidget {
  const RiskCorrectionPage({
    super.key,
    required this.jobId,
    required this.values,
  });

  final String jobId;
  final Map<String, dynamic> values;

  @override
  State<RiskCorrectionPage> createState() => _RiskCorrectionPageState();
}

class _RiskCorrectionPageState extends State<RiskCorrectionPage> {
  static const _rights = [
    '경매개시결정',
    '압류',
    '가압류',
    '가처분',
    '가등기',
    '신탁',
    '전세권',
    '임차권',
    '근저당권',
  ];

  late final TextEditingController _registryOwner;
  late final TextEditingController _buildingOwner;
  late final TextEditingController _maxClaim;
  late final TextEditingController _usage;
  late final TextEditingController _deposit;
  late final TextEditingController _marketPrice;
  late final Set<String> _selectedRights;
  bool? _violation;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    String value(String key) => widget.values[key]?.toString() ?? '';
    _registryOwner = TextEditingController(text: value('registry_owner'));
    _buildingOwner = TextEditingController(text: value('building_owner'));
    _maxClaim = TextEditingController(text: value('max_claim_amount'));
    _usage = TextEditingController(text: value('building_usage'));
    _deposit = TextEditingController(text: value('deposit'));
    _marketPrice = TextEditingController(text: value('market_price'));
    _selectedRights = {
      if (widget.values['active_rights'] is List)
        ...(widget.values['active_rights'] as List).map(
          (item) => item.toString(),
        ),
    };
    _violation = widget.values['building_violation'] as bool?;
  }

  @override
  void dispose() {
    _registryOwner.dispose();
    _buildingOwner.dispose();
    _maxClaim.dispose();
    _usage.dispose();
    _deposit.dispose();
    _marketPrice.dispose();
    super.dispose();
  }

  int? _number(TextEditingController controller) {
    final text = controller.text.replaceAll(',', '').trim();
    return text.isEmpty ? null : int.tryParse(text);
  }

  Future<void> _save() async {
    final deposit = _number(_deposit);
    final claim = _number(_maxClaim);
    final market = _number(_marketPrice);
    if (deposit == null || deposit <= 0 || claim == null || claim < 0) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('보증금과 채권최고액을 숫자로 확인해 주세요.')));
      return;
    }
    if (_marketPrice.text.trim().isNotEmpty &&
        (market == null || market <= 0)) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('시세는 0보다 큰 숫자로 입력해 주세요.')));
      return;
    }
    setState(() => _saving = true);
    final result = await ApiService.updateAnalysisCorrections(widget.jobId, {
      'registry_owner': _registryOwner.text.trim(),
      'building_owner': _buildingOwner.text.trim(),
      'active_rights': _selectedRights.toList()..sort(),
      'max_claim_amount': claim,
      'building_violation': _violation,
      'building_usage': _usage.text.trim(),
      'deposit': deposit,
      'market_price': market,
    });
    if (!mounted) return;
    setState(() => _saving = false);
    final envelope = result['data'];
    if (result['success'] == true &&
        envelope is Map &&
        envelope['data'] is Map) {
      Navigator.pop(
        context,
        Map<String, dynamic>.from(envelope['data'] as Map),
      );
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(result['message']?.toString() ?? '저장하지 못했습니다.')),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('OCR 추출값 확인')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
        children: [
          const Text(
            'PDF 원본과 대조한 뒤 잘못 읽힌 값만 고쳐 주세요. 수정값은 위험 규칙 재계산에 사용됩니다.',
            style: TextStyle(color: Colors.black54, height: 1.45),
          ),
          const SizedBox(height: 18),
          _field(_registryOwner, '등기부 소유자'),
          _field(_buildingOwner, '건축물대장 소유자'),
          _field(_maxClaim, '채권최고액(원)', number: true),
          _field(_usage, '건물 용도'),
          _field(_deposit, '보증금(원)', number: true),
          _field(_marketPrice, '시세(원, 모르면 비움)', number: true),
          DropdownButtonFormField<bool?>(
            value: _violation,
            decoration: const InputDecoration(labelText: '위반건축물 표시'),
            items: const [
              DropdownMenuItem(value: null, child: Text('확인 불가')),
              DropdownMenuItem(value: false, child: Text('없음')),
              DropdownMenuItem(value: true, child: Text('있음')),
            ],
            onChanged: (value) => setState(() => _violation = value),
          ),
          const SizedBox(height: 20),
          const Text(
            '말소되지 않은 권리',
            style: TextStyle(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 4,
            children:
                _rights.map((right) {
                  return FilterChip(
                    label: Text(right),
                    selected: _selectedRights.contains(right),
                    onSelected:
                        (selected) => setState(() {
                          selected
                              ? _selectedRights.add(right)
                              : _selectedRights.remove(right);
                        }),
                  );
                }).toList(),
          ),
          const SizedBox(height: 26),
          FilledButton(
            onPressed: _saving ? null : _save,
            child: Text(_saving ? '저장 중...' : '수정값으로 다시 분석'),
          ),
        ],
      ),
    );
  }

  Widget _field(
    TextEditingController controller,
    String label, {
    bool number = false,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextField(
        controller: controller,
        keyboardType: number ? TextInputType.number : TextInputType.text,
        decoration: InputDecoration(labelText: label),
      ),
    );
  }
}
