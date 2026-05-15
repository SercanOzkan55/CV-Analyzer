import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { Text } from 'react-native';
import { useAuth } from '../contexts/AuthContext';
import { Colors } from '../theme';

import LoginScreen from '../screens/LoginScreen';
import RegisterScreen from '../screens/RegisterScreen';
import AnalyzeScreen from '../screens/AnalyzeScreen';
import ResultsScreen from '../screens/ResultsScreen';
import RecruiterScreen from '../screens/RecruiterScreen';
import CameraScanScreen from '../screens/CameraScanScreen';
import HistoryScreen from '../screens/HistoryScreen';
import ProfileScreen from '../screens/ProfileScreen';

const AuthStack = createNativeStackNavigator();
const MainStack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

function AuthNavigator() {
  return (
    <AuthStack.Navigator screenOptions={{ headerShown: false }}>
      <AuthStack.Screen name="Login" component={LoginScreen} />
      <AuthStack.Screen name="Register" component={RegisterScreen} />
    </AuthStack.Navigator>
  );
}

function AnalyzeStack() {
  return (
    <MainStack.Navigator>
      <MainStack.Screen name="AnalyzeHome" component={AnalyzeScreen} options={{ title: 'Analyze CV' }} />
      <MainStack.Screen name="Results" component={ResultsScreen} options={{ title: 'Results' }} />
    </MainStack.Navigator>
  );
}

function HistoryStack() {
  return (
    <MainStack.Navigator>
      <MainStack.Screen name="HistoryHome" component={HistoryScreen} options={{ title: 'History' }} />
      <MainStack.Screen name="Results" component={ResultsScreen} options={{ title: 'Results' }} />
    </MainStack.Navigator>
  );
}

function RecruiterStack() {
  return (
    <MainStack.Navigator>
      <MainStack.Screen name="RecruiterHome" component={RecruiterScreen} options={{ title: 'Recruiter Dashboard' }} />
      <MainStack.Screen name="CameraScan" component={CameraScanScreen} options={{ title: '📷 Scan CV' }} />
    </MainStack.Navigator>
  );
}

function TabIcon({ label, focused }: { label: string; focused: boolean }) {
  const icons: Record<string, string> = {
    Analyze: '📝',
    Recruiter: '👔',
    History: '📊',
    Profile: '👤',
  };
  return <Text style={{ fontSize: focused ? 22 : 20 }}>{icons[label] || '📄'}</Text>;
}

function MainTabNavigator() {
  const c = Colors.light;
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        tabBarIcon: ({ focused }) => <TabIcon label={route.name} focused={focused} />,
        tabBarActiveTintColor: c.primary,
        tabBarInactiveTintColor: c.textMuted,
        tabBarStyle: {
          backgroundColor: c.tabBar,
          borderTopColor: c.tabBarBorder,
          paddingBottom: 4,
          height: 56,
        },
        tabBarLabelStyle: { fontSize: 11, fontWeight: '600' },
        headerShown: false,
      })}
    >
      <Tab.Screen name="Analyze" component={AnalyzeStack} />
      <Tab.Screen name="Recruiter" component={RecruiterStack}
        options={{ headerShown: false }} />
      <Tab.Screen name="History" component={HistoryStack} />
      <Tab.Screen name="Profile" component={ProfileScreen}
        options={{ headerShown: true, title: 'Profile' }} />
    </Tab.Navigator>
  );
}

export default function RootNavigator() {
  const { token, loading } = useAuth();

  if (loading) {
    return null; // splash screen would show
  }

  return token ? <MainTabNavigator /> : <AuthNavigator />;
}
