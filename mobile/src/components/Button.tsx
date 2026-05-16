import React from 'react';
import {
  TouchableOpacity,
  Text,
  StyleSheet,
  ActivityIndicator,
  ViewStyle,
  TextStyle,
} from 'react-native';
import { Colors, BorderRadius, Spacing, FontSize } from '../theme';

interface Props {
  title: string;
  onPress: () => void;
  variant?: 'primary' | 'outline' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  disabled?: boolean;
  icon?: React.ReactNode;
  style?: ViewStyle;
  textStyle?: TextStyle;
}

export default function Button({
  title, onPress, variant = 'primary', size = 'md',
  loading = false, disabled = false, icon, style, textStyle,
}: Props) {
  const c = Colors.light;
  const isDisabled = disabled || loading;

  const baseStyle: ViewStyle = {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
    borderRadius: BorderRadius.md,
    opacity: isDisabled ? 0.5 : 1,
    ...sizeStyles[size],
    ...variantStyles(c)[variant],
  };

  const textBaseStyle: TextStyle = {
    fontWeight: '600',
    ...textSizes[size],
    ...variantTextStyles(c)[variant],
  };

  return (
    <TouchableOpacity
      style={[baseStyle, style]}
      onPress={onPress}
      disabled={isDisabled}
      activeOpacity={0.7}
    >
      {loading ? (
        <ActivityIndicator size="small" color={variantTextStyles(c)[variant].color} />
      ) : icon ? icon : null}
      <Text style={[textBaseStyle, textStyle]}>{title}</Text>
    </TouchableOpacity>
  );
}

const sizeStyles: Record<string, ViewStyle> = {
  sm: { paddingHorizontal: Spacing.md, paddingVertical: Spacing.xs + 2, minHeight: 32 },
  md: { paddingHorizontal: Spacing.lg, paddingVertical: Spacing.sm + 2, minHeight: 42 },
  lg: { paddingHorizontal: Spacing.xl, paddingVertical: Spacing.md, minHeight: 50 },
};

const textSizes: Record<string, TextStyle> = {
  sm: { fontSize: FontSize.sm },
  md: { fontSize: FontSize.md },
  lg: { fontSize: FontSize.lg },
};

const variantStyles = (c: typeof Colors.light): Record<string, ViewStyle> => ({
  primary: { backgroundColor: c.primary },
  outline: { backgroundColor: 'transparent', borderWidth: 1.5, borderColor: c.border },
  ghost: { backgroundColor: 'transparent' },
  danger: { backgroundColor: c.danger },
});

const variantTextStyles = (c: typeof Colors.light): Record<string, TextStyle> => ({
  primary: { color: '#ffffff' },
  outline: { color: c.text },
  ghost: { color: c.primary },
  danger: { color: '#ffffff' },
});
