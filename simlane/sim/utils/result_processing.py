from simlane.sim.models import EventResult, TeamResult, ParticipantResult
from django.db import transaction
from simlane.teams.models import Team
from simlane.sim.models import SimProfile


def create_event_result_from_api(event_instance, api_data):
    """
    Create or update an EventResult from API data for a given EventInstance.
    Returns the EventResult instance.
    """
    result, _ = EventResult.objects.update_or_create(
        event_instance=event_instance,
        defaults={
            'subsession_id': api_data.get('subsession_id'),
            'session_id': api_data.get('session_id'),
            'num_drivers': api_data.get('num_drivers', 0),
            'event_best_lap_time': api_data.get('event_best_lap_time'),
            'event_average_lap': api_data.get('event_average_lap'),
            'start_time': api_data.get('start_time'),
            'end_time': api_data.get('end_time'),
            'weather_data': api_data.get('weather'),
            'track_state': api_data.get('track_state'),
            'track_data': api_data.get('track'),
            'raw_api_data': api_data,
            'is_processed': False,
        }
    )
    return result


def get_all_participants_for_event(event_result):
    """
    Fetch all ParticipantResult objects for a given EventResult (solo and team events).
    """
    solo = list(event_result.participants.all())
    team = list(ParticipantResult.objects.filter(team_result__event_result=event_result))
    return solo + team


def calculate_average_irating_change(event_result):
    """
    Calculate the average iRating change for all participants in an event.
    Returns None if no valid data.
    """
    participants = get_all_participants_for_event(event_result)
    changes = [p.i_rating_change for p in participants if p.i_rating_change is not None]
    if not changes:
        return None
    return sum(changes) / len(changes)


def create_team_and_participant_results(event_result, team_results_data):
    """
    Bulk create TeamResult and ParticipantResult objects from API data.
    team_results_data: list of team result dicts from API.
    """
    with transaction.atomic():
        for team_data in team_results_data:
            # Team lookup or creation
            team_obj, _ = Team.objects.get_or_create(
                sim_api_id=team_data['team_id'],
                defaults={
                    'name': team_data.get('display_name', f"Team {team_data['team_id']}")
                }
            )
            team_result = TeamResult.objects.create(
                event_result=event_result,
                team=team_obj,
                team_display_name=team_data.get('display_name', ''),
                finish_position=team_data.get('finish_position'),
                finish_position_in_class=team_data.get('finish_position_in_class'),
                laps_complete=team_data.get('laps_complete', 0),
                laps_lead=team_data.get('laps_lead', 0),
                incidents=team_data.get('incidents', 0),
                best_lap_time=team_data.get('best_lap_time'),
                best_lap_num=team_data.get('best_lap_num'),
                average_lap=team_data.get('average_lap'),
                champ_points=team_data.get('champ_points', 0),
                reason_out=team_data.get('reason_out', ''),
                reason_out_id=team_data.get('reason_out_id'),
                drop_race=team_data.get('drop_race', False),
                car_id=team_data.get('car_id'),
                car_class_id=team_data.get('car_class_id'),
                car_class_name=team_data.get('car_class_name', ''),
                car_name=team_data.get('car_name', ''),
                country_code=team_data.get('country_code', ''),
                division=team_data.get('division'),
                raw_team_data=team_data,
            )
            for driver_data in team_data.get('driver_results', []):
                # SimProfile lookup or creation
                sim_profile_obj, _ = SimProfile.objects.get_or_create(
                    sim_api_id=driver_data['cust_id'],
                    defaults={
                        'display_name': driver_data.get('display_name', f"Driver {driver_data['cust_id']}")
                    }
                )
                ParticipantResult.objects.create(
                    sim_profile=sim_profile_obj,
                    team_result=team_result,
                    driver_display_name=driver_data.get('display_name', ''),
                    finish_position=driver_data.get('finish_position'),
                    finish_position_in_class=driver_data.get('finish_position_in_class'),
                    starting_position=driver_data.get('starting_position'),
                    starting_position_in_class=driver_data.get('starting_position_in_class'),
                    laps_complete=driver_data.get('laps_complete', 0),
                    laps_lead=driver_data.get('laps_lead', 0),
                    incidents=driver_data.get('incidents', 0),
                    best_lap_time=driver_data.get('best_lap_time'),
                    best_lap_num=driver_data.get('best_lap_num'),
                    average_lap=driver_data.get('average_lap'),
                    champ_points=driver_data.get('champ_points', 0),
                    oldi_rating=driver_data.get('oldi_rating'),
                    newi_rating=driver_data.get('newi_rating'),
                    old_license_level=driver_data.get('old_license_level'),
                    new_license_level=driver_data.get('new_license_level'),
                    old_sub_level=driver_data.get('old_sub_level'),
                    new_sub_level=driver_data.get('new_sub_level'),
                    reason_out=driver_data.get('reason_out', ''),
                    reason_out_id=driver_data.get('reason_out_id'),
                    drop_race=driver_data.get('drop_race', False),
                    car_id=driver_data.get('car_id'),
                    car_class_id=driver_data.get('car_class_id'),
                    car_class_name=driver_data.get('car_class_name', ''),
                    car_name=driver_data.get('car_name', ''),
                    country_code=driver_data.get('country_code', ''),
                    division=driver_data.get('division'),
                    raw_participant_data=driver_data,
                ) 