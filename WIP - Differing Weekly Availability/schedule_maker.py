import os
import sys
import time
import pandas as pd
import numpy as np
from pprint import pprint
from constraint import *
from collections import Counter, defaultdict

####### Main function to generate schedule #######
def generate_schedule(dataframe, suffix = None):

    if suffix is not None:
        suffix = str(suffix)
    elif suffix is None:
        suffix = str(input("Please specify a suffix for the schedule: "))

    df = dataframe
    num_shopkeepers = len(df.columns[3:])

    check_input_range(df)

    # specify the date format explicitly
    df['Date'] = pd.to_datetime(df['Date'], format = "%d/%m/%Y")

    # extract unique weeks, days, and times
    df['Week'] = df['Date'].dt.isocalendar().week
    unique_weeks = df['Week'].unique()
    unique_days = df['Day'].unique()
    timeslots = df['Time'].unique()

    # create a team availability dictionary for each week, day, and time
    team = create_team_availability(df, unique_weeks, unique_days, timeslots)

    # CSP setup
    solutions_per_week = create_solutions_per_week(team, unique_weeks, unique_days, timeslots)

    # find most consistent solutions
    most_consistent_solutions = extract_most_consistent_solutions(solutions_per_week, team, num_shopkeepers)

    # now that you found solutions that fit best (most consistent),
    # for each solution come up with a schedule that takes care of the remaining weeks
    filled_solutions, unassigned_slots = fill_remaining_weeks(most_consistent_solutions, unique_weeks, team)

    # prompt user to choose between solutions if there are multiple best solutions
    best_solution, remind_list, remind_to_add_manually = pick_solution(filled_solutions, unassigned_slots)

    # write the schedule and warn one more time if necessary.
    df = dict_to_dataframe(best_solution, df)

    cd = os.getcwd()
    output_path = os.path.join(cd, 'output')
    if not os.path.exists(output_path):
        os.mkdir(output_path)
    output_file = f'schedule_{suffix}.xlsx'
    full_path = os.path.join(output_path, output_file)
    df.to_excel(full_path)
    print(f'Final schedule created and written to "{full_path}"')

    if remind_to_add_manually:
        RED_TEXT = "\033[91m"
        RESET_TEXT = "\033[0m"
        print(f"{RED_TEXT}REMINDER TO ADD THE FOLLOWING PEOPLE MANUALLY{RESET_TEXT}")
        print(remind_list)

    return df

####### sub-functions #######
def check_input_range(df):
    allowed_input = ['Yes', 'No', 'Preferably Not', np.nan]
    if not df.iloc[:, 5:].isin(allowed_input).all().all():
        sys.exit("Please only use 'Yes', 'Preferably Not' or 'No' as input")

def create_team_availability(df, unique_weeks, unique_days, timeslots):
    team = {}
    for person in df.columns[3:]:
        if person == 'Week':
            break
        else:
            team[person] = {}
            for week in unique_weeks:
                for day in unique_days:
                    for time in timeslots:
                        availability = df[(df['Day'] == day) & (df['Week'] == week) & (df['Time'] == time)][
                            person].values
                        team[person][f'{week}_{day}_{time}'] = availability[0] if availability.size > 0 else 'No'

    # add filler with availability for all timeslots
    team["filler"] = {}
    for week in unique_weeks:
        for day in unique_days:
            for time in timeslots:
                team["filler"][f'{week}_{day}_{time}'] = 'Yes'

    return team

