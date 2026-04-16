import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useLanguage } from '../i18n/LanguageContext';

export default function FeedbackButton() {
  const navigate = useNavigate();
  const { t } = useLanguage();
  return (
    <button
      className="feedback-floating-btn"
      title={t('feedback.button_title') || 'Şikayet / Destek'}
      onClick={() => navigate('/feedback')}
    >
      💬 {t('feedback.button_text') || 'Şikayet / Destek'}
    </button>
  );
}
