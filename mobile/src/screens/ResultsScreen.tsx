import React from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import ScoreCircle from '../components/ScoreCircle';
import SkillTags from '../components/SkillTags';
import Card from '../components/Card';
import Button from '../components/Button';
import { Colors, Spacing, FontSize, BorderRadius } from '../theme';

interface Props { route: any; navigation: any; }

export default function ResultsScreen({ route, navigation }: Props) {
  const { result } = route.params || {};
  const c = Colors.light;

  if (!result) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: c.background }]}>
        <View style={styles.empty}>
          <Text style={{ color: c.textSecondary }}>No results to display</Text>
        </View>
      </SafeAreaView>
    );
  }

  // Use section_scores from ATS details (same as web frontend)
  const sectionScores: any[] = result.ats?.section_scores || [];

  const scores = [
    { label: 'Overall', value: result.final_score, main: true },
    { label: 'ATS', value: result.ats_score },
    { label: 'Skills', value: result.skill_score },
    { label: 'Keywords', value: result.keyword_score },
    { label: 'Experience', value: result.experience_score },
    { label: 'Semantic', value: result.semantic_score },
  ];

  const interpretation = result.interpretation || '';
  const riskLevel = result.risk_level || '';
  const missingSkills = result.missing_skills || [];
  const detectedSkills = result.detected_skills || [];
  const recommendations = result.recommendations || [];

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: c.background }]} edges={['bottom']}>
      <ScrollView contentContainerStyle={styles.scroll}>

        {/* Main Score */}
        <Card>
          <View style={styles.mainScore}>
            <ScoreCircle score={result.final_score || 0} size={120} label="Match" />
            <View style={styles.mainInfo}>
              <Text style={[styles.interpretation, { color: c.text }]}>
                {interpretation}
              </Text>
              {riskLevel ? (
                <View style={[styles.riskBadge, {
                  backgroundColor: riskLevel.toLowerCase().includes('low') ? c.successBg
                    : riskLevel.toLowerCase().includes('high') ? c.dangerBg : c.warningBg,
                }]}>
                  <Text style={[styles.riskText, {
                    color: riskLevel.toLowerCase().includes('low') ? c.success
                      : riskLevel.toLowerCase().includes('high') ? c.danger : c.warning,
                  }]}>
                    {riskLevel}
                  </Text>
                </View>
              ) : null}
            </View>
          </View>
        </Card>

        {/* Score Breakdown (ATS Section Scores - same as web) */}
        {sectionScores.length > 0 ? (
          <Card title="Score Breakdown">
            {sectionScores.map((section: any, i: number) => {
              const score = Math.round(section.score || 0);
              const label = section.label?.en || section.name || '';
              const scoreColor = score >= 70 ? c.success : score >= 50 ? c.warning : c.danger;
              return (
                <View key={i} style={[styles.atsRow, { borderBottomColor: c.border }]}>
                  <View style={styles.atsInfo}>
                    <Text style={[styles.atsName, { color: c.text }]}>{label}</Text>
                    <Text style={[styles.atsStatus, { color: c.textSecondary }]}>
                      {section.status === 'pass' ? '✓ Pass' : section.status === 'warning' ? '⚠ Warning' : section.status === 'fail' ? '✕ Fail' : ''}
                    </Text>
                  </View>
                  <Text style={[styles.atsScore, { color: scoreColor }]}>{score}%</Text>
                </View>
              );
            })}
          </Card>
        ) : (
          <Card title="Score Breakdown">
            <View style={styles.scoreGrid}>
              {scores.filter(s => !s.main).map((s, i) => (
                <View key={i} style={styles.scoreItem}>
                  <ScoreCircle score={s.value || 0} size={60} label={s.label} />
                </View>
              ))}
            </View>
          </Card>
        )}

        {/* Detected Skills */}
        {detectedSkills.length > 0 && (
          <Card title={`Detected Skills (${detectedSkills.length})`}>
            <SkillTags skills={detectedSkills} variant="success" />
          </Card>
        )}

        {/* Missing Skills */}
        {missingSkills.length > 0 && (
          <Card title={`Missing Skills (${missingSkills.length})`}>
            <SkillTags skills={missingSkills} variant="danger" />
          </Card>
        )}

        {/* Recommendations */}
        {recommendations.length > 0 && (
          <Card title="Recommendations">
            {recommendations.map((rec: string, i: number) => (
              <View key={i} style={styles.recRow}>
                <Text style={[styles.recBullet, { color: c.primary }]}>•</Text>
                <Text style={[styles.recText, { color: c.text }]}>{rec}</Text>
              </View>
            ))}
          </Card>
        )}

        {/* Back */}
        <Button
          title="New Analysis"
          onPress={() => navigation.goBack()}
          variant="outline"
          size="lg"
          style={{ marginBottom: Spacing.xxxl }}
        />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { padding: Spacing.lg },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  mainScore: { flexDirection: 'row', alignItems: 'center', gap: Spacing.xl },
  mainInfo: { flex: 1 },
  interpretation: { fontSize: FontSize.md, fontWeight: '600', lineHeight: 22 },
  riskBadge: { alignSelf: 'flex-start', paddingHorizontal: Spacing.md, paddingVertical: 4, borderRadius: BorderRadius.sm, marginTop: Spacing.sm },
  riskText: { fontSize: FontSize.xs, fontWeight: '700' },
  scoreGrid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-around', gap: Spacing.md },
  scoreItem: { alignItems: 'center', width: '28%' },
  recRow: { flexDirection: 'row', marginBottom: Spacing.sm, gap: Spacing.sm },
  recBullet: { fontSize: FontSize.lg, lineHeight: 22 },
  recText: { flex: 1, fontSize: FontSize.sm, lineHeight: 20 },
  atsRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: Spacing.sm, borderBottomWidth: 1 },
  atsInfo: { flex: 1 },
  atsName: { fontSize: FontSize.sm, fontWeight: '600' },
  atsStatus: { fontSize: FontSize.xs, marginTop: 2 },
  atsScore: { fontSize: FontSize.md, fontWeight: '700', fontFamily: 'monospace' },
});
