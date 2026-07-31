import 'package:flutter_test/flutter_test.dart';
import 'package:sumeme_app/client_api.dart';
import 'package:sumeme_app/client_state.dart';

void main() {
  test('semantic version comparison detects upgrades', () {
    expect(compareVersions('0.4.1', '0.4.0'), greaterThan(0));
    expect(compareVersions('1.0.0', '0.9.99'), greaterThan(0));
    expect(compareVersions('0.4.0', '0.4.0'), 0);
    expect(compareVersions('0.4.0', '0.4.1'), lessThan(0));
  });

  test('native client uses the managed SuMeMe service endpoint', () {
    expect(SuMeMeClientApi.serverUrl, 'https://sumeme.mv3.cn');
  });
}
