import os
import pandas as pd
from pprint import pprint
from constraint import *
from collections import Counter, defaultdict


## #####################################
# some considerations:
# - one bug that may need to be resolved is what happens if all of the preferred solutions have
#   a "preferably not" timeslot. I'm not sure what happens then. I guess I would need to rewrite the code
#   such that if that happens, it takes the solutions with the least amount of "preferably not".
#
# - the imported excel sheet should be checked on whether the availability is indicated
#   with "Yes", "Preferably Not", "No"
#########################################


####### Main function to generate schedule #######
def generate_schedule(dataframe, suffix = None):

    if suffix is not None:
        suffix = str(suffix)
    elif suffix is None:
        suffix = str(input("Please specify a suffix for the schedule: "))

    df = dataframe
    num_shopkeepers = len(df.columns[3:])

    # specify the date format explicitly
    df['Date'] = pd.to_datetime(df['Date'])

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
    most_common_solutions_with_weeks = find_most_consistent_solutions(solutions_per_week, team, num_shopkeepers)

    # process the list of solutions (see function)
    final_processed_solutions = process_solutions(most_common_solutions_with_weeks)

    # now that you found solutions that fit best (most consistent),
    # for each solution come up with a schedule that takes care of the remaining weeks
    filled_solutions, unassigned_slots = fill_remaining_weeks(final_processed_solutions, unique_weeks, team)

    # prompt user to choose between solutions if there are multiple best solutions
    best_solution, remind_list, remind_to_add_manually = pick_solution(filled_solutions, unassigned_slots)

    # write the schedule and warn one more time if necessary.
    df = dict_to_dataframe(best_solution, df)

    cd = os.getcwd()
    output_path = os.path.join(cd, 'output')
    os.mkdir(output_path)
    output_file = f'schedule_{suffix}.xlsx'
    df.to_excel(os.path.join(output_path, output_file))
    print(f'Final schedule created and written to "{output_path}\\{output_file}"')

    if remind_to_add_manually:
        RED_TEXT = "\033[91m"
        RESET_TEXT = "\033[0m"
        print(f"{RED_TEXT}REMINDER TO ADD THE FOLLOWING PEOPLE MANUALLY{RESET_TEXT}")
        print(remind_list)

    return df

####### sub-functions #######

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
                        availability = df[(df['Day'] == day) & (df['Week'] == week) & (df['Time'] == time)][person].values
                        team[person][f'{week}_{day}_{time}'] = availability[0] if availability.size > 0 else 'No'
    return team

def create_solutions_per_week(team, unique_weeks, unique_days, timeslots):
    solutions_per_week = {}

    for week in unique_weeks[:-1]:
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

        # Set up the CSP problem
        problem = Problem()

        # add variables and related domains only for non-empty domains
        for day_time_key, domain in domains.items():
            if len(domain) > 0:
                problem.addVariable(variable=day_time_key, domain=domain)

        # get solutions
        solutions = problem.getSolutions()

        # store solutions per week
        solutions_per_week[week] = []

        # HIER NOG NAAR KIJKEN OF DIT UBERHAUPT IETS DOET OF REDUNDANT IS
        for solution in solutions:
            # check if all team members are in the solution
            if all(name in solution.values() for name in team.keys()):
                solutions_per_week[week].append(solution)

    return solutions_per_week

def find_most_consistent_solutions(solutions_per_week, team, num_shopkeepers):
    # create a list to gather all unique solutions
    all_solutions = []

    # gather all solutions from solutions_per_week
    for week, solutions in solutions_per_week.items():
        all_solutions.extend(solutions)

    # count occurrences of each unique solution
    solution_counts = Counter(tuple(sorted(solution.items())) for solution in all_solutions)

    # find the maximum count
    max_count = max(solution_counts.values())

    # filter solutions that have the maximum count and convert tuples back to dicts
    most_common_solutions = [
        dict(solution) for solution, count in solution_counts.items() if count == max_count
    ]

    # the following basically checks if any of the solutions include a timeslot that is not preferred by the employee
    solutions_preference = filter_preferred_solutions(most_common_solutions, solutions_per_week, team, num_shopkeepers)

    most_common_solutions_with_weeks = consolidate_solution_weeks(solutions_preference)
    # count occurrences and store weeks for each unique solution
    solution_counts = Counter()
    solution_weeks = defaultdict(list)

    for week, solution in solutions_preference:
        # convert the solution to a tuple for comparison and sorting
        solution_tuple = tuple(sorted(solution.items()))
        # increment count of the solution
        solution_counts[solution_tuple] += 1
        # track in which week this solution occurs
        solution_weeks[solution_tuple].append(week)

    # find the maximum count
    max_count = max(solution_counts.values())

    # filter solutions that have the maximum count and retrieve corresponding weeks
    most_common_solutions_with_weeks = [
        {'solution': dict(solution), 'weeks': solution_weeks[solution]}
        for solution, count in solution_counts.items() if count == max_count
    ]

    return most_common_solutions_with_weeks


