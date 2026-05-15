import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity, ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '../contexts/AuthContext';
import { getHistory } from '../api/client';
import Card from '../components/Card';
import ScoreCircle from '../components/ScoreCircle';
import SkillTags from '../components/SkillTags';
import { Colors, Spacing, FontSize, BorderRadius, getScoreColor } from '../theme';

export default function HistoryScreen({ navigation }: any) {
  const { token } = useAuth();
  const c = Colors.light;

  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const data = await getHistory(token);
      setItems(Array.isArray(data) ? data : data?.history || []);
    } catch { setItems([]); }
    finally { setLoading(false); setRefreshing(false); }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  function onRefresh() {
    setRefreshing(true);
    load();
  }

  function renderItem({ item }: any) {
    const score = item.final_score ?? item.overall_score ?? item.score ?? 0;
    const name = item.filename || item.candidate_name || 'Untitled';
    const date = item.created_at ? new Date(item.created_at).toLocaleDateString() : '';
    const missing = item.missing_skills || [];
    const detected = item.detected_skills || item.skills || [];

    return (
      <TouchableOpacity
        style={[styles.card, { backgroundColor: c.card, borderColor: c.border }]}
        activeOpacity={0.7}
        onPress={() => navigation.navigate('Results', { result: item })}
      >
        <View style={styles.row}>
          <ScoreCircle score={score} size={50} />
          <View style={styles.info}>
            <Text style={[styles.name, { color: c.text }]} numberOfLines={1}>{name}</Text>
            {date ? <Text style={[styles.date, { color: c.textMuted }]}>{date}</Text> : null}
          </View>
          <View style={styles.scoreLabelWrap}>
            <Text style={[styles.scoreLabel, { color: getScoreColor(score) }]}>{Math.round(score)}%</Text>
          </View>
        </View>
        {detected.length > 0 && (
          <View style={{ marginTop: Spacing.sm }}>
            <SkillTags skills={detected.slice(0, 4)} variant="success" />
          </View>
        )}
        {missing.length > 0 && (
          <View style={{ marginTop: Spacing.xs }}>
            <SkillTags skills={missing.slice(0, 3)} variant="danger" />
          </View>
        )}
      </TouchableOpacity>
    );
  }

  if (loading) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: c.background }]} edges={['bottom']}>
        <ActivityIndicator size="large" color={c.primary} style={{ flex: 1 }} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: c.background }]} edges={['bottom']}>
      {items.length === 0 ? (
        <View style={styles.emptyWrap}>
          <Text style={{ fontSize: 48, marginBottom: Spacing.lg }}>📄</Text>
          <Text style={[styles.emptyTitle, { color: c.text }]}>No analysis history yet</Text>
          <Text style={{ color: c.textMuted, textAlign: 'center' }}>
            Analyze a CV to see results here
          </Text>
        </View>
      ) : (
        <FlatList
          data={items}
          renderItem={renderItem}
          keyExtractor={(item, i) => item.id?.toString() || `${i}`}
          contentContainerStyle={styles.list}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={c.primary} />}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  list: { padding: Spacing.lg, paddingBottom: 40 },
  card: {
    borderRadius: BorderRadius.lg, borderWidth: 1,
    padding: Spacing.md, marginBottom: Spacing.md,
  },
  row: { flexDirection: 'row', alignItems: 'center', gap: Spacing.md },
  info: { flex: 1 },
  name: { fontWeight: '700', fontSize: FontSize.md },
  date: { fontSize: FontSize.xs, marginTop: 2 },
  scoreLabelWrap: { alignItems: 'flex-end' },
  scoreLabel: { fontWeight: '700', fontSize: FontSize.lg, fontFamily: 'monospace' },
  emptyWrap: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: Spacing.xl },
  emptyTitle: { fontSize: FontSize.xl, fontWeight: '700', marginBottom: Spacing.xs },
});
