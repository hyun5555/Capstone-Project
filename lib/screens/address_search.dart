import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_inappwebview/flutter_inappwebview.dart';

class AddressSearchPage extends StatefulWidget {
  const AddressSearchPage({super.key});

  @override
  State<AddressSearchPage> createState() => _AddressSearchPageState();
}

class _AddressSearchPageState extends State<AddressSearchPage> {
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("주소 검색")),
      body: InAppWebView(
        initialFile: 'assets/html/postcode.html',
        onWebViewCreated: (controller) {
          controller.addJavaScriptHandler(
            handlerName: 'onComplete',
            callback: (args) {
              final raw = jsonDecode(args.first);
              final result = {
                'fullAddress': raw['fullAddress'],
                'roadName': raw['roadName'] ?? '',
                'bcode': raw['bcode'] ?? '',
                'mainAddressNo': raw['mainAddressNo'] ?? '0',
                'subAddressNo': raw['subAddressNo'] ?? '0',
              };

              Navigator.pop(context, result);
            },
          );
        },
      ),
    );
  }
}
