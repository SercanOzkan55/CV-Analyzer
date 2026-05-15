import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Svg, { Circle } from 'react-native-svg';
import { getScoreColor } from '../theme';

interface Props {
  score: number;
  size?: number;
  strokeWidth?: number;
  dark?: boolean;
  label?: string;
}

export default function ScoreCircle({ score, size = 80, strokeWidth = 6, dark = false, label }: Props) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = Math.min(Math.max(score, 0), 100);
  const strokeDashoffset = circumference - (progress / 100) * circumference;
  const color = getScoreColor(score, dark);

  return (
    <View style={[styles.container, { width: size, height: size }]}>
      <Svg width={size} height={size}>
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={dark ? '#334155' : '#e2e8f0'}
          strokeWidth={strokeWidth}
          fill="none"
        />
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={color}
          strokeWidth={strokeWidth}
          fill="none"
          strokeDasharray={`${circumference}`}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          rotation="-90"
          origin={`${size / 2}, ${size / 2}`}
        />
      </Svg>
      <View style={styles.labelWrap}>
        <Text style={[styles.score, { color, fontSize: size * 0.28 }]}>
          {Math.round(score)}%
        </Text>
        {label && (
          <Text style={[styles.label, { color: dark ? '#94a3b8' : '#64748b', fontSize: size * 0.12 }]}>
            {label}
          </Text>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { alignItems: 'center', justifyContent: 'center' },
  labelWrap: { position: 'absolute', alignItems: 'center' },
  score: { fontWeight: '700', fontFamily: 'monospace' },
  label: { marginTop: 1 },
});
