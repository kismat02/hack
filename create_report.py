import pandas as pd
from get_routes import find_optimal_routes_with_iterating_num_vehicles
from find_terminals_to_cash_out import find_terminals_to_cash_out
from prepare_data import create_distance_matrix, get_mappings, prepare_data
from schedule_report import create_report_for_schedules, get_schedules_of_vehicles, postprocess_schedules
from calculate_costs import calc_daily_costs, find_daily_vehicles_cost


def make_overall_sheet(funding: pd.DataFrame, collection: pd.DataFrame):
    overall = pd.concat([
        pd.DataFrame({"статья расходов": "фондирование", **funding.sum(axis=0).to_dict()}, index=[0]),
        pd.DataFrame({"статья расходов": "инкассация", **collection.sum(axis=0).to_dict()}, index=[0]),
    ])

    daily_vehicles_cost = find_daily_vehicles_cost(routes)
    vehicles_cost = {dt: daily_vehicles_cost for dt in overall.drop("статья расходов", axis=1).columns}
    overall = pd.concat([
        overall,
        pd.DataFrame({"статья расходов": "стоимость броневиков", **vehicles_cost}, index=[0]),
    ])

    overall = pd.concat([
        overall,
        pd.DataFrame({"статья расходов": "итого", **overall.drop("статья расходов", axis=1).sum(axis=0).to_dict()}, index=[0]),
    ])
    return overall


if __name__ == "__main__":
    day_terminals_to_cash_out = find_terminals_to_cash_out()

    incomes, times = prepare_data()
    tid_2_idx, idx_2_tid = get_mappings()
    times["Destination_tid_idx"] = times["Destination_tid"].map(tid_2_idx)

    distance_matrix = create_distance_matrix()

    routes = {}
    max_num_vehicles = 0
    for day, terminals in day_terminals_to_cash_out.items():
        route, num_vehicles = find_optimal_routes_with_iterating_num_vehicles(
            distance_matrix=distance_matrix,
            terminals_to_cash_out=terminals,
            tid_2_idx=tid_2_idx,
            idx_2_tid=idx_2_tid,
            min_num_vehicles=8,
            max_num_vehicles=len(terminals) // 4 + 1,
        )
        max_num_vehicles = max(max_num_vehicles, num_vehicles)
        routes[day] = {"route": route, "num_vehicles": max_num_vehicles}

    schedules = get_schedules_of_vehicles(routes)
    report = create_report_for_schedules(schedules)
    final_report = postprocess_schedules(report)
    final_report[["дата-время прибытия", "дата-время отъезда"]] = final_report[["дата-время прибытия", "дата-время отъезда"]].astype(str)

    collection, funding, curr_sum = calc_daily_costs(routes)
    overall = make_overall_sheet(funding, collection)

    with pd.ExcelWriter("report.xlsx", date_format="YYYY-MM-DD HH:MM") as writer:
        curr_sum.to_excel(writer, sheet_name="остатки на конец дня")
        funding.to_excel(writer, sheet_name="стоимость фондирования")
        collection.to_excel(writer, sheet_name="стоимость инкассации")
        final_report.drop("день", axis=1).to_excel(writer, sheet_name="маршруты", index=False)
        overall.to_excel(writer, sheet_name="итог", index=False)
