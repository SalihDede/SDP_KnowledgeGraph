from typing import List
import dspy


class TextEntities(dspy.Signature):
    """Kaynak metinden anahtar varlıkları çıkar. Çıkarılan varlıklar özne veya nesnelerdir.
    Bu bir çıkarım görevi içindir, lütfen KAPSAMLI ve referans metne sadık olun."""

    source_text: str = dspy.InputField()
    entities: list[str] = dspy.OutputField(desc="Anahtar varlıkların KAPSAMLI listesi")


class ConversationEntities(dspy.Signature):
    """Konuşmadan anahtar varlıkları çıkar. Çıkarılan varlıklar özne veya nesnelerdir.
    Hem açık varlıkları hem de konuşmadaki katılımcıları dikkate alın.
    Bu bir çıkarım görevi içindir, lütfen KAPSAMLI ve doğru olun."""

    source_text: str = dspy.InputField()
    entities: list[str] = dspy.OutputField(desc="Anahtar varlıkların KAPSAMLI listesi")


def get_entities(input_data: str, is_conversation: bool = False) -> List[str]:
    extract = (
        dspy.Predict(ConversationEntities)
        if is_conversation
        else dspy.Predict(TextEntities)
    )
    result = extract(source_text=input_data)
    return result.entities