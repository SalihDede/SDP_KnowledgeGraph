##############################################################################
## Girdi Formatı Örneği:
##   {
##      "baş": "Lamine Yamal",
##       "baş_tipi": "Kişi",
##       "ilişki": "Kazandı",
##       "uç": "La Liga 2022-23 Sezonu",
##       "uç_tipi": "Turnuva"
##   },
## Uç ya da Baş isimleri incelenerek aynı olan varlıkların tip bilgilerini toplar
## Çıktı formatından entitiy (uç ya da baş) ve entity_type (tip bilgisi) vardır
## Çıktı json adı : entity_types_analysis.json
##############################################################################


##############################################################################
## Girdi Formatı Örneği:
##   {
##      "baş": "Lamine Yamal",
##       "baş_tipi": "Kişi",
##       "ilişki": "Kazandı",
##       "uç": "La Liga 2022-23 Sezonu",
##       "uç_tipi": "Turnuva"
##   },
## Uç ve Baş isimleri aynı olan KG 3'lülerini realtion bazlı birleştirir
## Çıktı formatından uç baş ve relation vardır
## Çıktı json adı : merged_all_relations.json
##############################################################################


##############################################################################
## Girdi Formatı Örneği:
##   {
##      "baş": "Lamine Yamal",
##       "baş_tipi": "Kişi",
##       "ilişki": "Kazandı",
##       "uç": "La Liga 2022-23 Sezonu",
##       "uç_tipi": "Turnuva"
##   },
## Uç ve Baş isimleri aynı olan KG 3'lülerini realtion,baş_tipi ve uç_tipi bazlı birleştirir
## Çıktı formatından uç, uç tipi, baş, baş tipi ve ralation vardır
## Çıktı json adı : merged_all_relations_with_types.json
##############################################################################

LLMWithCasualDataExample.json --> Dil modeline birkaç örnek metin üzerinden KG 3'lüleri oluşturulmuş ve sistem prompt ile bu çıkrımları benimseyerek çalışması istenmiştir.

LLMwithWikiDataExample.json --> Dil modeline Wikidatadan gelen örnek 3'lüler verilmiş ve sistem prompt ile bu çıkrımları benimseyerek çalışması istenmiştir.

WikiDataTriples.json --> Wikidata tarafından gelen KG 3'lüleri.