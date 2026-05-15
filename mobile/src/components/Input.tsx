import React from 'react';
import { TextInput, View, Text, StyleSheet, TextInputProps, ViewStyle } from 'react-native';
import { Colors, BorderRadius, Spacing, FontSize } from '../theme';

interface Props extends TextInputProps {
  label?: string;
  error?: string;
  containerStyle?: ViewStyle;
}

export default function Input({ label, error, containerStyle, style, ...rest }: Props) {
  const c = Colors.light;
  return (
    <View style={[styles.container, containerStyle]}>
      {label && <Text style={[styles.label, { color: c.text }]}>{label}</Text>}
      <TextInput
        style={[
          styles.input,
          {
            backgroundColor: c.surface,
            borderColor: error ? c.danger : c.border,
            color: c.text,
          },
          style,
        ]}
        placeholderTextColor={c.textMuted}
        {...rest}
      />
      {error && <Text style={[styles.error, { color: c.danger }]}>{error}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginBottom: Spacing.md },
  label: { fontSize: FontSize.sm, fontWeight: '600', marginBottom: Spacing.xs },
  input: {
    borderWidth: 1.5,
    borderRadius: BorderRadius.md,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm + 2,
    fontSize: FontSize.md,
    minHeight: 44,
  },
  error: { fontSize: FontSize.xs, marginTop: Spacing.xs },
});
