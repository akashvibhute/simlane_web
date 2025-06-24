"""
Data migration to create base seed data including simulators and iRacing content.
"""

from django.core.management import call_command
from django.db import migrations


def create_base_seed_data(apps, schema_editor):
    """Create base seed data via management command"""
    try:
        # Run the base seed data command
        # Skip iRacing API if it fails, but still create basic structure
        call_command('create_base_seed_data')
    except Exception:
        # If API fails, at least create the basic simulators
        call_command('create_base_seed_data', '--skip-iracing')


def reverse_base_seed_data(apps, schema_editor):
    """Reverse the seed data creation (no-op for safety)"""
    # We don't delete seed data on reverse for safety
    # Users can manually clean if needed
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0001_initial'),
        ('sim', '0009_remove_simprofile_sim_simprof_user_id_c94dd1_idx_and_more'),
    ]

    operations = [
        migrations.RunPython(
            create_base_seed_data,
            reverse_base_seed_data,
        ),
    ] 