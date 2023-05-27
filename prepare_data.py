import numpy as np
import pandas as pd


def read_data():
    terminals_coords = pd.read_excel("terminal_data_hackathon v4.xlsx", sheet_name="TIDS")
    incomes = pd.read_excel("terminal_data_hackathon v4.xlsx", sheet_name="Incomes")
    times = pd.read_csv("times v4.csv")
    return incomes, times, terminals_coords


def prepare_data():
    """Read data and make some processing."""
    incomes, times, _ = read_data()
    times['Total_Time'] = times['Total_Time'] + 10  # If vehicle arrives, it must spend 10 minutes
    times['Origin_tid'] = times['Origin_tid'].astype('category')
    times['Origin_tid_idx'] = times['Origin_tid'].cat.codes

    incomes = pd.melt(incomes, id_vars=["TID"], var_name="timestamp", value_name="cash")
    incomes.loc[incomes["timestamp"] == "остаток на 31.08.2022 (входящий)", "timestamp"] = "2022-08-31 00:00:00"
    incomes["timestamp"] = pd.to_datetime(incomes["timestamp"])
    return incomes, times


def get_mappings() -> tuple[dict[int, int]]:
    """Return mappings from TID to number from 0 to lenngth of unnique TIDs and vice versa."""
    _, times = prepare_data()
    tid_2_idx = {tid: idx for _, (tid, idx) in times[['Origin_tid', 'Origin_tid_idx']].drop_duplicates().iterrows()}
    idx_2_tid = {idx: tid for tid, idx in tid_2_idx.items()}
    return tid_2_idx, idx_2_tid


def create_distance_matrix() -> np.ndarray:
    """Return distance matriix from times df: Origin TID -> Destination TID times."""
    _, times = prepare_data()
    tid_2_idx, _ = get_mappings()
    times["Destination_tid_idx"] = times["Destination_tid"].map(tid_2_idx)
    distance_matrix = pd.concat([
        times[["Origin_tid_idx", "Destination_tid_idx", "Total_Time"]],
        pd.DataFrame({
            "Origin_tid_idx": range(times["Origin_tid"].nunique()),
            "Destination_tid_idx": range(times["Origin_tid"].nunique()),
            "Total_Time": 0
        })
    ])
    distance_matrix = distance_matrix.pivot_table(index="Origin_tid_idx", columns="Destination_tid_idx").values
    distance_matrix = distance_matrix.round(0).astype(int)  # for ortools because it works only with int
    return distance_matrix


# from geopy.distance import geodesic
# def calculate_distances(df: pd.DataFrame) -> np.array:
#     distances = np.zeros((df.shape[0], df.shape[0]))
#     for i1, row1 in tqdm(df.iloc[:-1].iterrows()):
#         for i2, row2 in df.iloc[i1 + 1:].iterrows():
#             distance = geodesic((row1["latitude"], row1["longitude"]), (row2["latitude"], row2["longitude"])).meters
#             distances[i1, i2] = distance
#             distances[i2, i1] = distance
#     return distances

