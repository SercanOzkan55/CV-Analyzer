import { useState, useCallback, useRef, useEffect } from 'react';
import { translatePost } from './translateService';

interface TranslatedFields {
  title: string;
  summary: string;
  content: string;
}

interface UseTranslationReturn {
  isTranslated: boolean;
  isLoading: boolean;
  error: string | null;
  translated: TranslatedFields | null;
  targetLang: string;
  toggle: (post: { title: string; summary: string; content: string }) => void;
}

function isUnchangedTranslation(
  original: { title: string; summary: string; content: string },
  translated: { title: string; summary: string; content: string }
): boolean {
  const normalize = (value: string) => value.trim().toLowerCase();
  return (
    normalize(original.title) === normalize(translated.title) &&
    normalize(original.summary) === normalize(translated.summary) &&
    normalize(original.content) === normalize(translated.content)
  );
}

/**
 * Hook that manages translation state for a blog post.
 * Automatically resets when currentLang changes.
 * @param currentLang - current site language code
 * @param errorMessage - translated error message to show on failure
 */
export function useTranslation(currentLang: string, errorMessage?: string): UseTranslationReturn {
  const [isTranslated, setIsTranslated] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [translated, setTranslated] = useState<TranslatedFields | null>(null);
  const translatedLangRef = useRef<string | null>(null);
  const targetLang = currentLang === 'tr' ? 'en' : 'tr';

  // When site language changes, reset translation state
  useEffect(() => {
    if (translatedLangRef.current && translatedLangRef.current !== currentLang) {
      setTranslated(null);
      setIsTranslated(false);
      setError(null);
      translatedLangRef.current = null;
    }
  }, [currentLang]);

  const toggle = useCallback(
    async (post: { title: string; summary: string; content: string }) => {
      // If already showing translation for this language, revert to original
      if (isTranslated) {
        setIsTranslated(false);
        return;
      }

      // If we already have a cached translation for this language, show it
      if (translated && translatedLangRef.current === targetLang) {
        setIsTranslated(true);
        return;
      }

      setIsLoading(true);
      setError(null);
      try {
        let result = await translatePost(post, targetLang);
        let effectiveLang = targetLang;

        if (isUnchangedTranslation(post, result)) {
          const fallbackLang = targetLang === 'tr' ? 'en' : 'tr';
          result = await translatePost(post, fallbackLang);
          effectiveLang = fallbackLang;
        }

        setTranslated(result);
        setIsTranslated(true);
        translatedLangRef.current = effectiveLang;
      } catch {
        setError(errorMessage || 'Translation failed. Please try again.');
      } finally {
        setIsLoading(false);
      }
    },
    [isTranslated, translated, targetLang]
  );

  return { isTranslated, isLoading, error, translated, targetLang, toggle };
}