def create_solutions_per_week(team, unique_weeks, unique_days, timeslots):
    solutions_per_week = {}
    num_shopkeepers = len(team.keys())

    for week in unique_weeks: # [:-1]? why?
        # initialize domains dict, domains are the values a variable can take
        domains = {}
        for day in unique_days:
            for time in timeslots:
                # changed to only day and time, might want to change this in team dict as well
                day_time_key = f'{day}_{time}'
                domain = []
                for person in team.keys():
                    availability = team[person].get(f'{week}_{day}_{time}',
                                                    'No')  # just a sanity check to default to 'No'
                    if availability != 'No':
                        domain.append(person)
                domains[day_time_key] = domain

        def check_absence(domains, team):
            all_values = [name for sublist in domains.values() for name in sublist]
            unique_entries = set(all_values)

            employees = set(team.keys())

            absent = list(employees - unique_entries)

            return absent

        absentee = check_absence(domains, team)
        num_absent = len(absentee)

        # Set up the CSP problem
        problem = Problem()

        # add variables and related domains only for non-empty domains
        for day_time_key, domain in domains.items():
            if len(domain) > 0:
                problem.addVariable(variable=day_time_key, domain=domain)

        problem.addConstraint(FunctionConstraint(lambda *values:
                                                 custom_constraint(
                                                     *values,
                                                     num_shopkeepers= num_shopkeepers-num_absent
                                                 )))
        # get solutions
        solutions = problem.getSolutions()

        # delete "filler"
        solutions = delete_filler(solutions)

        # store solutions per week
        solutions_per_week[week] = solutions

    return solutions_per_week

def custom_constraint(*values, num_shopkeepers):

    unique_names = set(values)
    compatible = True
    if len(unique_names) != num_shopkeepers:
        compatible = False
        return compatible # early return

    for name in unique_names:
        if name != "filler":
            name_count = values.count(name)
            if name_count > 1:
                compatible = False
                return compatible # early return

    return compatible

def delete_filler(solutions):
    for solution in solutions:
        # create a list of timeslots to delete
        timeslots_to_delete = [timeslot for timeslot, name in solution.items() if name == "filler"]
        # remove filler timeslots
        for timeslot in timeslots_to_delete:
            del solution[timeslot]
    return solutions

def extract_most_consistent_solutions(solutions_per_week, team, num_shopkeepers):
    # create a list to gather all unique solutions
    all_solutions = []

    # gather all solutions from solutions_per_week
    for week, solutions in solutions_per_week.items():
        all_solutions.extend(solutions)

    # so the problem that occurs here is that filled in spots that technically are removed later in the script
    # still occur here. So technically I should implement that step before this step already

    # count occurrences of each unique solution
    solution_counts = Counter(tuple(sorted(solution.items())) for solution in all_solutions)

    # find the maximum count
    max_count = max(solution_counts.values())

    # filter solutions that have the maximum count and convert tuples back to dicts
    most_common_solutions = [dict(solution) for solution, count in solution_counts.items() if count == max_count]

    # for solution in most_common_solutions:
    #     timeslots = list(solution.keys())
    #     days = [key.split('_')[0] for key in timeslots]
    #     unique_days = set(days)
    #     if len(unique_days) < 4:
    #         most_common_solutions.remove(solution)

    # the following basically checks if any of the solutions include a timeslot that is not preferred by the employee
    solutions_preference = filter_preferred_solutions(most_common_solutions,
                                                      solutions_per_week,
                                                      team,
                                                      num_shopkeepers)
    while len(solutions_preference) == 0:
        max_count -= 1
        most_common_solutions = [dict(solution) for solution, count in solution_counts.items() if count == max_count]
        solutions_preference = filter_preferred_solutions(most_common_solutions,
                                                          solutions_per_week,
                                                          team,
                                                          num_shopkeepers)

    # potentially also check whether the number of unique days is at least 4?

    # extract for what weeks the particular solutions appear
    most_consistent_solutions = link_solution_to_weeks(solutions_preference)

    return most_consistent_solutions

