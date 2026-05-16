import React, { useState } from 'react';
import {
  View, Text, StyleSheet, KeyboardAvoidingView, Platform,
  ScrollView, TouchableOpacity, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '../contexts/AuthContext';
import Input from '../components/Input';
import Button from '../components/Button';
import { Colors, Spacing, FontSize, BorderRadius } from '../theme';

interface Props {
  navigation: any;
}

export default function LoginScreen({ navigation }: Props) {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const c = Colors.light;

  async function handleLogin() {
    const errs: typeof errors = {};
    if (!email.trim()) errs.email = 'Email is required';
    if (!password) errs.password = 'Password is required';
    if (Object.keys(errs).length) { setErrors(errs); return; }
    setErrors({});

    setLoading(true);
    try {
      await login(email.trim(), password);
    } catch (err: any) {
      Alert.alert('Login Failed', err.message || 'Please check your credentials');
    } finally {
      setLoading(false);
    }
  }

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: c.background }]}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.flex}
      >
        <ScrollView
          contentContainerStyle={styles.scroll}
          keyboardShouldPersistTaps="handled"
        >
          {/* Header */}
          <View style={styles.header}>
            <View style={[styles.iconWrap, { backgroundColor: c.primary + '18' }]}>
              <Text style={styles.iconText}>📄</Text>
            </View>
            <Text style={[styles.title, { color: c.text }]}>CV Analyzer</Text>
            <Text style={[styles.subtitle, { color: c.textSecondary }]}>
              Sign in to your account
            </Text>
          </View>

          {/* Form */}
          <View style={[styles.formCard, { backgroundColor: c.card, borderColor: c.border }]}>
            <Input
              label="Email"
              value={email}
              onChangeText={setEmail}
              placeholder="you@example.com"
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
              error={errors.email}
            />
            <Input
              label="Password"
              value={password}
              onChangeText={setPassword}
              placeholder="••••••••"
              secureTextEntry
              error={errors.password}
            />
            <Button
              title="Sign In"
              onPress={handleLogin}
              loading={loading}
              size="lg"
              style={{ marginTop: Spacing.sm }}
            />
          </View>

          {/* Register link */}
          <View style={styles.footer}>
            <Text style={[styles.footerText, { color: c.textSecondary }]}>
              Don't have an account?{' '}
            </Text>
            <TouchableOpacity onPress={() => navigation.navigate('Register')}>
              <Text style={[styles.footerLink, { color: c.primary }]}>Sign Up</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  flex: { flex: 1 },
  scroll: { flexGrow: 1, justifyContent: 'center', padding: Spacing.xl },
  header: { alignItems: 'center', marginBottom: Spacing.xxxl },
  iconWrap: {
    width: 72, height: 72, borderRadius: BorderRadius.xl,
    alignItems: 'center', justifyContent: 'center', marginBottom: Spacing.md,
  },
  iconText: { fontSize: 32 },
  title: { fontSize: FontSize.title, fontWeight: '800' },
  subtitle: { fontSize: FontSize.md, marginTop: Spacing.xs },
  formCard: {
    borderRadius: BorderRadius.lg, borderWidth: 1,
    padding: Spacing.xl, shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.06,
    shadowRadius: 8, elevation: 2,
  },
  footer: { flexDirection: 'row', justifyContent: 'center', marginTop: Spacing.xl },
  footerText: { fontSize: FontSize.md },
  footerLink: { fontSize: FontSize.md, fontWeight: '700' },
});
