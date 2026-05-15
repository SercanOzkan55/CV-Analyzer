import React, { useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Alert, Linking } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '../contexts/AuthContext';
import Card from '../components/Card';
import Button from '../components/Button';
import { Colors, Spacing, FontSize, BorderRadius } from '../theme';

export default function ProfileScreen() {
  const { user, logout } = useAuth();
  const c = Colors.light;
  const [loggingOut, setLoggingOut] = useState(false);

  async function handleLogout() {
    Alert.alert('Logout', 'Are you sure you want to log out?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Logout', style: 'destructive', onPress: async () => {
          setLoggingOut(true);
          await logout();
        },
      },
    ]);
  }

  const role = user?.role || 'individual';
  const plan = user?.plan || 'free';
  const email = user?.email || '-';

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: c.background }]} edges={['bottom']}>
      <ScrollView contentContainerStyle={styles.content}>
        {/* Avatar placeholder */}
        <View style={styles.avatarWrap}>
          <View style={[styles.avatar, { backgroundColor: c.primary }]}>
            <Text style={styles.avatarText}>
              {email.charAt(0).toUpperCase()}
            </Text>
          </View>
          <Text style={[styles.email, { color: c.text }]}>{email}</Text>
        </View>

        <Card title="Account Details">
          <InfoRow label="Email" value={email} c={c} />
          <InfoRow label="Role" value={role} c={c} />
          <InfoRow label="Plan" value={plan} c={c} />
          {user?.organization && (
            <InfoRow label="Organization" value={user.organization} c={c} />
          )}
          {user?.quota_used !== undefined && (
            <InfoRow label="API Usage" value={`${user.quota_used} / ${user.quota_limit || '∞'}`} c={c} />
          )}
        </Card>

        <Card title="App Info">
          <InfoRow label="Version" value="1.0.0" c={c} />
          <InfoRow label="Platform" value="React Native (Expo)" c={c} />
        </Card>

        <Button
          title={loggingOut ? 'Logging out...' : 'Logout'}
          onPress={handleLogout}
          variant="danger"
          size="lg"
          loading={loggingOut}
          style={{ marginTop: Spacing.md }}
        />
      </ScrollView>
    </SafeAreaView>
  );
}

function InfoRow({ label, value, c }: { label: string; value: string; c: any }) {
  return (
    <View style={styles.infoRow}>
      <Text style={[styles.infoLabel, { color: c.textSecondary }]}>{label}</Text>
      <Text style={[styles.infoValue, { color: c.text }]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  content: { padding: Spacing.lg, paddingBottom: 40 },
  avatarWrap: { alignItems: 'center', marginBottom: Spacing.xl },
  avatar: {
    width: 80, height: 80, borderRadius: 40,
    alignItems: 'center', justifyContent: 'center', marginBottom: Spacing.md,
  },
  avatarText: { color: '#fff', fontSize: 32, fontWeight: '700' },
  email: { fontSize: FontSize.lg, fontWeight: '600' },
  infoRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingVertical: Spacing.sm, borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.light.border,
  },
  infoLabel: { fontSize: FontSize.sm },
  infoValue: { fontSize: FontSize.sm, fontWeight: '600' },
});
