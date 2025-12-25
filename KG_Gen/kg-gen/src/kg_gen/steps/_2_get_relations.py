from typing import List, Tuple
import dspy
from pydantic import BaseModel


def extraction_sig(
    Relation: BaseModel, is_conversation: bool, context: str = ""
) -> dspy.Signature:
    if not is_conversation:

        class ExtractTextRelations(dspy.Signature):
            __doc__ = f"""Kaynak metinden özne-yüklem-nesne üçlülerini çıkar.
      Özne ve nesne, varlıklar listesinden olmalıdır. Sağlanan varlıklar daha önce aynı kaynak metinden çıkarılmıştır.
      Bu bir çıkarım görevi içindir, lütfen kapsamlı, doğru ve referans metne sadık olun. {context}"""

            source_text: str = dspy.InputField()
            entities: list[str] = dspy.InputField()
            relations: list[Relation] = dspy.OutputField(
                desc="Özne-yüklem-nesne üçlülerinin listesi. Kapsamlı olun."
            )

        return ExtractTextRelations
    else:

        class ExtractConversationRelations(dspy.Signature):
            __doc__ = f"""Konuşmadan özne-yüklem-nesne üçlülerini çıkar, bunlar dahil:
      1. Tartışılan kavramlar arasındaki ilişkiler
      2. Konuşmacılar ve kavramlar arasındaki ilişkiler (örn. kullanıcı X hakkında soruyor)
      3. Konuşmacılar arasındaki ilişkiler (örn. asistan kullanıcıya yanıt veriyor)
      Özne ve nesne, varlıklar listesinden olmalıdır. Sağlanan varlıklar daha önce aynı kaynak metinden çıkarılmıştır.
      Bu bir çıkarım görevi içindir, lütfen kapsamlı, doğru ve referans metne sadık olun. {context}"""

            source_text: str = dspy.InputField()
            entities: list[str] = dspy.InputField()
            relations: list[Relation] = dspy.OutputField(
                desc="Özne ve nesnenin varlıklar listesindeki öğelerle tam eşleştiği özne-yüklem-nesne üçlülerinin listesi. Kapsamlı olun"
            )

        return ExtractConversationRelations


def fallback_extraction_sig(
    entities, is_conversation, context: str = ""
) -> dspy.Signature:
    """Bu yedek çıkarım, özne ve nesne dizelerini katı şekilde tiplemez."""

    entities_str = "\n- ".join(entities)

    class Relation(BaseModel):
        # TODO: burada literal kullanılmalı.
        __doc__ = f"""Bilgi grafiği özne-yüklem-nesne üçlüsü. Özne ve nesne varlıkları şunlardan biri olmalıdır: {entities_str}"""

        subject: str = dspy.InputField(desc="Özne varlığı", examples=["Kevin"])
        predicate: str = dspy.InputField(desc="Yüklem", examples=["kardeşidir"])
        object: str = dspy.InputField(desc="Nesne varlığı", examples=["Vicky"])

    return Relation, extraction_sig(Relation, is_conversation, context)


def get_relations(
    input_data: str,
    entities: list[str],
    is_conversation: bool = False,
    context: str = "",
) -> List[Tuple[str, str, str]]:
    class Relation(BaseModel):
        """Bilgi grafiği özne-yüklem-nesne üçlüsü."""

        subject: str = dspy.InputField(desc="Özne varlığı", examples=["Kevin"])
        predicate: str = dspy.InputField(desc="Yüklem", examples=["kardeşidir"])
        object: str = dspy.InputField(desc="Nesne varlığı", examples=["Vicky"])

    ExtractRelations = extraction_sig(Relation, is_conversation, context)

    try:
        extract = dspy.Predict(ExtractRelations)
        result = extract(source_text=input_data, entities=entities)
        return [(r.subject, r.predicate, r.object) for r in result.relations]

    except Exception as _:
        # print("get_relations: yedek çıkarım")
        Relation, ExtractRelations = fallback_extraction_sig(
            entities, is_conversation, context
        )
        extract = dspy.Predict(ExtractRelations)
        result = extract(source_text=input_data, entities=entities)

        class FixedRelations(dspy.Signature):
            """İlişkileri düzelt, böylece her ilişkinin öznesi ve nesnesi bir varlıkla tam eşleşsin. Yüklemi aynı tut. Her ilişkinin anlamı referans metne sadık kalmalı. Orijinal ilişkinin anlamını kaynak metne göre koruyamıyorsanız, onu döndürmeyin."""

            source_text: str = dspy.InputField()
            entities: list[str] = dspy.InputField()
            relations: list[Relation] = dspy.InputField()
            fixed_relations: list[Relation] = dspy.OutputField()

        fix = dspy.ChainOfThought(FixedRelations)

        fix_res = fix(
            source_text=input_data, entities=entities, relations=result.relations
        )

        good_relations = []
        for rel in fix_res.fixed_relations:
            if rel.subject in entities and rel.object in entities:
                good_relations.append(rel)
        return [(r.subject, r.predicate, r.object) for r in good_relations]