def filter_preferred_solutions(most_common_solutions, solutions_per_week, team, num_shopkeepers):
    # instead of immediately deleting, possibly just keep a list of the index and then delete later if
    # pref_not is larger than, let's say, 2 for a person

    solutions_preference = []
    for week, solutions in solutions_per_week.items():
        for solution in solutions:
            if solution in most_common_solutions:
                for day_time_key, person in list(solution.items()):
                    # extract the week, day, and time from the key (assuming day_time_key is formatted as 'day_time')
                    week_day_time = f"{week}_{day_time_key}"  # construct the correct key to match the `team`

                    # check availability in team dictionary
                    if team[person].get(week_day_time) == 'Preferably Not': #might want to make this a variable/constant
                        # delete the availability from solution
                        del (solution[day_time_key])

                # this basically just adds the solutions where timeslots are preferred (so excludes 'preferably not')
                names_n = len(set(solution.values()))
                if names_n == num_shopkeepers:
                    solutions_preference.append((week, solution))

    return solutions_preference

def link_solution_to_weeks(solutions_preference):
    solution_counts, solution_weeks = Counter(), defaultdict(list)
    for week, solution in solutions_preference:
        sol_tuple = tuple(sorted(solution.items()))
        solution_counts[sol_tuple] += 1
        solution_weeks[sol_tuple].append(week)
    max_count = max(solution_counts.values())

    most_consistent_solutions = [
        {'solution': dict(sol), 'weeks': solution_weeks[sol]} for sol, count in solution_counts.items() if count == max_count]
    return most_consistent_solutions

def fill_remaining_weeks(final_processed_solutions, unique_weeks, team):
    list_of_final_solutions = {}
    filled_solutions = []
    iter = 0
    least_changes = float('inf')
    unassigned_slots = None

    for entry in final_processed_solutions:
        iter += 1
        solution_n = f"solution{iter}"

        # basically what this code does is that it tries to find the solution with the most consistent
        # schedule over the weeks. It does this by checking how many changes per person per week have to be made
        number_of_changes, schedule_per_person, current_unassigned_slots = extract_least_changes(unique_weeks,
                                                                                                team,
                                                                                                entry)
        # store the solution and unassigned slots in the list of final solutions
        list_of_final_solutions[solution_n] = (schedule_per_person, number_of_changes, current_unassigned_slots)

        # check for the best solution with the least number of changes
        if number_of_changes < least_changes:
            least_changes = number_of_changes
            filled_solutions = [schedule_per_person]  # store the current best schedule
            unassigned_slots = [current_unassigned_slots]  # store the corresponding unassigned available slots
        elif number_of_changes == least_changes:
            filled_solutions.append(
                schedule_per_person)  # append the actual schedule if it has the same number of changes
            unassigned_slots.append(current_unassigned_slots)

    return filled_solutions, unassigned_slots

# basically what this code does is that it tries to find the solution with the most consistent
# schedule over the weeks. It does this by checking how many changes per person per week have to be made
def extract_least_changes(unique_weeks, team, entry):
    solution = entry['solution']  # access the 'solution' dictionary
    weeks = entry['weeks']  # access the 'weeks' value
    number_of_changes = 0
    schedule_per_person = defaultdict(dict)
    current_unassigned_slots = defaultdict(dict)
    for week in unique_weeks:
        for day_time_key, person in solution.items():
            week_day_time = f"{week}_{day_time_key}"  # construct the correct key to match the `team`

            if week in weeks:
                # just assign the key corresponding to the person value as the value in the week key
                schedule_per_person[person][week] = (day_time_key)

            else:
                # check if person can still be assigned to same timeslot, if not, select timeslots that are available
                # for that person and request input of user which timeslot they want to pick for this user

                # Check availability in team dictionary
                if team[person].get(week_day_time) != 'No':
                    schedule_per_person[person][week] = (day_time_key)
                    # assign to same timeslot
                else:
                    schedule_per_person[person][week] = 'Not Determined Yet'
                    number_of_changes += 1
                    available_timeslots = {}
                    for timeslot, availability in team[person].items():
                        # Split the key to extract the week part
                        week_na = timeslot.split('_')[0]

                        # Check if the week matches the week of interest and the availability is not 'No'
                        if week_na == str(week) and availability != 'No':
                            available_timeslots[timeslot] = availability

                    if available_timeslots:
                        current_unassigned_slots[person][week] = available_timeslots
                    else:
                        current_unassigned_slots[person][week] = {week: 'No available slots for this week'}

    schedule_per_person = dict(schedule_per_person)
    current_unassigned_slots = dict(current_unassigned_slots)
    return number_of_changes, schedule_per_person, current_unassigned_slots

