import React from 'react';
import { View, Text, StyleSheet, ViewStyle } from 'react-native';
import { Colors, BorderRadius, Spacing, FontSize } from '../theme';

interface Props {
  title?: string;
  children: React.ReactNode;
  style?: ViewStyle;
  headerRight?: React.ReactNode;
}

export default function Card({ title, children, style, headerRight }: Props) {
  const c = Colors.light;
  return (
    <View style={[styles.card, { backgroundColor: c.card, borderColor: c.border, shadowColor: c.shadow }, style]}>
      {title && (
        <View style={styles.header}>
          <Text style={[styles.title, { color: c.text }]}>{title}</Text>
          {headerRight}
        </View>
      )}
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: BorderRadius.lg,
    borderWidth: 1,
    padding: Spacing.lg,
    marginBottom: Spacing.md,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 2,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing.md,
  },
  title: {
    fontSize: FontSize.lg,
    fontWeight: '700',
    flex: 1,
  },
});
