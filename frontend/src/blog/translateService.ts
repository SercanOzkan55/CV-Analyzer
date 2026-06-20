const CACHE_KEY = 'cv_blog_translations';

interface TranslationCache {
  [key: string]: string;
}

function loadCache(): TranslationCache {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveCache(cache: TranslationCache) {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(cache));
  } catch { /* quota exceeded — ignore */ }
}

function cacheKey(text: string, targetLang: string): string {
  // Use first 80 chars + length as key to keep cache manageable
  const snippet = text.slice(0, 80).trim();
  return `${targetLang}::${snippet}::${text.length}`;
}

/**
 * Translate a text chunk using Google Translate (gtx client).
 * Auto-detects source language. No API key needed.
 */
async function callTranslateAPI(text: string, targetLang: string): Promise<string> {
  const MAX_CHUNK = 4500; // Google gtx supports longer chunks
  if (text.length <= MAX_CHUNK) {
    return translateChunkGoogle(text, targetLang);
  }

  const parts = splitText(text, MAX_CHUNK);
  const translated = await Promise.all(parts.map(p => translateChunkGoogle(p, targetLang)));
  return translated.join('');
}

function splitText(text: string, maxLen: number): string[] {
  const parts: string[] = [];
  let remaining = text;
  while (remaining.length > 0) {
    if (remaining.length <= maxLen) {
      parts.push(remaining);
      break;
    }
    let splitIdx = -1;
    for (let i = maxLen; i >= maxLen * 0.5; i--) {
      if (remaining[i] === '\n' || remaining[i] === '.' || remaining[i] === '。') {
        splitIdx = i + 1;
        break;
      }
    }
    if (splitIdx < 0) splitIdx = maxLen;
    parts.push(remaining.slice(0, splitIdx));
    remaining = remaining.slice(splitIdx);
  }
  return parts;
}

async function translateChunkGoogle(text: string, targetLang: string): Promise<string> {
  if (!text.trim()) return text;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);

  try {
    const url = `https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=${encodeURIComponent(targetLang)}&dt=t&q=${encodeURIComponent(text)}`;
    const res = await fetch(url, { signal: controller.signal });
    clearTimeout(timeout);

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (Array.isArray(data) && Array.isArray(data[0])) {
      return data[0].map((seg: any) => seg[0]).join('');
    }
    throw new Error('Unexpected response format');
  } catch (err) {
    clearTimeout(timeout);
    throw err;
  }
}

/**
 * Translate a text string to the target language, with caching.
 */
export async function translateText(text: string, targetLang: string): Promise<string> {
  if (!text.trim()) return text;

  const hasConsent = typeof window !== 'undefined' && localStorage.getItem('cookie_consent') === 'accepted';
  if (!hasConsent) {
    return text;
  }

  const key = cacheKey(text, targetLang);
  const cache = loadCache();
  if (cache[key]) return cache[key];

  const translated = await callTranslateAPI(text, targetLang);
  cache[key] = translated;
  saveCache(cache);
  return translated;
}

/**
 * Translate title, summary, and content of a blog post.
 */
export async function translatePost(
  post: { title: string; summary: string; content: string },
  targetLang: string
): Promise<{ title: string; summary: string; content: string }> {
  const [title, summary, content] = await Promise.all([
    translateText(post.title, targetLang),
    translateText(post.summary, targetLang),
    translateText(post.content, targetLang),
  ]);
  return { title, summary, content };
}

/** Language display names */
export const LANG_LABELS: Record<string, string> = {
  en: 'English',
  tr: 'Türkçe',
  fr: 'Français',
  ar: 'العربية',
  de: 'Deutsch',
  es: 'Español',
};
