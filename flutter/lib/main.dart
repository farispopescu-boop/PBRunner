// lib/main.dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'theme.dart';
import 'screens/home_screen.dart';
import 'screens/athletes_screen.dart';
import 'screens/history_screen.dart';
import 'screens/settings_screen.dart';

// ─────────────────────────────────────────────────────────────────────────────
//  REFRESH BUS GLOBAL
//  Notifier-i globali pe care ecranele Istoric si Atleti il asculta.
//  Cand utilizatorul apasa un tab, valoarea se incrementeaza, iar ecranul
//  apasat isi reincarca datele.
// ─────────────────────────────────────────────────────────────────────────────
final ValueNotifier<int> historyRefreshBus = ValueNotifier<int>(0);
final ValueNotifier<int> athletesRefreshBus = ValueNotifier<int>(0);

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.landscapeLeft,
    DeviceOrientation.landscapeRight,
  ]);
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.light,
  ));
  runApp(const PBRunnerApp());
}

class PBRunnerApp extends StatelessWidget {
  const PBRunnerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'PBRunner',
      debugShowCheckedModeBanner: false,
      theme: PBTheme.theme,
      home: const AppShell(),
    );
  }
}

class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _currentIndex = 0;

  final List<Widget> _screens = const [
    HomeScreen(),
    AthletesScreen(),
    HistoryScreen(),
    SettingsScreen(),
  ];

  void _onTabTap(int i) {
    setState(() => _currentIndex = i);
    // Declanseaza refresh la deschiderea tab-ului
    if (i == 1) athletesRefreshBus.value++;
    if (i == 2) historyRefreshBus.value++;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: _screens,
      ),
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          border: Border(top: BorderSide(color: PBTheme.border)),
        ),
        child: BottomNavigationBar(
          currentIndex: _currentIndex,
          onTap: _onTabTap,
          items: const [
            BottomNavigationBarItem(
              icon: Icon(Icons.play_circle_outline),
              activeIcon: Icon(Icons.play_circle),
              label: 'Analiză',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.people_outline),
              activeIcon: Icon(Icons.people),
              label: 'Atleți',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.history_outlined),
              activeIcon: Icon(Icons.history),
              label: 'Istoric',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.settings_outlined),
              activeIcon: Icon(Icons.settings),
              label: 'Setări',
            ),
          ],
        ),
      ),
    );
  }
}
