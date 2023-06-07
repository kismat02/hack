import pandas as pd
import numpy as np
# import optuna

from prepare_data import read_data

# Initial constants from specification
PCT = (2/100/365)

INCASSATION_PCT = .0001
INCASSATION_MIN = 100

MAX_DOWNTIME = 14
MAX_AMT = 1_000_000

ARMORED_CAR_PRICE = 20_000
MAX_TRAVEL_TIME = 12 * 60
STOP_TIME = 10

BEST_CASH_WEIGHT = 0.07387688919651192
BEST_NUM_OF_TERMINALS_TO_CASH_OUT = 133


def incassation_price(amount):
    return max(INCASSATION_MIN, INCASSATION_PCT * amount)


def incassation_price_fix(amount, n_cars, n_points):
    return incassation_price(amount) + (n_cars / n_points) * ARMORED_CAR_PRICE


def incassation_price_by_time(amount, waiting_days):
    """Return pencents from start time to time then we NEED to do incassation."""
    # if we have some money and need to wait n_days to next incassation
    # it can be more profitable to do it now 
    return incassation_price(amount) * waiting_days


def amount_price(amount):
    return amount * INCASSATION_PCT


def estimate_waiting_days(amt_history):
    pass


class PoiStats():
    """Counting poi statistics class."""
    
    def __init__(self, sum_dict, top_k=100, start_date=None, weights=(0.5, 0.5)):
        if start_date is None:
            raise ValueError('start_date must be non empty')
        else:
            self.start_date = pd.to_datetime(start_date)
        
        self._state_date = self.start_date
        self.sum_dict = sum_dict
        self.state_dict = {elem: 0 for elem in sum_dict.keys()}
        self.top_k = top_k
        
        self._required_list = []
        self._optional_list = []
        self._daily_list = []
        
        self._n_violations = 0
        self._weights = weights
    
    def update_day(self, day_sum_dict, daily_list=None):
        """Function to get incassation points for every day."""
        if daily_list is None:
            self._daily_list = self._get_required_poi() + self._get_optional_poi()
        else:
            self._daily_list = daily_list
        
        # if point in incassation list -> we restart state counter (num of days)
        # if point in incassation list -> we restart point cash amount (with last day value)
        for elem in self.sum_dict:
            if elem in self._daily_list:
                self.state_dict[elem] = 0
                self.sum_dict[elem] = day_sum_dict[elem]
            else:
                self.state_dict[elem] += 1
                self.sum_dict[elem] += day_sum_dict[elem]
       
        self._check_violations()
        self._state_date += pd.Timedelta('24 hours')
    
    def _check_violations(self):
        """Function to check, if there is any rules violations."""
        self._n_violations += len([elem for elem, val in self.state_dict.items() if val >= MAX_DOWNTIME])
        self._n_violations += max(0, len(self._required_list) - self.top_k)
    
    def _get_required_poi(self):
        self._required_list = [elem for elem, val in self.sum_dict.items() if val >= MAX_AMT]
        return self._required_list
        
    def _get_optional_poi(self):
        # normalized score is sum of normalized (between 0 and 1) daily and amount score
        self._normalized_dict = {}
        # weights are importances of time and cash amount to sort points
        for elem in self.sum_dict:
            self._normalized_dict[elem] = (self._weights[0] * self.sum_dict[elem] / MAX_AMT + 
                                          self._weights[1] * self.state_dict[elem] / MAX_DOWNTIME)
        
        # if there is some space, we take into roures not only points with > 1 mln RUB cash amount
        # but some more points (with suitable timing or amount of money)
        self._optional_list = [
            elem for elem, _ in sorted(self._normalized_dict.items(), key=lambda x: x[1], reverse=True)
            if elem not in self._required_list][:max(0, self.top_k - len(self._required_list))
        ]
        
        return self._optional_list


# def objective_function(trial):
#     amt_weight = trial.suggest_float("amt_weight", 0.01, 0.99)
#     n_points = trial.suggest_int("n_points", 90, 150)
#     obj = 10**6

#     stat_obj = PoiStats(
#         cash_ts[DAYS[0]].to_dict(),
#         n_points,
#         start_date='2022-08-31 00:00:00', 
#         weights=(amt_weight, 1 - amt_weight)
#     )

#     for day in DAYS[1:]:
#         stat_obj.update_day(cash_ts[day].to_dict())

#     step_obj = int(stat_obj._n_violations > 0) * 10**5 + n_points

#     if obj > step_obj:
#         obj = step_obj

#     return obj

def find_terminals_to_cash_out() -> dict[str, list[int]]:
    """Find terminals that satisfy conditions to be cashed out for every day."""
    cash_ts, _, _ = read_data()
    cash_ts.index = cash_ts['TID']

    days = cash_ts.columns[1:]

    # if we want to get new best parameters, we need to uncomment code below

    # study = optuna.create_study(sampler=optuna.samplers.TPESampler(seed=2023))
    # study.optimize(objective_function, n_trials=100)
    # print(study.best_params, study.best_value)

    # These are founded by optuna best parameters
    # best_amt_weight - importance of time and money charasteristics
    # best_value - number of collection points per day 

    stat_obj = PoiStats(
        cash_ts[days[0]].to_dict(),
        BEST_NUM_OF_TERMINALS_TO_CASH_OUT,
        start_date='2022-08-31 00:00:00', 
        weights=(BEST_CASH_WEIGHT, 1 - BEST_CASH_WEIGHT)
    )

    day_required_terminals = {}

    for day in days[1:]:
        stat_obj.update_day(cash_ts[day].to_dict())
        day_required_terminals[day] = stat_obj._daily_list
        if BEST_NUM_OF_TERMINALS_TO_CASH_OUT < len(stat_obj._required_list):
            raise NameError("There is no parameters without 1 mln RUB rule violation")

    return day_required_terminals
