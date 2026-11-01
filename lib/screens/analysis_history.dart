import 'package:capstone_project/screens/risk_result.dart';
import 'package:capstone_project/services/api_service.dart';
import 'package:capstone_project/theme/app_theme.dart';
import 'package:flutter/material.dart';

class AnalysisHistoryPage extends StatefulWidget {
  const AnalysisHistoryPage({super.key});

  @override
  State<AnalysisHistoryPage> createState() => _AnalysisHistoryPageState();
}

class _AnalysisHistoryPageState extends State<AnalysisHistoryPage> {
  List<Map<String, dynamic>> _items = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final response = await ApiService.fetchAnalysisHistory();
    if (!mounted) return;
    final data = response['data'];
    setState(() {
      _loading = false;
      if (response['success'] == true && data is Map && data['items'] is List) {
        _items =
            (data['items'] as List)
                .whereType<Map>()
                .map((item) => Map<String, dynamic>.from(item))
                .toList();
      } else {
        _error = response['message']?.toString() ?? '분석 이력을 불러오지 못했습니다.';
      }
    });
  }

  Future<bool> _confirm(String title, String content) async {
    return await showDialog<bool>(
          context: context,
          builder:
              (context) => AlertDialog(
                title: Text(title),
                content: Text(content),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.pop(context, false),
                    child: const Text('취소'),
                  ),
                  FilledButton(
                    onPressed: () => Navigator.pop(context, true),
                    child: const Text('삭제'),
                  ),
                ],
              ),
        ) ??
        false;
  }

  Future<void> _open(Map<String, dynamic> item) async {
    if (item['status'] != 'succeeded') return;
    final response = await ApiService.fetchAnalysisHistoryItem(
      item['job_id'].toString(),
    );
    if (!mounted) return;
    final job = response['data'];
    final envelope = job is Map ? job['result'] : null;
    if (response['success'] == true &&
        envelope is Map &&
        envelope['data'] is Map) {
      await Navigator.push(
        context,
        MaterialPageRoute(
          builder:
              (_) => RiskResultPage.fromData(
                data: Map<String, dynamic>.from(envelope['data'] as Map),
                jobId: item['job_id'].toString(),
              ),
        ),
      );
      _load();
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(response['message']?.toString() ?? '결과를 열 수 없습니다.'),
      ),
    );
  }

  Future<void> _deleteOne(Map<String, dynamic> item) async {
    if (!await _confirm('분석 이력 삭제', '선택한 분석 결과와 연결된 개인정보를 삭제할까요?')) return;
    final response = await ApiService.deleteAnalysisHistoryItem(
      item['job_id'].toString(),
    );
    if (!mounted) return;
    if (response['success'] == true) {
      _load();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(response['message']?.toString() ?? '삭제하지 못했습니다.'),
        ),
      );
    }
  }

  Future<void> _deleteAll() async {
    if (_items.isEmpty ||
        !await _confirm(
          '개인 분석 데이터 전체 삭제',
          '저장된 분석 이력을 모두 삭제할까요? 이 작업은 되돌릴 수 없습니다.',
        )) {
      return;
    }
    final response = await ApiService.clearAnalysisHistory();
    if (!mounted) return;
    if (response['success'] == true) {
      _load();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(response['message']?.toString() ?? '삭제하지 못했습니다.'),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('분석 이력'),
        actions: [
          IconButton(
            tooltip: '개인 분석 데이터 전체 삭제',
            onPressed: _items.isEmpty ? null : _deleteAll,
            icon: const Icon(Icons.delete_sweep_outlined),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child:
            _loading
                ? ListView(
                  children: const [
                    SizedBox(height: 220),
                    Center(child: CircularProgressIndicator()),
                  ],
                )
                : _error != null
                ? ListView(
                  children: [
                    const SizedBox(height: 180),
                    Center(child: Text('분석 이력을 불러오지 못했습니다.')),
                  ],
                )
                : _items.isEmpty
                ? ListView(
                  children: [
                    const SizedBox(height: 180),
                    Center(child: Text('저장된 분석 이력이 없습니다.')),
                  ],
                )
                : ListView.separated(
                  padding: const EdgeInsets.all(20),
                  itemCount: _items.length,
                  separatorBuilder: (_, _) => const SizedBox(height: 10),
                  itemBuilder: (context, index) {
                    final item = _items[index];
                    final score = (item['risk_score'] as num?)?.round();
                    return Card(
                      elevation: 0,
                      shape: RoundedRectangleBorder(
                        side: const BorderSide(color: AppColors.border),
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: ListTile(
                        onTap: () => _open(item),
                        contentPadding: const EdgeInsets.fromLTRB(
                          16,
                          10,
                          8,
                          10,
                        ),
                        title: Text(
                          item['address']?.toString() ??
                              item['stage']?.toString() ??
                              '분석 결과',
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontWeight: FontWeight.w800),
                        ),
                        subtitle: Text(
                          '${item['created_at']?.toString().replaceFirst('T', ' ').split('.').first ?? ''}'
                          '${item['risk_rule_version'] != null ? ' · 규칙 ${item['risk_rule_version']}' : ''}',
                        ),
                        trailing: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            if (score != null)
                              Text(
                                '$score점',
                                style: const TextStyle(
                                  fontWeight: FontWeight.w800,
                                ),
                              ),
                            IconButton(
                              tooltip: '삭제',
                              onPressed: () => _deleteOne(item),
                              icon: const Icon(Icons.delete_outline_rounded),
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
      ),
    );
  }
}
