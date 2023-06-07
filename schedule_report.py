import pandas as pd
from datetime import datetime, timedelta
from prepare_data import get_mappings, create_distance_matrix


def get_schedules_of_vehicles(routes_with_num_vehiles: dict) -> dict:
    """Return everyday schedule of armoured vehicles based on their routes."""
    tid_2_idx, _ = get_mappings()
    # we need to add 10 minutes to do incassation
    distance_matrix = create_distance_matrix() - 10
    # we can't go back in time ;)
    distance_matrix[distance_matrix < 0] = 0

    schedules = {}
    for day_str, inner_dict in routes_with_num_vehiles.items():
        schedules[day_str] = {}
        for vehicle_id, route in enumerate(inner_dict["route"]):
            cur_time = datetime.strptime(day_str, "%Y-%m-%d %H:%M:%S") + timedelta(hours=8)
            terminal_ids = [tid_2_idx[tid] for tid in route]
            schedules[day_str][vehicle_id] = {}

            if len(terminal_ids) == 1:
                # If a vehicle has only 1 terminal to attend
                schedules[day_str][vehicle_id][route[0]] = (
                    cur_time,
                    cur_time + timedelta(minutes=10)
                )
            else:
                for i in range(1, len(terminal_ids)):
                    schedules[day_str][vehicle_id][route[i - 1]] = (
                        cur_time,
                        cur_time + timedelta(minutes=10)
                    )

                    time_to_next_terminal = int(distance_matrix[terminal_ids[i-1], terminal_ids[i]])
                    cur_time += timedelta(minutes=time_to_next_terminal + 10)
                
                if i == len(terminal_ids) - 1:
                    # Don't forget about last terminal
                    schedules[day_str][vehicle_id][route[i]] = (
                        cur_time,
                        cur_time + timedelta(minutes=10)
                    )

    return schedules


def create_report_for_schedules(schedules: dict) -> pd.DataFrame:
    """Return report of every day schedule of armoured vehicles based on their schedules."""
    df_data = []
    for day, routes in schedules.items():
        for vehicle_id, vehicle_data in routes.items():
            for terminal_id, (arrival_time, departure_time) in vehicle_data.items():
                df_data.append({
                    "день": day.split()[0],
                    "порядковый номер броневика": vehicle_id,
                    "устройство": terminal_id,
                    "дата-время прибытия": arrival_time,
                    "дата-время отъезда": departure_time
                })
    return pd.DataFrame(df_data)


def postprocess_schedules(schedules_report: pd.DataFrame) -> pd.DataFrame:
    """
    If somehow some vehicle gets terminals after 20:00,
    it is needed to give these terminals to another vehicles.
    So, we find such terminals, find free vehicles and assigm these terminals to these free vehicles.
    """
    tid_2_idx, _ = get_mappings()
    distance_matrix = create_distance_matrix()
    schedules_report_copy = schedules_report.copy()
    violated_routes = schedules_report[pd.to_datetime(schedules_report["дата-время отъезда"]).dt.hour >= 20]
    new_rows = []
    # going by violations and get cars with some free space in it
    for idx, row in violated_routes.iterrows():
        free_vehicle = (
            schedules_report_copy[
                (schedules_report_copy["день"] == row["день"])
                & (schedules_report_copy["порядковый номер броневика"] != row["порядковый номер броневика"])
            ]
            .groupby("порядковый номер броневика")
            ["дата-время отъезда"]
            .agg("max")
            .idxmin()
        )

        # get routes of "free" vehicles
        terminals_of_free_vehicle = schedules_report_copy[
            (schedules_report_copy["день"] == row["день"])
            & (schedules_report_copy["порядковый номер броневика"] == free_vehicle)
        ].sort_values("дата-время отъезда")

        last_terminal_of_free_vehicle = terminals_of_free_vehicle["устройство"].values[-1]
        last_arrival_of_free_vehicle = terminals_of_free_vehicle["дата-время отъезда"].tolist()[-1]
        time_to_next_terminal = int(
            distance_matrix[tid_2_idx[last_terminal_of_free_vehicle], tid_2_idx[row["устройство"]]]
        ) - 10  # We add 10 minutes to all times Origin TID -> Destination TID, so we need to subtract 10

        assert (
            (last_arrival_of_free_vehicle + timedelta(minutes=time_to_next_terminal + 10)).hour < 20,
            f"Cannot move terminal {row['устройство']} to another vehicle {free_vehicle} on {row['день']}"
        )

        # change vehicle for some points
        new_row = {
            "день": row["день"],
            "порядковый номер броневика": free_vehicle,
            "устройство": row["устройство"],
            "дата-время прибытия": last_arrival_of_free_vehicle + timedelta(minutes=time_to_next_terminal),
            "дата-время отъезда": last_arrival_of_free_vehicle + timedelta(minutes=time_to_next_terminal + 10),
        }
        new_rows.append(pd.DataFrame(new_row, index=[0]))
        schedules_report_copy = schedules_report_copy.drop(index=[idx])
    return pd.concat([schedules_report_copy, pd.concat(new_rows)]).reset_index(drop=True)
