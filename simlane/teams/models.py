import uuid

from django.db import models

from simlane.sim.models import Event
from simlane.sim.models import EventClass
from simlane.sim.models import EventInstance
from simlane.sim.models import SimCar
from simlane.users.models import User


# Create your models here.
class Club(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    logo_url = models.URLField(blank=True)
    website = models.URLField(blank=True)
    social_links = models.JSONField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    discord_guild_id = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["discord_guild_id"]),
        ]

    def __str__(self):
        return self.name


class ClubMember(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="clubs")
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="members")
    role = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "club"]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["club"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.club.name}"


class Team(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="teams")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    logo_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["club", "name"]
        indexes = [
            models.Index(fields=["club"]),
        ]

    def __str__(self):
        return f"{self.club.name} - {self.name}"


class TeamMember(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="team_members",
    )
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="members")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "team"]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["team"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.team.name}"


class EventEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="entries")
    sim_car = models.ForeignKey(
        SimCar,
        on_delete=models.CASCADE,
        related_name="entries",
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entries",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="event_entries",
    )
    event_class = models.ForeignKey(
        EventClass,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entries",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["event"]),
            models.Index(fields=["sim_car"]),
            models.Index(fields=["team"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.event.name}"


class DriverAvailability(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_entry = models.ForeignKey(
        EventEntry,
        on_delete=models.CASCADE,
        related_name="availabilities",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="driver_availabilities",
    )
    instance = models.ForeignKey(
        EventInstance,
        on_delete=models.CASCADE,
        related_name="availabilities",
    )
    available = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["event_entry", "user", "instance"]
        indexes = [
            models.Index(fields=["event_entry"]),
            models.Index(fields=["user"]),
            models.Index(fields=["instance"]),
        ]

    def __str__(self):
        return (
            f"{self.event_entry.user.username} - "
            f"{self.instance.event.name} - "
            f"{self.available}"
        )


class PredictedStint(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_entry = models.ForeignKey(
        EventEntry,
        on_delete=models.CASCADE,
        related_name="predicted_stints",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="predicted_stints",
    )
    instance = models.ForeignKey(
        EventInstance,
        on_delete=models.CASCADE,
        related_name="predicted_stints",
    )
    stint_order = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["event_entry"]),
            models.Index(fields=["user"]),
            models.Index(fields=["instance"]),
        ]

    def __str__(self):
        return (
            f"{self.event_entry.user.username} - "
            f"{self.instance.event.name} - "
            f"{self.stint_order}"
        )
