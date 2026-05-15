import React from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';
import { Colors, BorderRadius, Spacing, FontSize } from '../theme';

interface Props {
  skills: string[];
  variant?: 'success' | 'danger' | 'normal';
  dark?: boolean;
}

export default function SkillTags({ skills, variant = 'normal', dark = false }: Props) {
  const c = dark ? Colors.dark : Colors.light;
  const bgMap = { success: c.successBg, danger: c.dangerBg, normal: c.surfaceAlt };
  const colorMap = { success: c.success, danger: c.danger, normal: c.primary };

  if (!skills || skills.length === 0) return null;

  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.scroll}>
      <View style={styles.container}>
        {skills.map((skill, i) => (
          <View key={i} style={[styles.tag, { backgroundColor: bgMap[variant] }]}>
            <Text style={[styles.tagText, { color: colorMap[variant] }]}>{skill}</Text>
          </View>
        ))}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { flexGrow: 0 },
  container: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.xs },
  tag: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: 3,
    borderRadius: BorderRadius.sm,
  },
  tagText: { fontSize: FontSize.xs, fontWeight: '600' },
});
