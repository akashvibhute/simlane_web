"""
Django Admin actions for triggering iRacing sync jobs.

This module provides admin actions that can be triggered from the Django admin
interface to manually initiate various sync tasks.
"""

import logging
from typing import Any, Dict

from django.contrib import admin, messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

from simlane.iracing.tasks import (
    queue_all_past_seasons_sync_task,
    sync_car_classes_task,
    sync_current_seasons_task,
    sync_season_task,
    sync_series_task,
)
from simlane.sim.models import Series, Season

logger = logging.getLogger(__name__)


class IRacingSyncAdmin(admin.ModelAdmin):
    """
    Custom admin interface for triggering iRacing sync jobs.
    
    This provides a UI for manually triggering various sync tasks
    from the Django admin interface.
    """
    
    def get_urls(self):
        """Add custom URLs for sync actions."""
        urls = super().get_urls() if hasattr(super(), 'get_urls') else []
        custom_urls = [
            path('sync-overview/', self.sync_overview_view, name='iracing_sync_overview'),
            path('sync-series/', self.sync_series_view, name='iracing_sync_series'),
            path('sync-current-seasons/', self.sync_current_seasons_view, name='iracing_sync_current_seasons'),
            path('sync-past-seasons/', self.sync_past_seasons_view, name='iracing_sync_past_seasons'),
            path('sync-car-classes/', self.sync_car_classes_view, name='iracing_sync_car_classes'),
            path('sync-season/<int:season_id>/', self.sync_single_season_view, name='iracing_sync_single_season'),
        ]
        return custom_urls + urls

    def sync_overview_view(self, request: HttpRequest) -> HttpResponse:
        """Overview page for all iRacing sync operations."""
        context = {
            'title': 'iRacing Sync Dashboard',
            'description': 'Manage iRacing data synchronization tasks',
            'sync_actions': [
                {
                    'name': 'Sync Series',
                    'description': 'Update all iRacing series data',
                    'url': reverse('admin:iracing_sync_series'),
                },
                {
                    'name': 'Sync Current Seasons',
                    'description': 'Update current and future seasons',
                    'url': reverse('admin:iracing_sync_current_seasons'),
                },
                {
                    'name': 'Sync Past Seasons',
                    'description': 'Queue sync for all past seasons',
                    'url': reverse('admin:iracing_sync_past_seasons'),
                },
                {
                    'name': 'Sync Car Classes',
                    'description': 'Update car classes and assignments',
                    'url': reverse('admin:iracing_sync_car_classes'),
                },
            ],
        }
        
        return render(request, 'admin/iracing/sync_overview.html', context)
    
    def sync_series_view(self, request: HttpRequest) -> HttpResponse:
        """View to trigger series sync."""
        if request.method == 'POST':
            refresh = request.POST.get('refresh', False) == 'on'
            
            try:
                # Trigger the task
                task = sync_series_task.delay(refresh=refresh)
                
                messages.success(
                    request,
                    f"Series sync task queued successfully. Task ID: {task.id}"
                )
                
                logger.info(f"Series sync triggered by {request.user.username}. Task ID: {task.id}")
                
            except Exception as e:
                logger.exception("Error triggering series sync")
                messages.error(request, f"Error triggering series sync: {e}")
            
            return redirect('admin:index')
        
        context = {
            'title': 'Sync iRacing Series',
            'action_name': 'Sync Series',
            'description': 'Fetch and update all iRacing series data (names, licenses, etc.)',
        }
        
        return render(request, 'admin/iracing/sync_form.html', context)
    
    def sync_current_seasons_view(self, request: HttpRequest) -> HttpResponse:
        """View to trigger current seasons sync."""
        if request.method == 'POST':
            refresh = request.POST.get('refresh', False) == 'on'
            
            try:
                # Trigger the task
                task = sync_current_seasons_task.delay(refresh=refresh)
                
                messages.success(
                    request,
                    f"Current seasons sync task queued successfully. Task ID: {task.id}"
                )
                
                logger.info(f"Current seasons sync triggered by {request.user.username}. Task ID: {task.id}")
                
            except Exception as e:
                logger.exception("Error triggering current seasons sync")
                messages.error(request, f"Error triggering current seasons sync: {e}")
            
            return redirect('admin:index')
        
        context = {
            'title': 'Sync Current Seasons',
            'action_name': 'Sync Current Seasons',
            'description': 'Fetch and update current and future seasons for all series, including schedules and events.',
        }
        
        return render(request, 'admin/iracing/sync_form.html', context)
    
    def sync_past_seasons_view(self, request: HttpRequest) -> HttpResponse:
        """View to trigger past seasons sync."""
        if request.method == 'POST':
            refresh = request.POST.get('refresh', False) == 'on'
            
            try:
                # Trigger the task
                task = queue_all_past_seasons_sync_task.delay(refresh=refresh)
                
                messages.success(
                    request,
                    f"Past seasons sync task queued successfully. Task ID: {task.id}. "
                    "This will queue individual season sync tasks for all series."
                )
                
                logger.info(f"Past seasons sync triggered by {request.user.username}. Task ID: {task.id}")
                
            except Exception as e:
                logger.exception("Error triggering past seasons sync")
                messages.error(request, f"Error triggering past seasons sync: {e}")
            
            return redirect('admin:index')
        
        context = {
            'title': 'Sync Past Seasons',
            'action_name': 'Sync Past Seasons',
            'description': 'Queue sync tasks for all past seasons. This may take a while as it processes many seasons.',
            'warning': 'This action will queue many individual season sync tasks. Use with caution.',
            'opts': self.model._meta,
        }
        
        return render(request, 'admin/iracing/sync_form.html', context)
    
    def sync_car_classes_view(self, request: HttpRequest) -> HttpResponse:
        """View to trigger car classes sync."""
        if request.method == 'POST':
            refresh = request.POST.get('refresh', False) == 'on'
            
            try:
                # Trigger the task
                task = sync_car_classes_task.delay(refresh=refresh)
                
                messages.success(
                    request,
                    f"Car classes sync task queued successfully. Task ID: {task.id}"
                )
                
                logger.info(f"Car classes sync triggered by {request.user.username}. Task ID: {task.id}")
                
            except Exception as e:
                logger.exception("Error triggering car classes sync")
                messages.error(request, f"Error triggering car classes sync: {e}")
            
            return redirect('admin:index')
        
        context = {
            'title': 'Sync Car Classes',
            'action_name': 'Sync Car Classes',
            'description': 'Fetch and update all iRacing car classes and their car assignments.',
            'opts': self.model._meta,
        }
        
        return render(request, 'admin/iracing/sync_form.html', context)
    
    def sync_single_season_view(self, request: HttpRequest, season_id: int) -> HttpResponse:
        """View to trigger sync for a single season."""
        if request.method == 'POST':
            refresh = request.POST.get('refresh', False) == 'on'
            
            try:
                # Trigger the task
                task = sync_season_task.delay(season_id, refresh=refresh)
                
                messages.success(
                    request,
                    f"Season {season_id} sync task queued successfully. Task ID: {task.id}"
                )
                
                logger.info(f"Season {season_id} sync triggered by {request.user.username}. Task ID: {task.id}")
                
            except Exception as e:
                logger.exception(f"Error triggering season {season_id} sync")
                messages.error(request, f"Error triggering season {season_id} sync: {e}")
            
            return redirect('admin:sim_season_changelist')
        
        context = {
            'title': f'Sync Season {season_id}',
            'action_name': f'Sync Season {season_id}',
            'description': f'Fetch and update season {season_id} schedule and events.',
            'opts': Season._meta,
        }
        
        return render(request, 'admin/iracing/sync_form.html', context)


