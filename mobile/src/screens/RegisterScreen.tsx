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

interface Props { navigation: any; }

export default function RegisterScreen({ navigation }: Props) {
  const { register } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const c = Colors.light;

  async function handleRegister() {
    const errs: Record<string, string> = {};
    if (!email.trim()) errs.email = 'Email is required';
    if (!password) errs.password = 'Password is required';
    else if (password.length < 6) errs.password = 'Minimum 6 characters';
    if (password !== confirm) errs.confirm = 'Passwords do not match';
    if (Object.keys(errs).length) { setErrors(errs); return; }
    setErrors({});

    setLoading(true);
    try {
      await register(email.trim(), password);
      Alert.alert('Success', 'Account created! Please check your email for verification.');
    } catch (err: any) {
      Alert.alert('Registration Failed', err.message || 'Please try again');
    } finally {
      setLoading(false);
    }
  }

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: c.background }]}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={styles.flex}>
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <View style={styles.header}>
            <View style={[styles.iconWrap, { backgroundColor: c.primary + '18' }]}>
              <Text style={styles.iconText}>✨</Text>
            </View>
            <Text style={[styles.title, { color: c.text }]}>Create Account</Text>
            <Text style={[styles.subtitle, { color: c.textSecondary }]}>Join CV Analyzer</Text>
          </View>

          <View style={[styles.formCard, { backgroundColor: c.card, borderColor: c.border }]}>
            <Input label="Email" value={email} onChangeText={setEmail}
              placeholder="you@example.com" keyboardType="email-address"
              autoCapitalize="none" error={errors.email} />
            <Input label="Password" value={password} onChangeText={setPassword}
              placeholder="••••••••" secureTextEntry error={errors.password} />
            <Input label="Confirm Password" value={confirm} onChangeText={setConfirm}
              placeholder="••••••••" secureTextEntry error={errors.confirm} />
            <Button title="Create Account" onPress={handleRegister} loading={loading}
              size="lg" style={{ marginTop: Spacing.sm }} />
          </View>

          <View style={styles.footer}>
            <Text style={[styles.footerText, { color: c.textSecondary }]}>Already have an account? </Text>
            <TouchableOpacity onPress={() => navigation.navigate('Login')}>
              <Text style={[styles.footerLink, { color: c.primary }]}>Sign In</Text>
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
  iconWrap: { width: 72, height: 72, borderRadius: BorderRadius.xl, alignItems: 'center', justifyContent: 'center', marginBottom: Spacing.md },
  iconText: { fontSize: 32 },
  title: { fontSize: FontSize.title, fontWeight: '800' },
  subtitle: { fontSize: FontSize.md, marginTop: Spacing.xs },
  formCard: { borderRadius: BorderRadius.lg, borderWidth: 1, padding: Spacing.xl, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.06, shadowRadius: 8, elevation: 2 },
  footer: { flexDirection: 'row', justifyContent: 'center', marginTop: Spacing.xl },
  footerText: { fontSize: FontSize.md },
  footerLink: { fontSize: FontSize.md, fontWeight: '700' },
});
