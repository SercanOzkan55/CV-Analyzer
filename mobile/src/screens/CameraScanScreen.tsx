import React, { useState, useRef, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, Alert, Image,
  TouchableOpacity, ActivityIndicator, Dimensions, Platform,
  NativeModules,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as FileSystem from 'expo-file-system';
import { useAuth } from '../contexts/AuthContext';
import { scanCV } from '../api/client';
import Card from '../components/Card';
import Button from '../components/Button';
import ScoreCircle from '../components/ScoreCircle';
import { Colors, Spacing, FontSize, BorderRadius, getScoreColor } from '../theme';

const { width: SCREEN_W } = Dimensions.get('window');

/**
 * Get device locale (ISO 639-1 code) for OCR language selection.
 */
function getDeviceLang(): string {
  try {
    const loc =
      Platform.OS === 'ios'
        ? NativeModules.SettingsManager?.settings?.AppleLocale ||
          NativeModules.SettingsManager?.settings?.AppleLanguages?.[0] ||
          'en'
        : NativeModules.I18nManager?.localeIdentifier || 'en';
    return (loc as string).slice(0, 2).toLowerCase();
  } catch {
    return 'en';
  }
}

type ScanPhase = 'capture' | 'preview' | 'analyzing' | 'results';

export default function CameraScanScreen({ navigation }: any) {
  const { token } = useAuth();
  const c = Colors.light;
  const cameraRef = useRef<any>(null);

  const [permission, requestPermission] = useCameraPermissions();
  const [phase, setPhase] = useState<ScanPhase>('capture');
  const [capturedPages, setCapturedPages] = useState<{ uri: string }[]>([]);
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');

  // ── Camera capture ──
  const takePicture = useCallback(async () => {
    if (!cameraRef.current) return;
    try {
      const photo = await cameraRef.current.takePictureAsync({
        quality: 0.85,
        base64: false,
        skipProcessing: false,
      });
      setCapturedPages(prev => [...prev, { uri: photo.uri }]);
    } catch (err: any) {
      Alert.alert('Error', 'Failed to capture photo');
    }
  }, []);

  const removePage = (index: number) => {
    setCapturedPages(prev => prev.filter((_, i) => i !== index));
  };

  const resetScan = () => {
    setCapturedPages([]);
    setPhase('capture');
    setResult(null);
    setError('');
  };

  // ── Send to backend ──
  const handleAnalyze = useCallback(async () => {
    if (!token || !capturedPages.length) return;
    setPhase('analyzing');
    setAnalyzing(true);
    setError('');

    try {
      const formData = new FormData();
      for (let i = 0; i < capturedPages.length; i++) {
        const page = capturedPages[i];
        formData.append('images', {
          uri: page.uri,
          type: 'image/jpeg',
          name: `cv_page_${i + 1}.jpg`,
        } as any);
      }
      formData.append('job_description', '');
      formData.append('lang', getDeviceLang());

      const data = await scanCV(token, formData);
      setResult(data);
      setPhase('results');
    } catch (err: any) {
      setError(err.message || 'Analysis failed');
      setPhase('preview');
      Alert.alert('Error', err.message || 'Scan analysis failed');
    } finally {
      setAnalyzing(false);
    }
  }, [token, capturedPages]);

  // ── Download PDF ──
  const handleDownloadPdf = useCallback(async () => {
    if (!result?.pdf_base64) {
      Alert.alert('Error', 'No PDF available');
      return;
    }
    try {
      const path = `${FileSystem.documentDirectory}scanned_cv_${Date.now()}.pdf`;
      await FileSystem.writeAsStringAsync(path, result.pdf_base64, {
        encoding: FileSystem.EncodingType.Base64,
      });
      Alert.alert('Success', `PDF saved to device:\n${path}`);
    } catch (err: any) {
      Alert.alert('Error', 'Failed to save PDF');
    }
  }, [result]);

  // ── Permission check ──
  if (!permission) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: c.background }]}>
        <ActivityIndicator size="large" color={c.primary} />
      </SafeAreaView>
    );
  }
  if (!permission.granted) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: c.background }]}>
        <View style={styles.permissionBox}>
          <Text style={[styles.permIcon]}>📷</Text>
          <Text style={[styles.permTitle, { color: c.text }]}>Camera Permission Required</Text>
          <Text style={[styles.permDesc, { color: c.textSecondary }]}>
            Grant camera access to scan physical CVs for instant ATS analysis.
          </Text>
          <Button title="Grant Permission" onPress={requestPermission} />
        </View>
      </SafeAreaView>
    );
  }

  // ── Results view ──
  if (phase === 'results' && result) {
    const atsScore = result.ats_score ?? result.final_score ?? 0;
    const sections = result.ats?.section_scores || [];
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: c.background }]}>
        <ScrollView contentContainerStyle={styles.scrollContent}>
          {/* Header */}
          <View style={styles.resultsHeader}>
            <Text style={[styles.resultsTitle, { color: c.text }]}>📋 Scan Results</Text>
            <Text style={[styles.resultsSubtitle, { color: c.textSecondary }]}>
              {result.scan_pages} page{result.scan_pages > 1 ? 's' : ''} scanned
            </Text>
          </View>

          {/* Score */}
          <Card title="ATS Score">
            <View style={styles.scoreRow}>
              <ScoreCircle score={Math.round(atsScore)} size={100} />
              <View style={styles.scoreInfo}>
                <Text style={[styles.scoreLabel, { color: c.text }]}>
                  {atsScore >= 75 ? '✅ Strong' : atsScore >= 50 ? '⚠️ Moderate' : '❌ Needs Work'}
                </Text>
                <Text style={[styles.scoreDesc, { color: c.textSecondary }]}>
                  {result.interpretation || 'ATS compatibility score based on scanned CV'}
                </Text>
              </View>
            </View>
          </Card>

          {/* Section scores */}
          {sections.length > 0 && (
            <Card title="Section Breakdown">
              {sections.map((sec: any, i: number) => (
                <View key={i} style={styles.sectionRow}>
                  <Text style={[styles.sectionLabel, { color: c.text }]}>
                    {sec.label?.en || sec.label || sec.name || `Section ${i + 1}`}
                  </Text>
                  <View style={[styles.sectionBadge, { backgroundColor: getScoreColor(sec.score) + '20' }]}>
                    <Text style={[styles.sectionScore, { color: getScoreColor(sec.score) }]}>
                      {sec.score}%
                    </Text>
                  </View>
                </View>
              ))}
            </Card>
          )}

          {/* Skills */}
          {result.detected_skills?.length > 0 && (
            <Card title="Detected Skills">
              <View style={styles.skillsWrap}>
                {result.detected_skills.map((skill: string, i: number) => (
                  <View key={i} style={[styles.skillChip, { backgroundColor: c.primaryLight + '20' }]}>
                    <Text style={[styles.skillText, { color: c.primary }]}>{skill}</Text>
                  </View>
                ))}
              </View>
            </Card>
          )}

          {/* Missing skills */}
          {result.missing_skills?.length > 0 && (
            <Card title="Missing Skills">
              <View style={styles.skillsWrap}>
                {result.missing_skills.map((skill: string, i: number) => (
                  <View key={i} style={[styles.skillChip, { backgroundColor: c.dangerBg }]}>
                    <Text style={[styles.skillText, { color: c.danger }]}>{skill}</Text>
                  </View>
                ))}
              </View>
            </Card>
          )}

          {/* OCR Text preview */}
          <Card title="Extracted Text">
            <Text style={[styles.ocrText, { color: c.textSecondary }]} numberOfLines={20}>
              {result.ocr_text || '(empty)'}
            </Text>
          </Card>

          {/* Actions */}
          <View style={styles.actionsRow}>
            {result.pdf_base64 && (
              <Button title="📥 Download PDF" onPress={handleDownloadPdf} variant="primary" />
            )}
            <Button title="📷 New Scan" onPress={resetScan} variant="outline" />
          </View>

          <View style={{ height: 40 }} />
        </ScrollView>
      </SafeAreaView>
    );
  }

  // ── Analyzing view ──
  if (phase === 'analyzing') {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: c.background }]}>
        <View style={styles.analyzingBox}>
          <ActivityIndicator size="large" color={c.primary} />
          <Text style={[styles.analyzingText, { color: c.text }]}>Analyzing scanned CV...</Text>
          <Text style={[styles.analyzingSubtext, { color: c.textSecondary }]}>
            OCR extraction + ATS analysis + PDF generation
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  // ── Preview captured pages ──
  if (phase === 'preview' || capturedPages.length > 0) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: c.background }]}>
        <ScrollView contentContainerStyle={styles.scrollContent}>
          <Text style={[styles.sectionTitle, { color: c.text }]}>
            📄 Captured Pages ({capturedPages.length})
          </Text>
          <Text style={[styles.hint, { color: c.textSecondary }]}>
            Tap a page to remove it. Add more pages or start analysis.
          </Text>

          <View style={styles.pagesGrid}>
            {capturedPages.map((page, idx) => (
              <TouchableOpacity
                key={idx}
                style={[styles.pageThumb, { borderColor: c.border }]}
                onPress={() => removePage(idx)}
                activeOpacity={0.7}
              >
                <Image source={{ uri: page.uri }} style={styles.pageImage} resizeMode="cover" />
                <View style={[styles.pageOverlay, { backgroundColor: 'rgba(0,0,0,0.5)' }]}>
                  <Text style={styles.pageNumber}>Page {idx + 1}</Text>
                  <Text style={styles.removeHint}>Tap to remove</Text>
                </View>
              </TouchableOpacity>
            ))}

            {/* Add more button */}
            <TouchableOpacity
              style={[styles.pageThumb, styles.addPageBtn, { borderColor: c.primary, backgroundColor: c.primaryLight + '10' }]}
              onPress={() => setPhase('capture')}
            >
              <Text style={[styles.addPageIcon, { color: c.primary }]}>📷</Text>
              <Text style={[styles.addPageText, { color: c.primary }]}>Add Page</Text>
            </TouchableOpacity>
          </View>

          {error ? (
            <Text style={[styles.errorText, { color: c.danger }]}>{error}</Text>
          ) : null}

          <View style={styles.previewActions}>
            <Button
              title="🔍 Analyze CV"
              onPress={handleAnalyze}
              loading={analyzing}
              disabled={capturedPages.length === 0}
              size="lg"
            />
            <Button
              title="🗑️ Clear All"
              onPress={resetScan}
              variant="danger"
              style={{ marginTop: Spacing.sm }}
            />
          </View>
        </ScrollView>
      </SafeAreaView>
    );
  }

  // ── Camera capture view ──
  return (
    <SafeAreaView style={[styles.container, { backgroundColor: '#000' }]}>
      <CameraView
        ref={cameraRef}
        style={styles.camera}
        facing="back"
      >
        {/* Overlay guide */}
        <View style={styles.cameraOverlay}>
          <View style={styles.guideTop}>
            <Text style={styles.guideText}>
              📄 Position the CV within the frame
            </Text>
            {capturedPages.length > 0 && (
              <Text style={styles.pageCount}>
                {capturedPages.length} page{capturedPages.length > 1 ? 's' : ''} captured
              </Text>
            )}
          </View>

          {/* Corner guides */}
          <View style={styles.guideFrame}>
            <View style={[styles.corner, styles.cornerTL]} />
            <View style={[styles.corner, styles.cornerTR]} />
            <View style={[styles.corner, styles.cornerBL]} />
            <View style={[styles.corner, styles.cornerBR]} />
          </View>

          {/* Bottom controls */}
          <View style={styles.cameraControls}>
            <TouchableOpacity
              style={[styles.controlBtn, { backgroundColor: 'rgba(255,255,255,0.2)' }]}
              onPress={resetScan}
            >
              <Text style={styles.controlBtnText}>✖</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.captureBtn}
              onPress={takePicture}
              activeOpacity={0.7}
            >
              <View style={styles.captureBtnInner} />
            </TouchableOpacity>

            {capturedPages.length > 0 ? (
              <TouchableOpacity
                style={[styles.controlBtn, { backgroundColor: Colors.light.primary }]}
                onPress={() => setPhase('preview')}
              >
                <Text style={styles.controlBtnText}>✓ {capturedPages.length}</Text>
              </TouchableOpacity>
            ) : (
              <View style={styles.controlBtn} />
            )}
          </View>
        </View>
      </CameraView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  scrollContent: { padding: Spacing.lg },

  // Permission
  permissionBox: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: Spacing.xxl },
  permIcon: { fontSize: 64, marginBottom: Spacing.lg },
  permTitle: { fontSize: FontSize.xl, fontWeight: '700', marginBottom: Spacing.sm, textAlign: 'center' },
  permDesc: { fontSize: FontSize.md, textAlign: 'center', marginBottom: Spacing.xl, lineHeight: 22 },

  // Camera
  camera: { flex: 1 },
  cameraOverlay: { flex: 1, justifyContent: 'space-between' },
  guideTop: { alignItems: 'center', paddingTop: 20, paddingHorizontal: Spacing.lg },
  guideText: { color: '#fff', fontSize: FontSize.md, fontWeight: '600', textShadowColor: '#000', textShadowRadius: 4, textShadowOffset: { width: 0, height: 1 } },
  pageCount: { color: '#fff', fontSize: FontSize.sm, marginTop: 4, backgroundColor: 'rgba(99,102,241,0.6)', paddingHorizontal: 10, paddingVertical: 3, borderRadius: 10, overflow: 'hidden' },

  guideFrame: { position: 'absolute', top: '15%', left: '8%', right: '8%', bottom: '22%' },
  corner: { position: 'absolute', width: 30, height: 30, borderColor: '#fff' },
  cornerTL: { top: 0, left: 0, borderTopWidth: 3, borderLeftWidth: 3 },
  cornerTR: { top: 0, right: 0, borderTopWidth: 3, borderRightWidth: 3 },
  cornerBL: { bottom: 0, left: 0, borderBottomWidth: 3, borderLeftWidth: 3 },
  cornerBR: { bottom: 0, right: 0, borderBottomWidth: 3, borderRightWidth: 3 },

  cameraControls: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-around', paddingBottom: 30, paddingHorizontal: 30 },
  controlBtn: { width: 50, height: 50, borderRadius: 25, alignItems: 'center', justifyContent: 'center' },
  controlBtnText: { color: '#fff', fontSize: 18, fontWeight: '700' },
  captureBtn: { width: 75, height: 75, borderRadius: 37.5, borderWidth: 4, borderColor: '#fff', alignItems: 'center', justifyContent: 'center' },
  captureBtnInner: { width: 60, height: 60, borderRadius: 30, backgroundColor: '#fff' },

  // Preview
  sectionTitle: { fontSize: FontSize.xl, fontWeight: '700', marginBottom: Spacing.xs },
  hint: { fontSize: FontSize.sm, marginBottom: Spacing.lg },
  pagesGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.md },
  pageThumb: { width: (SCREEN_W - Spacing.lg * 2 - Spacing.md * 2) / 3, height: 160, borderRadius: BorderRadius.md, borderWidth: 1, overflow: 'hidden' },
  pageImage: { width: '100%', height: '100%' },
  pageOverlay: { position: 'absolute', bottom: 0, left: 0, right: 0, padding: 4, alignItems: 'center' },
  pageNumber: { color: '#fff', fontSize: FontSize.xs, fontWeight: '700' },
  removeHint: { color: '#fff', fontSize: 9, opacity: 0.8 },
  addPageBtn: { alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderStyle: 'dashed' },
  addPageIcon: { fontSize: 28, marginBottom: 4 },
  addPageText: { fontSize: FontSize.xs, fontWeight: '600' },
  previewActions: { marginTop: Spacing.xl },
  errorText: { fontSize: FontSize.sm, marginTop: Spacing.sm, textAlign: 'center' },

  // Analyzing
  analyzingBox: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: Spacing.xxl },
  analyzingText: { fontSize: FontSize.lg, fontWeight: '600', marginTop: Spacing.lg },
  analyzingSubtext: { fontSize: FontSize.sm, marginTop: Spacing.xs },

  // Results
  resultsHeader: { alignItems: 'center', marginBottom: Spacing.lg },
  resultsTitle: { fontSize: FontSize.xxl, fontWeight: '700' },
  resultsSubtitle: { fontSize: FontSize.sm, marginTop: 2 },
  scoreRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.lg },
  scoreInfo: { flex: 1 },
  scoreLabel: { fontSize: FontSize.lg, fontWeight: '700', marginBottom: 4 },
  scoreDesc: { fontSize: FontSize.sm, lineHeight: 20 },
  sectionRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: Spacing.sm, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: '#e2e8f0' },
  sectionLabel: { fontSize: FontSize.md, flex: 1 },
  sectionBadge: { paddingHorizontal: 10, paddingVertical: 3, borderRadius: 8 },
  sectionScore: { fontSize: FontSize.sm, fontWeight: '700' },
  skillsWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  skillChip: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 },
  skillText: { fontSize: FontSize.xs, fontWeight: '600' },
  ocrText: { fontSize: FontSize.xs, lineHeight: 18, fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace' },
  actionsRow: { gap: Spacing.sm, marginTop: Spacing.lg },
});
