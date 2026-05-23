import pytest
from agents.extract_agent import extract_structured, _is_fullname, _is_colon_label
from services.layout_analyzer import analyze_layout

def test_is_fullname_unicode():
    # Valid Name Title Case (English, Turkish, German, Spanish, French)
    assert _is_fullname("Sercan Özkan") is True
    assert _is_fullname("Jörg Müller") is True
    assert _is_fullname("José María") is True
    assert _is_fullname("Álvaro Gómez") is True
    assert _is_fullname("Émile Zola") is True
    
    # Valid Name All Caps
    assert _is_fullname("SERCAN ÖZKAN") is True
    assert _is_fullname("JÖRG MÜLLER") is True
    assert _is_fullname("JOSÉ MARÍA") is True
    
    # Invalid Names
    assert _is_fullname("Sercan") is False  # Too short (1 word)
    assert _is_fullname("Sercan Özkan Deneme Sınavı Test") is False  # Too long (5 words)
    assert _is_fullname("Sercan123 Özkan") is False  # Contains digits
    assert _is_fullname("Sercan @ Özkan") is False  # Contains special character


def test_is_colon_label_unicode():
    assert _is_colon_label("Yabancı Dil: İngilizce") is True
    assert _is_colon_label("Über mich: Entwickler") is True
    assert _is_colon_label("Eğitim: Üniversite") is True
    
    # Invalid cases
    assert _is_colon_label("C++: Senior") is False  # Left side has non-alpha
    assert _is_colon_label("Eğitim:") is False  # Right side is empty


def test_extract_structured_german_cv():
    text = """
Jörg Müller
Softwareentwickler

PERSÖNLICHE ZUSAMMENFASSUNG
Erfahrener Fullstack-Entwickler mit Schwerpunkt auf Python.

KONTAKT
E-Mail: joerg.mueller@example.de
Telefon: +49 170 1234567
Adresse: Berlin, Deutschland

BERUFLICHER WERDEGANG
Developer GmbH
Software Engineer | Jan 2020 - Heute
- Entwicklung von Microservices mit FastAPI

AUSBILDUNG
Universität Berlin
Master of Science in Informatik | 2017 - 2019
"""
    result = extract_structured(text)
    assert result["full_name"] == "Jörg Müller"
    assert result["title"] == "Softwareentwickler"
    assert result["email"] == "joerg.mueller@example.de"
    assert result["phone"] == "+49 170 1234567"
    assert result["location"] == "Berlin, Deutschland"
    assert len(result["experiences"]) == 1
    assert "Developer GmbH" in result["experiences"][0]["title"]
    assert len(result["education"]) == 1
    assert "Universität Berlin" in result["education"][0]["school"]
