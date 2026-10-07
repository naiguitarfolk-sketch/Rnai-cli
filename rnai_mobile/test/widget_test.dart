import 'package:flutter_test/flutter_test.dart';
import 'package:rnai_mobile/main.dart';
import 'package:rnai_mobile/services/api_service.dart';

void main() {
  testWidgets('RnaiApp initializes smoke test', (WidgetTester tester) async {
    final apiService = ApiService();
    await tester.pumpWidget(RnaiApp(apiService: apiService));
    expect(find.text('Rnai Workspace'), findsNothing);
  });
}
