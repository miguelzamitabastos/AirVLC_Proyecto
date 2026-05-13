import 'package:flutter/material.dart';

import 'core/api/airvlc_api_client.dart';
import 'core/storage/profile_storage.dart';
import 'core/theme/airvlc_theme.dart';
import 'features/chat/chat_screen.dart';
import 'features/dashboard/dashboard_screen.dart';
import 'features/map/map_risk_screen.dart';
import 'features/profile/onboarding_screen.dart';
import 'features/profile/profile_screen.dart';
import 'features/subscriptions/subscriptions_screen.dart';

/// Bootstrap principal. Decide si mostrar el onboarding (primer arranque)
/// o la home con bottom nav (arranques siguientes).
class AirVLCApp extends StatelessWidget {
  const AirVLCApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AirVLC',
      debugShowCheckedModeBanner: false,
      theme: AirVLCTheme.lightTheme,
      home: const _RootBootstrap(),
    );
  }
}

class _RootBootstrap extends StatefulWidget {
  const _RootBootstrap();

  @override
  State<_RootBootstrap> createState() => _RootBootstrapState();
}

class _RootBootstrapState extends State<_RootBootstrap> {
  final _profileStorage = ProfileStorage();
  Future<bool>? _onboardingDoneFuture;

  @override
  void initState() {
    super.initState();
    _onboardingDoneFuture = _profileStorage.isOnboardingDone();
  }

  void _refresh() {
    setState(() {
      _onboardingDoneFuture = _profileStorage.isOnboardingDone();
    });
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<bool>(
      future: _onboardingDoneFuture,
      builder: (context, snap) {
        if (!snap.hasData) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }
        if (snap.data == false) {
          return OnboardingScreen(onCompleted: _refresh);
        }
        return const HomeShell();
      },
    );
  }
}

/// Shell con bottom nav: Dashboard / Mapa / Chat / Alertas / Perfil.
///
/// Sprint 7: se añade la pestaña "Mapa" (MapRiskScreen) como segundo tab.
class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;
  late final AirVLCApiClient _apiClient;
  late final ProfileStorage _profileStorage;

  @override
  void initState() {
    super.initState();
    _apiClient = AirVLCApiClient();
    _profileStorage = ProfileStorage();
  }

  @override
  void dispose() {
    _apiClient.close();
    super.dispose();
  }

  List<Widget> get _pages => [
        DashboardScreen(api: _apiClient, profileStorage: _profileStorage),
        MapRiskScreen(api: _apiClient),
        ChatScreen(api: _apiClient),
        SubscriptionsScreen(api: _apiClient),
        ProfileScreen(profileStorage: _profileStorage),
      ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(index: _index, children: _pages),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.dashboard_outlined),
            selectedIcon: Icon(Icons.dashboard),
            label: 'Inicio',
          ),
          NavigationDestination(
            icon: Icon(Icons.map_outlined),
            selectedIcon: Icon(Icons.map),
            label: 'Mapa',
          ),
          NavigationDestination(
            icon: Icon(Icons.chat_bubble_outline),
            selectedIcon: Icon(Icons.chat_bubble),
            label: 'Chat',
          ),
          NavigationDestination(
            icon: Icon(Icons.notifications_none),
            selectedIcon: Icon(Icons.notifications_active),
            label: 'Alertas',
          ),
          NavigationDestination(
            icon: Icon(Icons.person_outline),
            selectedIcon: Icon(Icons.person),
            label: 'Perfil',
          ),
        ],
      ),
    );
  }
}
