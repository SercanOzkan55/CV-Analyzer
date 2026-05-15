// Theme colors for CV Analyzer mobile app
export const Colors = {
  light: {
    primary: '#6366f1',
    primaryDark: '#4f46e5',
    primaryLight: '#818cf8',
    accent: '#8b5cf6',
    background: '#f8fafc',
    surface: '#ffffff',
    surfaceAlt: '#f1f5f9',
    text: '#1e293b',
    textSecondary: '#64748b',
    textMuted: '#94a3b8',
    border: '#e2e8f0',
    success: '#22c55e',
    successBg: '#dcfce7',
    warning: '#eab308',
    warningBg: '#fef9c3',
    danger: '#ef4444',
    dangerBg: '#fee2e2',
    info: '#3b82f6',
    infoBg: '#dbeafe',
    card: '#ffffff',
    shadow: 'rgba(0,0,0,0.08)',
    tabBar: '#ffffff',
    tabBarBorder: '#e2e8f0',
    scoreHigh: '#22c55e',
    scoreMedium: '#eab308',
    scoreLow: '#ef4444',
  },
  dark: {
    primary: '#818cf8',
    primaryDark: '#6366f1',
    primaryLight: '#a5b4fc',
    accent: '#a78bfa',
    background: '#0f172a',
    surface: '#1e293b',
    surfaceAlt: '#334155',
    text: '#f1f5f9',
    textSecondary: '#94a3b8',
    textMuted: '#64748b',
    border: '#334155',
    success: '#4ade80',
    successBg: '#166534',
    warning: '#facc15',
    warningBg: '#854d0e',
    danger: '#f87171',
    dangerBg: '#991b1b',
    info: '#60a5fa',
    infoBg: '#1e40af',
    card: '#1e293b',
    shadow: 'rgba(0,0,0,0.3)',
    tabBar: '#1e293b',
    tabBarBorder: '#334155',
    scoreHigh: '#4ade80',
    scoreMedium: '#facc15',
    scoreLow: '#f87171',
  },
};

export function getScoreColor(score: number, dark = false) {
  const c = dark ? Colors.dark : Colors.light;
  if (score >= 75) return c.scoreHigh;
  if (score >= 50) return c.scoreMedium;
  return c.scoreLow;
}

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
  xxxl: 32,
};

export const FontSize = {
  xs: 11,
  sm: 13,
  md: 15,
  lg: 17,
  xl: 20,
  xxl: 24,
  xxxl: 30,
  title: 28,
};

export const BorderRadius = {
  sm: 6,
  md: 10,
  lg: 14,
  xl: 18,
  full: 999,
};
