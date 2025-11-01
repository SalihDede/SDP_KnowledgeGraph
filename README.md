# README  

## Proje Amacı  

Bu proje, ileri aşamalarda kullanılacak **bilgi grafiği oluşturma süreci** için temel **veri toplama fazını** kapsamaktadır.  
Birinci fazın hedefi, hem **Wikipedia** hem de **Wikidata** kaynaklarından anlamlı veri çekip, bu verilerden **bilgi grafiği üçlüleri (head–relation–tail)** elde etmektir.  

---

## 1. Faz: Veri Toplama ve Bilgi Grafiği Temeli  

### 1.1 — `DataCollection`  
**Hedef:** Wikipedia üzerinden veri çekimi  

**Amaç:**  
- Web scraping yöntemiyle Wikipedia metinleri toplanır.  
- Metin içindeki **URL’ye sahip kelimeler**, **olası entity** olarak işaretlenir.  
- Bu kelimeler ve bağlı oldukları URL’ler birlikte kaydedilir.  

**Genelleme Mantığı:**  
Aynı URL’ye yönlenen farklı kelimeler tespit edilirse, bu kelimelerin **yakın anlamlı** olduğu varsayılır.  

**Ek Süreç:**  
- Cümlelerdeki entity geçiş sıklıkları (frekansları) hesaplanır.  
- Bu frekans verileri, **LLM destekli bilgi grafiği üçlüleri** üretmek için temel oluşturur.  

