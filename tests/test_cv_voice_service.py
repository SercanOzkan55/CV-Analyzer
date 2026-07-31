from services.cv_voice_service import analyze_resume_voice, rewrite_resume_voice


def test_turkish_first_person_is_detected_and_rewritten_generically():
    source = (
        "Üretim hattında zaman etütleri yaparak iş istasyonlarındaki süre farklarını analiz ettim.\n"
        "• İyileştirme önerilerinde bulundum, yönetime sundum ve darboğazları belirledim.\n"
        "• Raporlama sürecini geliştirdim."
    )

    rewritten = rewrite_resume_voice(source, lang="tr")

    assert "analiz etti." in rewritten
    assert "bulundu, yönetime sundu ve darboğazları belirledi." in rewritten
    assert "geliştirdi." in rewritten
    assert analyze_resume_voice(source, lang="tr")["score"] < 70
    assert analyze_resume_voice(rewritten, lang="tr")["score"] == 100


def test_turkish_resume_nouns_are_not_mistaken_for_first_person_verbs():
    source = "EĞİTİM\nÜretim yönetimi, yazılım tasarımı ve takım çalışması"

    assert rewrite_resume_voice(source, lang="tr") == source
    assert analyze_resume_voice(source, lang="tr")["first_person_count"] == 0


def test_english_resume_voice_omits_subject_instead_of_using_third_person():
    source = "- I analyzed cycle times.\n- I have developed weekly reports.\n- My responsibilities included planning."
    rewritten = rewrite_resume_voice(source, lang="en")

    assert "- Analyzed cycle times." in rewritten
    assert "- Developed weekly reports." in rewritten
    assert "- Responsibilities included planning." in rewritten
    assert "He " not in rewritten