def filter_preferred_solutions(most_common_solutions, solutions_per_week, team, num_shopkeepers):
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

def consolidate_solution_weeks(solutions_preference):
    solution_counts, solution_weeks = Counter(), defaultdict(list)
    for week, solution in solutions_preference:
        sol_tuple = tuple(sorted(solution.items()))
        solution_counts[sol_tuple] += 1
        solution_weeks[sol_tuple].append(week)
    max_count = max(solution_counts.values())

    most_common_solutions_with_weeks = [
        {'solution': dict(sol), 'weeks': solution_weeks[sol]} for sol, count in solution_counts.items() if count == max_count]
    return most_common_solutions_with_weeks


def process_solutions(solutions):
    processed_solutions = []
    seen_solutions = set()  # a set to track unique (solution, weeks) pairs

    for solution_with_weeks in solutions:
        solution = solution_with_weeks['solution']
        weeks = solution_with_weeks['weeks']  # extract weeks information
        appearance_count = defaultdict(int)

        # count appearances for each person
        for person in solution.values():
            appearance_count[person] += 1

        # sort people by the number of appearances (least to most)
        sorted_people = sorted(appearance_count.items(), key=lambda x: x[1])

        unique_schedule = {}
        assigned_days = set()  # track assigned days to maximize unique days

        # attempt to assign time slots based on sorted appearances
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

def fill_remaining_weeks(final_processed_solutions, unique_weeks, team):
    list_of_final_solutions = {}
    filled_solutions = []
    iter = 0
    least_changes = float('inf')
    unassigned_slots = None

    for entry in final_processed_solutions:
        solution = entry['solution']  # access the 'solution' dictionary
        weeks = entry['weeks']  # access the 'weeks' value
        iter += 1
        number_of_changes = 0
        solution_n = f"solution{iter}"
        person_schedule = defaultdict(dict)
        current_unassigned_slots = defaultdict(dict)

        # basically what this code does is that it tries to find the solution with the most consistent
        # schedule over the weeks. It does this by checking how many changes per person per week have to be made
        for week in unique_weeks:
            for day_time_key, person in solution.items():
                week_day_time = f"{week}_{day_time_key}"  # construct the correct key to match the `team`

                if week in weeks:
                    # just assign the key corresponding to the person value as the value in the week key
                    person_schedule[person][week] = (day_time_key)

                else:
                    # check if person can still be assigned to same timeslot, if not, select timeslots that are available
                    # for that person and request input of user which timeslot they want to pick for this user

                    # Check availability in team dictionary
                    if team[person].get(week_day_time) != 'No':
                        person_schedule[person][week] = (day_time_key)
                        # assign to same timeslot
                    else:
                        person_schedule[person][week] = 'NA'
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
        # store the solution and unassigned slots in the list of final solutions
        list_of_final_solutions[solution_n] = (person_schedule, number_of_changes, current_unassigned_slots)

        # check for the best solution with the least number of changes
        if number_of_changes < least_changes:
            least_changes = number_of_changes
            filled_solutions = [person_schedule]  # store the current best schedule
            unassigned_slots = [current_unassigned_slots]  # store the corresponding unassigned available slots
        elif number_of_changes == least_changes:
            filled_solutions.append(
                person_schedule)  # append the actual schedule if it has the same number of changes
            unassigned_slots.append(current_unassigned_slots)

    return filled_solutions, unassigned_slots

def pick_solution(filled_solutions, unassigned_slots):
    if len(filled_solutions) > 1:
        print("Multiple solutions have the least changes. Please choose one:")

        # pretty print each solution before asking for user input
        for idx, schedule in enumerate(filled_solutions, 1):
            print(f"\nOption {idx}:")
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
            if best_solution[person][week] == 'NA':
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
    # create a mapping from week to date using the original DataFrame
    week_to_date = dict(zip(original_df['Week'], original_df['Date']))

    # empty list to store variables
    entries = []

    for person, weeks in schedule_dict.items():
        for week, timeslot in weeks.items():
            date = week_to_date.get(week, 'NA')  # get the corresponding date or NA

            # split the timeslot into day and time if it's not NA
            if timeslot != 'NA':
                day, time = timeslot.split('_')
            else:
                day, time = 'NA', 'NA'  # handle 'NA' case

            entries.append({
                'Person': person,
                'Week': week,
                'Date': date,
                'Day': day,
                'Time': time
            })

    df = pd.DataFrame(entries)
    return df


