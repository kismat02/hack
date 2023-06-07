import pandas as pd
from itertools import chain
from find_terminals_to_cash_out import ARMORED_CAR_PRICE, incassation_price, PCT
from prepare_data import prepare_data


def flatten_list(x: list[list[int]]) -> list[int]:
    return list(chain(*x))


def find_daily_vehicles_cost(routes_with_num_vehiles: dict[str, dict]) -> int:
    """Return vehicles cost for a day."""
    max_num_vehicles = 0

    # get total price of our automobile park
    for day in routes_with_num_vehiles.keys():
        max_num_vehicles = max(max_num_vehicles, routes_with_num_vehiles[day]["num_vehicles"])
    return ARMORED_CAR_PRICE * max_num_vehicles


def calc_daily_costs(routes_with_num_vehiles) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Calculate collection and funding costs + remaining cash in terminal."""
    # prepare initial data
    incomes, _ = prepare_data()
    incomes = incomes.sort_values(["timestamp", "TID"])
    incomes["timestamp"] = incomes["timestamp"].astype(str)

    # get top-k terminals for every day
    day_terminals = {day.split()[0]: flatten_list(v["route"]) for day, v in routes_with_num_vehiles.items()}
    collection_schedule = pd.DataFrame(day_terminals.items(), columns=["timestamp", "TID"]).explode("TID")

    # get daily incomes
    incomes = (
        incomes
        .merge(collection_schedule.assign(was_collection=1), on=["TID", "timestamp"], how="left")
        .fillna(0)
    )

    results = []
    # going by points and add spents
    for terminal in incomes["TID"].unique():
        curr_sum = 0
        for i, (_, row) in enumerate(incomes.query(f"TID == {terminal}").iterrows()):
            if i == 0:
                curr_sum = row["cash"]
            else:
                new_row = {"TID": terminal, "timestamp": row["timestamp"]}
                if row["was_collection"]:
                    new_row["funding"] = 0
                    new_row["cur_sum"] = 0
                    new_row["collection"] = incassation_price(curr_sum) # price of incassation (depends of money amount)
                    curr_sum = row["cash"] # only amount of cash for day, because money was taken by auto
                else:
                    new_row["funding"] = PCT * curr_sum # price of percents
                    new_row["collection"] = 0
                    new_row["cur_sum"] = curr_sum
                    curr_sum += row["cash"]
                results.append(pd.DataFrame(new_row, index=[0]))
    results = pd.concat(results).reset_index(drop=True)

    # get total spents
    collection = results.drop(["funding", "cur_sum"], axis=1).pivot_table(index="TID", columns="timestamp")
    funding = results.drop(["collection", "cur_sum"], axis=1).pivot_table(index="TID", columns="timestamp")
    curr_sum = results.drop(["funding", "collection"], axis=1).pivot_table(index="TID", columns="timestamp")

    # get overall dataframe
    for df in (collection, funding, curr_sum):
        df.columns = df.columns.droplevel(0)
        df.columns.name = ''
        df.index.name = "Устройство"

    return collection, funding, curr_sum