def pick_solution(filled_solutions, unassigned_slots):
    RED_TEXT = "\033[91m"
    RESET_TEXT = "\033[0m"

    if len(filled_solutions) > 1:
        print(f"{RED_TEXT}Multiple solutions have the least changes. Please choose one:{RESET_TEXT}")
        time.sleep(1.5)

        # pretty print each solution before asking for user input
        for idx, schedule in enumerate(filled_solutions, 1):
            print(f"{RED_TEXT}\nOption {idx}:{RESET_TEXT}")
            pprint(schedule)  # Pretty print the schedule for each option
            print("\n")

        user_choice = int(input("Enter the number of your choice: ")) - 1
        best_solution = filled_solutions[user_choice]  # Get the user's choice
        unassigned_slots = unassigned_slots[user_choice]

    else:  # if there's only one best solution
        best_solution = filled_solutions[0]
        unassigned_slots = unassigned_slots[0]

    # convert defaultdict to dict to remove default_factory, don't know why this happens
    best_solution = {person: dict(weeks) for person, weeks in best_solution.items()}
    unassigned_slots = {person: dict(weeks) for person, weeks in unassigned_slots.items()}

    # so basically what the code below does is check whether there are weeks where employees are not
    # assigned a shift yet. For these weeks, let the user pick the best fitting shift.
    remind_list = []
    remind_to_add_manually = False
    for person, weeks in unassigned_slots.items():
        missing_count = 0
        for week in weeks.keys():
            if best_solution[person][week] == 'Not Determined Yet':
                available_timeslots = unassigned_slots[person][week]

                # retrieve the current week's schedule from best_solution
                week_schedule = defaultdict(dict)

                for person_2, schedule in best_solution.items():
                    for week_2, timeslot in schedule.items():
                        # assign the person to their timeslot in the given week
                        week_schedule[week_2][person_2] = timeslot

                # prompt user to select a date from available timeslots --> see function
                selected_date = prompt_user_to_pick_date(available_timeslots, person, week, week_schedule)

                # update the person's schedule with the selected date
                if selected_date is not None:
                    best_solution[person][week] = selected_date

                # if an employee is completely unavailable for a week, warn the user that the shift
                # needs to be added manually to another week
                elif selected_date is None:
                    missing_count += 1
        if missing_count > 0:
            remind_list.append((person, f"{missing_count} time(s)"))
            remind_to_add_manually = True

    return best_solution, remind_list, remind_to_add_manually

def prompt_user_to_pick_date(available_timeslots, person, week, week_schedule):
    RED_TEXT = "\033[91m"
    RESET_TEXT = "\033[0m"

    if 'No available slots for this week' in available_timeslots.values():
        print(f"{RED_TEXT}No available timeslots for the week {week}. Manually add {person} to other week.{RESET_TEXT}")
        return None

    # display the available timeslots for the person for that week
    print(f"{RED_TEXT}Please pick a timeslot for {person} for the week {week}.{RESET_TEXT}")
    print("Available timeslots:")
    timeslot_list = [timeslot.split('_', 1)[1] for timeslot in available_timeslots.keys()]
    iter = 0

    for timeslot, availability in available_timeslots.items():
        iter += 1
        print(f"{iter}. {timeslot} (Availability: {availability})")

    # display the current week's schedule so that can be taken into account
    print(f"\nCurrent schedule for week {week}:")
    print(week_schedule[week])

    # prompt the user to pick a timeslot
    while True:
        try:
            # select a number between 1 and total number of timeslots
            choice = int(input(f"Please pick a timeslot #number (1-{len(timeslot_list)}): "))

            if 1 <= choice <= len(timeslot_list): # check if response is out of bounds
                selected_timeslot = timeslot_list[choice - 1]
                print(f"You selected: {selected_timeslot}")
                return selected_timeslot
            else: # response is out of bounds
                print(f"Invalid input. Please choose a #number between 1 and {len(timeslot_list)}.")
        except ValueError: # response is not an integer
            print("Invalid input. Please enter a #number.")

