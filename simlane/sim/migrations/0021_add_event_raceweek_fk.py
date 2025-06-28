from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('sim', '0020_enhance_car_class_restrictions_v2'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='race_week',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name='events',
                to='sim.raceweek',
            ),
        ),
    ] 