import 'dart:convert';

import 'package:capstone_project/services/api_service.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

Map<String, String>? addressResultFromApi(Object? value) {
  if (value is! Map) return null;

  final fullAddress = value['roadAddr']?.toString().trim() ?? '';
  if (fullAddress.isEmpty) return null;

  return {
    'fullAddress': fullAddress,
    'roadName': value['roadName']?.toString() ?? '',
    'bcode': value['bcode']?.toString() ?? '',
    'mainAddressNo': value['mainAddressNo']?.toString() ?? '0',
    'subAddressNo': value['subAddressNo']?.toString() ?? '0',
  };
}

class AddressSearchPage extends StatefulWidget {
  const AddressSearchPage({super.key});

  @override
  State<AddressSearchPage> createState() => _AddressSearchPageState();
}

class _AddressSearchPageState extends State<AddressSearchPage> {
  final _controller = TextEditingController();
  List<Map<String, dynamic>> _results = const [];
  String? _error;
  bool _loading = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _search() async {
    final keyword = _controller.text.trim();
    if (keyword.isEmpty) {
      setState(() => _error = '검색할 주소를 입력해 주세요.');
      return;
    }

    FocusScope.of(context).unfocus();
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final response = await http.get(
        ApiService.endpoint('/address/search').replace(
          queryParameters: {
            'keyword': keyword,
            'currentPage': '1',
            'countPerPage': '10',
          },
        ),
      );
      if (!mounted) return;
      if (response.statusCode != 200) throw Exception();

      final decoded = jsonDecode(utf8.decode(response.bodyBytes));
      final results =
          decoded is List
              ? decoded.map((item) => Map<String, dynamic>.from(item)).toList()
              : <Map<String, dynamic>>[];
      setState(() {
        _results = results;
        _error = results.isEmpty ? '검색 결과가 없습니다.' : null;
      });
    } catch (_) {
      if (mounted) setState(() => _error = '주소 검색에 실패했습니다. 다시 시도해 주세요.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('주소 검색')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: TextField(
              controller: _controller,
              autofocus: true,
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => _search(),
              decoration: InputDecoration(
                hintText: '도로명 또는 지번을 입력해 주세요',
                suffixIcon: IconButton(
                  tooltip: '검색',
                  onPressed: _loading ? null : _search,
                  icon: const Icon(Icons.search),
                ),
              ),
            ),
          ),
          if (_loading) const LinearProgressIndicator(),
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 16, vertical: 4),
            child: Align(
              alignment: Alignment.centerRight,
              child: Text(
                '주소 데이터 © OpenStreetMap contributors',
                style: TextStyle(fontSize: 11, color: Colors.grey),
              ),
            ),
          ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.all(24),
              child: Text(_error!, textAlign: TextAlign.center),
            ),
          Expanded(
            child: ListView.separated(
              itemCount: _results.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (context, index) {
                final item = _results[index];
                final building = item['bdNm']?.toString() ?? '';
                return ListTile(
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 20,
                    vertical: 8,
                  ),
                  leading: Text(
                    item['zipNo']?.toString() ?? '',
                    style: const TextStyle(color: Colors.redAccent),
                  ),
                  title: Text(item['roadAddr']?.toString() ?? ''),
                  subtitle: Text(
                    [
                      item['jibunAddr']?.toString() ?? '',
                      if (building.isNotEmpty) building,
                    ].where((text) => text.isNotEmpty).join('\n'),
                  ),
                  trailing: const Icon(Icons.chevron_right_rounded),
                  onTap: () {
                    final result = addressResultFromApi(item);
                    if (result != null) Navigator.pop(context, result);
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