# create dataframe from final dictionary
def dict_to_dataframe(schedule_dict, original_df):
    week_day_to_date = dict(zip(zip(original_df['Week'], original_df['Day']), original_df['Date']))
    # Empty list to store entries
    entries = []

    for person, weeks in schedule_dict.items():
        for week, timeslot in weeks.items():
            # Initialize day and time as 'NA'
            day, time, date = 'Add to other week', 'Add to other week', 'Add to other week'

            if timeslot != 'Not Determined Yet':
                day, time = timeslot.split('_')  # Split timeslot into day and time
                date = week_day_to_date.get((week, day), 'NA')  # Get date based on week and day
                date = date.strftime("%x")

            entries.append({
                'Person': person,
                'Week': week,
                'Date': date,
                'Day': day,
                'Time': time
            })

    df = pd.DataFrame(entries)
    #df["Date"] = pd.to_datetime(df["Date"])
    return df

### NO LONGER USED FUNCTIONS ###

# this step is nog longer needed, since I added 'filler' and extra constraints. Now I can just delete the filler
def process_solutions(solutions):
    processed_solutions = []
    seen_solutions = set()  # a set to track unique (solution, weeks) pairs

    # need to be written such that, for every solution where an individual is added more than one time, it creates
    # all possible unique solutions
    for solution_with_weeks in solutions:
        solution = solution_with_weeks['solution']
        weeks = solution_with_weeks['weeks']  # extract weeks information
        appearance_count = defaultdict(int)

        # count appearances for each person
        for person in solution.values():
            appearance_count[person] += 1

        # sort people by the number of appearances (least to most)
        sorted_people = sorted(appearance_count.items(), key=lambda x: x[1])

        # attempt to assign time slots based on sorted appearances
        unique_schedule = assign_timeslots(sorted_people, solution)

        # check if the combination of (solution, weeks) is unique
        solution_tuple = (tuple(unique_schedule.items()), tuple(weeks))
        if solution_tuple not in seen_solutions:
            seen_solutions.add(solution_tuple)  # add to seen set
            # combine the unique schedule with the weeks information
            processed_solutions.append({
                'solution': unique_schedule,
                'weeks': weeks
            })

    return processed_solutions

# this step is nog longer needed, since I added 'filler' and extra constraints. Now I can just delete the filler
def assign_timeslots(sorted_people, solution):
    unique_schedule = {}
    assigned_days = set()  # track assigned days to maximize unique days

    for person, _ in sorted_people:
        for timeslot, assigned_person in solution.items():
            day = timeslot.split('_')[0]  # get the day part of the key

            # only consider time slots assigned to this person
            if assigned_person == person:
                # check if the person has already been assigned to a different time on this day
                if person not in unique_schedule.values() and day not in assigned_days:
                    unique_schedule[timeslot] = person
                    assigned_days.add(day)  # mark this day as assigned

                # if the day is taken and the person has multiple appearances, check for removal
                elif day in assigned_days and person in unique_schedule.values():
                    # check if we need to replace an existing assignment for this person
                    for existing_timeslot, assigned_person in unique_schedule.items():
                        if assigned_person == person and existing_timeslot.split('_')[0] == day:
                            # remove the less favorable assignment
                            del unique_schedule[existing_timeslot]
                            unique_schedule[timeslot] = person
                            break
    return unique_schedule