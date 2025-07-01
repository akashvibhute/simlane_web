from django.urls import path

from .dashboard_views import (
    OverviewView,
    MembersView,
    TeamsView,
    EventsView,
    RequestsView,
    DiscordSettingsView,
    ClubSettingsView,
    UpdateBasicInfoView,
    UploadLogoView,
    RemoveBannerView,
    UploadBannerView,
    UpdatePrivacySettingsView,
    ArchiveClubView,
    DeleteClubView,
    SyncDiscordRolesView,
    RefreshDiscordChannelsView,
    UpdateDiscordChannelsView,
    UpdateDiscordNotificationsView,
    UpdateDiscordRoleMappingView,
    TestDiscordNotificationsView,
    DisconnectDiscordView,
)

app_name = "clubs"

urlpatterns = [
    # Root -> overview
    path(
        "<slug:club_slug>/",
        OverviewView.as_view(),
        name="dashboard_root",
    ),
    path("<slug:club_slug>/overview/", OverviewView.as_view(), name="overview"),
    path("<slug:club_slug>/members/", MembersView.as_view(), name="members"),
    path("<slug:club_slug>/teams/", TeamsView.as_view(), name="teams"),
    path("<slug:club_slug>/events/", EventsView.as_view(), name="events"),
    path("<slug:club_slug>/requests/", RequestsView.as_view(), name="requests"),
    path("<slug:club_slug>/discord/", DiscordSettingsView.as_view(), name="discord"),
    path("<slug:club_slug>/settings/", ClubSettingsView.as_view(), name="settings"),
    
    # Settings actions
    path("<slug:club_slug>/settings/update-basic-info/", UpdateBasicInfoView.as_view(), name="update_basic_info"),
    path("<slug:club_slug>/settings/upload-logo/", UploadLogoView.as_view(), name="upload_logo"),
    path("<slug:club_slug>/settings/remove-banner/", RemoveBannerView.as_view(), name="remove_banner"),
    path("<slug:club_slug>/settings/upload-banner/", UploadBannerView.as_view(), name="upload_banner"),
    path("<slug:club_slug>/settings/update-privacy/", UpdatePrivacySettingsView.as_view(), name="update_privacy_settings"),
    path("<slug:club_slug>/settings/archive/", ArchiveClubView.as_view(), name="archive_club"),
    path("<slug:club_slug>/settings/delete/", DeleteClubView.as_view(), name="delete_club"),
    
    # Discord actions
    path("<slug:club_slug>/discord/sync-roles/", SyncDiscordRolesView.as_view(), name="sync_discord_roles"),
    path("<slug:club_slug>/discord/refresh-channels/", RefreshDiscordChannelsView.as_view(), name="refresh_discord_channels"),
    path("<slug:club_slug>/discord/update-channels/", UpdateDiscordChannelsView.as_view(), name="update_discord_channels"),
    path("<slug:club_slug>/discord/update-notifications/", UpdateDiscordNotificationsView.as_view(), name="update_discord_notifications"),
    path("<slug:club_slug>/discord/update-role-mapping/", UpdateDiscordRoleMappingView.as_view(), name="update_discord_role_mapping"),
    path("<slug:club_slug>/discord/test-notifications/", TestDiscordNotificationsView.as_view(), name="test_discord_notifications"),
    path("<slug:club_slug>/discord/disconnect/", DisconnectDiscordView.as_view(), name="disconnect_discord"),
] 