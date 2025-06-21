"""
Django management command to clean up expired club invitations.
This command should be run periodically via cron job.
"""

import logging
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.conf import settings

from simlane.teams.models import ClubInvitation


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clean up expired club invitations'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days after expiry to keep invitations (default: 7)',
        )
        parser.add_argument(
            '--club',
            type=str,
            help='Limit cleanup to specific club UUID',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        days_buffer = options['days']
        club_id = options['club']
        verbose = options['verbose']

        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=days_buffer)
        
        if verbose:
            self.stdout.write(
                self.style.SUCCESS(f'Looking for invitations expired before: {cutoff_date}')
            )

        # Build queryset
        queryset = ClubInvitation.objects.filter(
            expires_at__lt=cutoff_date,
            status__in=['PENDING', 'EXPIRED']
        )

        if club_id:
            try:
                queryset = queryset.filter(club__id=club_id)
                if verbose:
                    self.stdout.write(f'Filtering by club: {club_id}')
            except Exception as e:
                raise CommandError(f'Invalid club ID: {e}')

        # Get expired invitations
        expired_invitations = list(queryset.select_related('club', 'inviter'))
        
        if not expired_invitations:
            self.stdout.write(
                self.style.SUCCESS('No expired invitations found.')
            )
            return

        # Display what will be deleted
        self.stdout.write(
            self.style.WARNING(f'Found {len(expired_invitations)} expired invitations:')
        )
        
        for invitation in expired_invitations:
            self.stdout.write(
                f'  - {invitation.invitee_email} to {invitation.club.name} '
                f'(expired: {invitation.expires_at}, status: {invitation.status})'
            )

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'DRY RUN: Would delete {len(expired_invitations)} invitations'
                )
            )
            return

        # Confirm deletion
        if not options.get('force', False):
            confirm = input(f'Delete {len(expired_invitations)} expired invitations? [y/N]: ')
            if confirm.lower() not in ['y', 'yes']:
                self.stdout.write('Cancelled.')
                return

        # Delete expired invitations
        try:
            with transaction.atomic():
                deleted_count = 0
                errors = []

                for invitation in expired_invitations:
                    try:
                        invitation_info = f'{invitation.invitee_email} to {invitation.club.name}'
                        invitation.delete()
                        deleted_count += 1
                        
                        if verbose:
                            self.stdout.write(f'Deleted: {invitation_info}')
                            
                        logger.info(f'Deleted expired invitation: {invitation_info}')
                        
                    except Exception as e:
                        error_msg = f'Failed to delete invitation {invitation.pk}: {e}'
                        errors.append(error_msg)
                        logger.error(error_msg)

                if errors:
                    self.stdout.write(
                        self.style.ERROR(f'Encountered {len(errors)} errors:')
                    )
                    for error in errors:
                        self.stdout.write(f'  - {error}')

                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully deleted {deleted_count} expired invitations'
                    )
                )
                
                logger.info(f'Cleanup completed: {deleted_count} invitations deleted')

        except Exception as e:
            error_msg = f'Failed to clean up invitations: {e}'
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg)
            raise CommandError(error_msg)

    def _get_statistics(self):
        """Get invitation statistics for reporting."""
        stats = {
            'total_invitations': ClubInvitation.objects.count(),
            'pending_invitations': ClubInvitation.objects.filter(status='PENDING').count(),
            'expired_invitations': ClubInvitation.objects.filter(status='EXPIRED').count(),
            'accepted_invitations': ClubInvitation.objects.filter(status='ACCEPTED').count(),
            'declined_invitations': ClubInvitation.objects.filter(status='DECLINED').count(),
        }
        
        # Add expired but not yet cleaned up
        cutoff_date = timezone.now()
        stats['expired_pending'] = ClubInvitation.objects.filter(
            expires_at__lt=cutoff_date,
            status='PENDING'
        ).count()
        
        return stats 