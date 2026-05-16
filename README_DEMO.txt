CV ANALYZER - YEREL KURULUM TEST REHBERI (DEMO)

Bu uygulama, verilerin tamamen sirket bunyesinde kaldigi "On-Premise" kurulumu simule eder.

TEST ICIN ADIMLAR:
1. 'start_private_demo.bat' dosyasina cift tiklayin.
2. Siyah ekran acik kaldigi surece uygulama calisir.
3. Tarayicinizdan http://localhost:8001 adresine gidin.

GIZLILIK KONTROLU NASIL YAPILIR?
- Bir CV yukledikten sonra proje klasorundeki 'storage_data' klasorune bakin.
- Yuklediginiz dosyanin buraya kaydedildigini goreceksiniz.
- AWS S3 veya herhangi bir bulut servisi kullanilmamaktadir.

NOT: Bu demo modunda yapay zeka yanitlari simule edilmektedir (Mock Mode). 
Gercek yerel yapay zeka (Ollama) baglantisi kurumsal kurulumda yapilmaktadir.