def add_sync_actions_to_admin():
    """
    Add sync actions to relevant admin classes.
    
    This function registers custom actions with existing admin classes
    to provide sync functionality from list views.
    """
    
    @admin.action(description="Sync selected seasons")
    def sync_selected_seasons(modeladmin, request, queryset):
        """Admin action to sync selected seasons."""
        tasks_queued = 0
        errors = []
        
        for season in queryset:
            if season.external_season_id:
                try:
                    task = sync_season_task.delay(season.external_season_id)
                    tasks_queued += 1
                    logger.info(f"Queued sync for season {season.external_season_id}. Task ID: {task.id}")
                except Exception as e:
                    error_msg = f"Error queuing sync for season {season.external_season_id}: {e}"
                    logger.exception(error_msg)
                    errors.append(error_msg)
        
        if tasks_queued:
            messages.success(
                request,
                f"Queued sync tasks for {tasks_queued} seasons."
            )
        
        if errors:
            for error in errors[:5]:  # Show max 5 errors
                messages.error(request, error)
            if len(errors) > 5:
                messages.error(request, f"... and {len(errors) - 5} more errors")
    
    @admin.action(description="Queue past seasons sync for selected series")
    def sync_past_seasons_for_series(modeladmin, request, queryset):
        """Admin action to sync past seasons for selected series."""
        from celery import current_app
        
        tasks_queued = 0
        errors = []
        
        for series in queryset:
            if series.external_series_id:
                try:
                    current_app.send_task(
                        'simlane.iracing.tasks.sync_past_seasons_for_series_task',
                        args=[series.external_series_id],
                        kwargs={'refresh': False}
                    )
                    tasks_queued += 1
                    logger.info(f"Queued past seasons sync for series {series.external_series_id}")
                except Exception as e:
                    error_msg = f"Error queuing past seasons sync for series {series.external_series_id}: {e}"
                    logger.exception(error_msg)
                    errors.append(error_msg)
        
        if tasks_queued:
            messages.success(
                request,
                f"Queued past seasons sync for {tasks_queued} series."
            )
        
        if errors:
            for error in errors[:5]:  # Show max 5 errors
                messages.error(request, error)
            if len(errors) > 5:
                messages.error(request, f"... and {len(errors) - 5} more errors")
    
    # Add actions to admin classes
    try:
        from simlane.sim.admin import SeasonAdmin, SeriesAdmin
        
        if hasattr(SeasonAdmin, 'actions'):
            SeasonAdmin.actions = list(SeasonAdmin.actions) + [sync_selected_seasons]
        else:
            SeasonAdmin.actions = [sync_selected_seasons]
        
        if hasattr(SeriesAdmin, 'actions'):
            SeriesAdmin.actions = list(SeriesAdmin.actions) + [sync_past_seasons_for_series]
        else:
            SeriesAdmin.actions = [sync_past_seasons_for_series]
            
    except ImportError:
        logger.warning("Could not import Season/Series admin classes to add sync actions")


def get_sync_dashboard_links() -> list[dict[str, str]]:
    """
    Get links for the sync dashboard to be displayed in admin.
    
    Returns:
        List of dictionaries with 'name', 'url', and 'description' keys
    """
    return [
        {
            'name': 'Sync Series',
            'url': reverse('admin:iracing_sync_series'),
            'description': 'Update all series information'
        },
        {
            'name': 'Sync Current Seasons',
            'url': reverse('admin:iracing_sync_current_seasons'),
            'description': 'Update current and future seasons with events'
        },
        {
            'name': 'Sync Car Classes',
            'url': reverse('admin:iracing_sync_car_classes'),
            'description': 'Update car class definitions'
        },
        {
            'name': 'Sync Past Seasons',
            'url': reverse('admin:iracing_sync_past_seasons'),
            'description': 'Queue sync for all historical seasons (slow)'
        },
    ] 