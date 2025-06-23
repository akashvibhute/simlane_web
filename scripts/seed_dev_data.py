#!/usr/bin/env python
"""
Development Data Seeding Script
===============================

This script seeds the database with development/testing data.
DO NOT INCLUDE THIS FILE IN PRODUCTION BUILDS.

Usage:
    python scripts/seed_dev_data.py [--clear]

Requirements:
    - Django environment must be set up
    - Database must be migrated
"""

import os
import sys

import django

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

# Now import Django models and management
import argparse

from django.core.management import call_command


def main():
    parser = argparse.ArgumentParser(description="Seed development data")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing data before seeding",
    )
    args = parser.parse_args()

    print("🌱 Starting development data seeding...")
    print("=" * 50)

    if args.clear:
        print("⚠️  Clearing existing data...")
        call_command("seed_dev_data", "--clear")
    else:
        call_command("seed_dev_data")

    print("=" * 50)
    print("✅ Development data seeding complete!")
    print("\nYou can now:")
    print("- Login with any of the test users (password: password123)")
    print("- Admin user: admin_user / password123")
    print("- Test the clubs, teams, and event functionality")


if __name__ == "__main__":
    main()
