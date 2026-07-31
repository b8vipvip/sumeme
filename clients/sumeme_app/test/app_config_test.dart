import 'package:flutter_test/flutter_test.dart';
import 'package:sumeme_app/client_api.dart';

void main() {
  test('managed SuMeMe server URL uses HTTPS', () {
    final Uri uri = Uri.parse(SuMeMeClientApi.serverUrl);
    expect(uri.scheme, 'https');
    expect(uri.host, 'sumeme.mv3.cn');
    expect(uri.path, isEmpty);
  });
}
