const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);

// Supabase auth-js uses .cjs files internally that Metro can't resolve by default
config.resolver.sourceExts.push('cjs');

module.exports = config;
