from django.db import migrations, models


def move_ner_sections(apps, schema_editor):
    Ner = apps.get_model("core", "Ner")
    for ner in Ner.objects.select_related("chunk").iterator():
        meta = ner.meta if isinstance(ner.meta, dict) else {}
        section = ner.chunk.section if ner.chunk_id else meta.get("section", "")
        if section or "section" in meta:
            ner.section = section
            ner.meta = {key: value for key, value in meta.items() if key != "section"}
            ner.save(update_fields=["section", "meta"])


class Migration(migrations.Migration):
    dependencies = [("core", "0010_judgement")]

    operations = [
        migrations.AddField(
            model_name="ner",
            name="section",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.RunPython(move_ner_sections, migrations.RunPython.noop),
    ]
