import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, Alert, TextInput,
  TouchableOpacity, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as DocumentPicker from 'expo-document-picker';
import * as FileSystem from 'expo-file-system';
import { useAuth } from '../contexts/AuthContext';
import { analyzeCV, analyzePdf } from '../api/client';
import Card from '../components/Card';
import Button from '../components/Button';
import { Colors, Spacing, FontSize, BorderRadius } from '../theme';

interface Props { navigation: any; }

export default function AnalyzeScreen({ navigation }: Props) {
  const { token } = useAuth();
  const c = Colors.light;

  const [mode, setMode] = useState<'text' | 'pdf'>('pdf');
  const [cvText, setCvText] = useState('');
  const [jdText, setJdText] = useState('');
  const [pdfName, setPdfName] = useState('');
  const [pdfUri, setPdfUri] = useState('');
  const [loading, setLoading] = useState(false);

  const pickPdf = useCallback(async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: 'application/pdf',
        copyToCacheDirectory: true,
      });
      if (!result.canceled && result.assets?.[0]) {
        const asset = result.assets[0];
        setPdfUri(asset.uri);
        setPdfName(asset.name || 'cv.pdf');
      }
    } catch {
      Alert.alert('Error', 'Failed to pick PDF file');
    }
  }, []);

  const handleAnalyze = useCallback(async () => {
    if (!token) { Alert.alert('Error', 'Please sign in first'); return; }

    if (mode === 'text') {
      if (!cvText.trim()) { Alert.alert('Error', 'Please enter CV text'); return; }
      setLoading(true);
      try {
        const result = await analyzeCV(token, cvText, jdText);
        navigation.navigate('Results', { result, cvText, jdText });
      } catch (err: any) {
        Alert.alert('Analysis Failed', err.message);
      } finally {
        setLoading(false);
      }
    } else {
      if (!pdfUri) { Alert.alert('Error', 'Please select a PDF file'); return; }
      setLoading(true);
      try {
        const fileInfo = await FileSystem.getInfoAsync(pdfUri);
        if (!fileInfo.exists) throw new Error('File not found');

        const formData = new FormData();
        formData.append('file', {
          uri: pdfUri,
          type: 'application/pdf',
          name: pdfName || 'cv.pdf',
        } as any);
        formData.append('job_description', jdText);

        const result = await analyzePdf(token, formData);
        navigation.navigate('Results', { result, cvText: '', jdText });
      } catch (err: any) {
        Alert.alert('Analysis Failed', err.message);
      } finally {
        setLoading(false);
      }
    }
  }, [token, mode, cvText, jdText, pdfUri, pdfName, navigation]);

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: c.background }]} edges={['bottom']}>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">

        {/* Mode Toggle */}
        <Card>
          <View style={styles.modeRow}>
            <TouchableOpacity
              style={[styles.modeBtn, mode === 'pdf' && { backgroundColor: c.primary }]}
              onPress={() => setMode('pdf')}
            >
              <Text style={[styles.modeBtnText, mode === 'pdf' && { color: '#fff' }]}>📄 PDF Upload</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.modeBtn, mode === 'text' && { backgroundColor: c.primary }]}
              onPress={() => setMode('text')}
            >
              <Text style={[styles.modeBtnText, mode === 'text' && { color: '#fff' }]}>✏️ Paste Text</Text>
            </TouchableOpacity>
          </View>
        </Card>

        {/* CV Input */}
        <Card title={mode === 'pdf' ? 'Upload CV' : 'CV Text'}>
          {mode === 'pdf' ? (
            <View>
              <TouchableOpacity
                style={[styles.dropzone, { borderColor: c.border, backgroundColor: c.surfaceAlt }]}
                onPress={pickPdf}
              >
                <Text style={{ fontSize: 36, marginBottom: Spacing.sm }}>📁</Text>
                <Text style={[styles.dropTitle, { color: c.text }]}>
                  {pdfName || 'Tap to select PDF'}
                </Text>
                <Text style={[styles.dropHint, { color: c.textMuted }]}>
                  PDF files only, max 10 MB
                </Text>
              </TouchableOpacity>
              {pdfName ? (
                <View style={[styles.fileChip, { backgroundColor: c.primary + '15' }]}>
                  <Text style={{ color: c.primary, fontWeight: '600', fontSize: FontSize.sm }}>
                    📎 {pdfName}
                  </Text>
                  <TouchableOpacity onPress={() => { setPdfUri(''); setPdfName(''); }}>
                    <Text style={{ color: c.danger, fontSize: 18, marginLeft: Spacing.sm }}>✕</Text>
                  </TouchableOpacity>
                </View>
              ) : null}
            </View>
          ) : (
            <TextInput
              style={[styles.textarea, { borderColor: c.border, backgroundColor: c.surface, color: c.text }]}
              value={cvText}
              onChangeText={setCvText}
              placeholder="Paste your CV text here..."
              placeholderTextColor={c.textMuted}
              multiline
              textAlignVertical="top"
            />
          )}
        </Card>

        {/* Job Description */}
        <Card title="Job Description (Optional)">
          <TextInput
            style={[styles.textarea, { borderColor: c.border, backgroundColor: c.surface, color: c.text }]}
            value={jdText}
            onChangeText={setJdText}
            placeholder="Paste job description for matching analysis, or leave empty for ATS check..."
            placeholderTextColor={c.textMuted}
            multiline
            textAlignVertical="top"
          />
        </Card>

        {/* Analyze Button */}
        <Button
          title={loading ? 'Analyzing...' : 'Analyze CV'}
          onPress={handleAnalyze}
          loading={loading}
          size="lg"
          style={{ marginBottom: Spacing.xxxl }}
          icon={!loading ? <Text style={{ fontSize: 18 }}>🔍</Text> : undefined}
        />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { padding: Spacing.lg },
  modeRow: { flexDirection: 'row', gap: Spacing.sm },
  modeBtn: {
    flex: 1, paddingVertical: Spacing.sm, borderRadius: BorderRadius.md,
    alignItems: 'center', backgroundColor: 'transparent',
  },
  modeBtnText: { fontWeight: '600', fontSize: FontSize.sm, color: Colors.light.textSecondary },
  dropzone: {
    borderWidth: 2, borderStyle: 'dashed', borderRadius: BorderRadius.lg,
    paddingVertical: Spacing.xxxl, alignItems: 'center',
  },
  dropTitle: { fontSize: FontSize.md, fontWeight: '600' },
  dropHint: { fontSize: FontSize.xs, marginTop: Spacing.xs },
  fileChip: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    padding: Spacing.md, borderRadius: BorderRadius.md, marginTop: Spacing.md,
  },
  textarea: {
    borderWidth: 1.5, borderRadius: BorderRadius.md,
    padding: Spacing.md, minHeight: 120, fontSize: FontSize.md,
    lineHeight: 22,
  },
});
