import sys
import os
import pandas as pd
import numpy as np
import itertools
import time
from constraint import *
from collections import defaultdict

pd.set_option('future.no_silent_downcasting', True)

'''
    These scripts can be used or adapted to create a schedule for the Statistics Practicals for the
    University of Groningen. 

    The problem of making a schedule is an instance of a Constraint Satisfaction
    Problem (CSP). Please be aware that computationally these problems can require a lot computing power
    and memory. It is therefore important to minimize the search space as much as possible. 
    For instance, say there are 10 groups (variables) that need assigning to, and on average 3 individuals
    (domain) are available for a group, then the search space is 3^10 = 59049. As the variables and domain
    increase, the search space grows exponentially. For example, if the variables increase, the problem 
    space becomes 3^11 = 177147. If the domain increases, the search space becomes 4^10 = 1048576, as you
    can see, it's especially important to reduce the average domain size.

    Thus, if there are A LOT of groups (say >14) and/or A LOT of TAs with one weekly 
    shift (let's say >2; INCREASING NUMBERS OF TAs ARE ESPECIALLY HARD FOR THE CSP),
    it is recommended to either look whether that many groups are needed (discuss with coordinator),
    or think about ways the average domain size of the CSP can be reduced. You could for example set
    some "Preferably Not" to "No" for some slots that are filled plenty already for people who
    have plenty of other availability already. You could also, for example, treat persons with similar
    availability as one person by collapsing their availability and later on splitting them apart again.

    See, e.g., functions in *schedule_maker_practical.py*
    My personal experience is that 12/13 groups with TAs who are available for on average 5 groups works perfectly fine

    ##### DATAFRAME PREPROCESSING #####

    Script needs a specific structure as input, the script won't work without this structure. Thus, some preprocessing
    is required. See the example dataframe for the requirements.

'''

####### Main function to generate schedule #######
def generate_schedule(dataframe, suffix = None, required_columns = int(9),
                      min_availability_ratio = float(0.5),consecutive_ratio = float(0.4)):

    if consecutive_ratio <= 0.0 or consecutive_ratio >= 1.0:
        sys.exit("consecutive_ratio must be between 0.0 and 1.0")
    if min_availability_ratio <= 0.0 or min_availability_ratio >= 1.0:
        sys.exit("min_availability_ratio must be between 0.0 and 1.0")

    if suffix is None:
        suffix = str(input("Please specify a suffix for the schedule: "))

    start = time.time()
    df = dataframe

    """
    # merge the availability of some TAs in case there are many TAs (e.g. 9 or more)
    # In case of less TAs, typically the decr_PrefNot should already do the trick.
    """

    columns_to_compare = df.columns[5:]
    n_TAs = len(columns_to_compare)
    merged = False
    if n_TAs > 9:  # only do this when number of TAs is larger than 9, otherwise not necessary
        df, merged = merge_TA_availability(df, required_columns=required_columns)

    """ 
    # decrease the number of "preferably not" if overall availability is high
    # # Set minimal ratio of availability to total amount of groups for TA.
    # Lower settings significantly reduce the time to solve the problem
    # but may result in finding suboptimal or no results (default = 0.4).
    """
    df = decr_PrefNot(df,min_availability_ratio=min_availability_ratio)

    """ 
    # if the number of groups is larger than 16 (arbitrary cut-off), find the first solution. Typically this solution is
      already near perfect.
    """

    n_groups = df.shape[0]
    if n_groups > 16:
        all_solutions = False
    else:
        all_solutions = True

    # check whether columns of dataframe have the correct names and structure
    example_columns = pd.DataFrame(columns=['Day','Time', 'Group', 'Location', 'Room']).columns
    columns_first5 = df.columns[:5]
    common_column = example_columns.intersection(columns_first5)
    if len(common_column) < 5:
        sys.exit("First 5 columns do not match: 'Day','Time', 'Group', 'Location', 'Room'")

    # extract important information from groups
    incompatible_groups = find_incompatible_combinations(df)
    consecutive_groups = find_consecutive_combinations(df)
    consecutive_diff_rooms = find_consecutive_improb(df)
    incompatible_combinations = incompatible_groups + consecutive_diff_rooms


    # create a team availability dictionary for group (which can link back to time, day, and location)
    team = {}
    n_TAs_plus1shift = 0

    # loop over employees
    for person_n in df.columns[5:]:  # make sure that columns from column 6 onwards are the names
        if "_" not in person_n:
            sys.exit("number of shifts not indicated by suffix '_n', where 'n' is number of shifts")
        n_shifts = person_n.split('_')[1]
        if not float(n_shifts).is_integer():
            sys.exit("number of shifts not indicated by suffix '_n', where 'n' is number of shifts")
        n_shifts = int(n_shifts)
        if n_shifts > 1:
            n_TAs_plus1shift += 1


        person = person_n.split('_')[0]
        team[person] = {}
        team[person]['n_shifts'] = n_shifts
        team[person]['availability'] = {}
        for group in df["Group"]:
            # store availability
            availability = df[(df['Group'] == group)][person_n].values
            if len(availability) > 0:
                team[person]['availability'][group] = availability[0]
            else:
                team[person]['availability'][group] = 'No'  # in case of NA


    total_shifts = sum(person_info['n_shifts'] for person_info in team.values())
    n_groups = df.shape[0]
    if total_shifts != n_groups:
        sys.exit("total amount of shifts over all TAs not equal to number of groups, which is a requirement for this script to run. Check your dataframe")

    # CSP setup
    domains = {}
    for group in df["Group"]:
        domain = []
        for person in team.keys():
            availability = team[person]['availability'].get(group, 'No') # just a sanity check to default to 'No'
            if availability != 'No':
                domain.append(person)
        domains[group] = domain

    # set up the CSP problem
    problem = Problem(OptimizedBacktrackingSolver())

    domains = sorted_data = dict(sorted(domains.items(), key=lambda x: len(x[1])))
    # add the variables and the related domains

    for group in domains.keys():
        problem.addVariable(variable=group, domain=domains[group])

    # add the custom constraints
    group_list = list(domains.keys())

    problem.addConstraint(FunctionConstraint(lambda *values:
                                             consecutive_constraint(
                                                 *values,
                                                 list_of_groups=group_list,
                                                 diff_rooms_consec=incompatible_combinations, # consecutive_diff_rooms
                                                 consecutive_groups= consecutive_groups,
                                                 plus1shift= n_TAs_plus1shift,
                                                 consecutive_ratio=consecutive_ratio,
                                                 team_dict=team,
                                                 all_solutions=all_solutions)
                                             ), group_list)


    # find solutions
    if all_solutions:
        print("Finding solutions, please wait")
        solutions = problem.getSolutions()
    if not all_solutions:
        print("Finding solution, please wait")
        solutions = problem.getSolution()

    if solutions == None:
        sys.exit("No solutions found, check your dataframe!")
    elif isinstance(solutions, dict):
        # immediately return dataframe
        solution = solutions
        df = dict_to_dataframe(solution, df)
        df.to_excel(f'schedule_{suffix}.xlsx')
        cd = os.getcwd()
        print(f'Final schedule created and written to "{cd}\\schedule_{suffix}.xlsx"')
        print('It took {0:0.1f} seconds'.format(time.time() - start))
        return df

    # the following basically checks if any of the solutions include a timeslot that is not preferred by the employee
    solutions_preference = {}
    for solution in solutions:
        prefNot_counter = 0
        for group, person in solution.items():
                if team[person]['availability'].get(group) == 'Preferably Not':  # might want to make this a variable/constant
                    # delete the availability from solution
                    prefNot_counter += 1
        solution['preferably_not_count'] = prefNot_counter


    # schrijf mogelijke combinaties uit van direct op een na volgende groepen
    for solution in solutions:
        consecutive_count = 0
        for shift1, shift2 in consecutive_groups:
            # check if both consecutive shifts are assigned to the same person in the solution
            if solution.get(shift1) == solution.get(shift2):
                consecutive_count += 1

        # Add the consecutive shift count to the solution
        solution['consecutive_shift_count'] = consecutive_count

    max_count = max(sol['consecutive_shift_count'] for sol in solutions)
    solutions_with_most_consecutive = [sol for sol in solutions if sol['consecutive_shift_count'] == max_count]

    best_solution = min(solutions_with_most_consecutive, key=lambda sol: sol['preferably_not_count'])

    df = dict_to_dataframe(best_solution, df)

    if merged:
        df.loc[df["TA"].str.contains("-"), "Warning"] = "don't forget to split TAs again"

    df.to_excel(f'schedule_{suffix}.xlsx')

    cd = os.getcwd()
    print(f'Final schedule created and written to "{cd}\\schedule_{suffix}.xlsx"')
    print('It took {0:0.1f} seconds'.format(time.time() - start))
    return df

####### sub-functions #######

# create overview of incompatible groups
def find_incompatible_combinations(dataframe):
    incompatible_groups = []

    # Iterate over each group
    for day in pd.unique(dataframe["Day"]):
        # Check for its incompatible groups
        for time in pd.unique(dataframe["Time"]):
            same_day_time = dataframe[(dataframe["Day"] == day) & (dataframe["Time"] == time)]

            # Collect all groups that share the same day and time
            if len(same_day_time) > 1:  # If more than one group shares the same time
                groups = same_day_time["Group"].tolist()
                # split lists of 3 in lists of 2
                if len(groups) > 2:
                    groups = list(itertools.combinations(groups, 2))
                    for combination in groups:
                        combination = sorted(combination)
                        incompatible_groups.append(combination)
                else:
                    incompatible_groups.append(groups)

    return incompatible_groups

# find pairs of consecutive shifts in same room
def find_consecutive_combinations(dataframe):
    consecutive_groups = []
    df_copy = dataframe.copy()

    # split Time in begin time and end time
    df_copy[["s_time", "e_time"]] = df_copy["Time"].str.split('-',expand=True)

    # Iterate over each group
    for room in pd.unique(df_copy["Room"]):
        for day in pd.unique(df_copy["Day"]):
        # Check whether there are consecutive groups
            same_room_day = df_copy[(df_copy["Room"] == room) & (df_copy["Day"] == day)]
            # Loop over DataFrame and find matching start and end times
            for i, row1 in same_room_day.iterrows():
                for j, row2 in same_room_day.iterrows():
                    if i != j:  # Ensure you're not comparing the same row
                        if row1['e_time'] == row2['s_time']:
                            consecutive_groups.append(sorted([row1['Group'], row2['Group']]))

    return consecutive_groups

# find pairs of consecutive shifts in different room
def find_consecutive_improb(dataframe):
    consecutive_groups = []

    df_copy = dataframe.copy()

    # split Time in begin time and end time
    df_copy[["s_time", "e_time"]] = df_copy["Time"].str.split('-', expand=True)
    # Iterate over each group
    for day in pd.unique(df_copy["Day"]):
    # Check whether there are consecutive groups in DIFFERENT rooms
        same_day = df_copy[(df_copy["Day"] == day)]
        # Loop over DataFrame and find matching start and end times
        for i, row1 in same_day.iterrows():
            for j, row2 in same_day.iterrows():
                if i != j:  # Ensure you're not comparing the same row
                    if row1['e_time'] == row2['s_time'] and row1['Room'] != row2['Room']:
                        consecutive_groups.append(sorted([row1['Group'], row2['Group']])) # ensure it's sorted for comparison later

    return consecutive_groups

# NO LONGER USED. create constraint that ignores solutions that include incompatible groups
def combination_constraint(*values, list_of_groups, incompatible_groups):

    solution = dict(list(zip(list_of_groups, values)))

    compatible = True
    for combination in incompatible_groups:
        person_list = []
        for group in combination:
            person = solution[group]
            person_list.append(person)
        # check the number of unique persons
        unique_persons = list(set(person_list))

        # if the number of unique persons is less than the number of groups, there is a conflict
        if len(unique_persons) != len(combination):
            compatible = False
            break

    return compatible


# NO LONGER USED: Constraint to ensure that each person is assigned exactly the number of shifts they should work.
def person_shift_constraint(*values, list_of_groups, team_dict):

    solution = list(zip(list_of_groups,values))

    # Count how many shifts each person has been assigned
    shift_counter = {person: 0 for person in team_dict}
    for group, person in solution:
        if person in shift_counter:
            shift_counter[person] += 1

    # Check if the assigned shifts match the required number for each person
    return all(shift_counter[person] == team_dict[person]['n_shifts'] for person in team_dict)

# add constraint where if a solution has someone placed in two simultaneous shifts, the location shouldn't be different
# now also checks for incompatible groups in one go, and ensures that there's a minimum number of consecutive shifts
def consecutive_constraint(*values, list_of_groups, diff_rooms_consec, consecutive_groups, plus1shift, consecutive_ratio = float(),team_dict, all_solutions):
    consecutive_count = int(0)

    solution = defaultdict(list)
    for value, group in zip(values, list_of_groups):
        solution[value].append(group)
    solution = dict(solution)

    compatible = True
    for person, groups in solution.items():
        if team_dict[person]['n_shifts'] != len(groups):
            compatible = False
            return compatible

    for groups in solution.values():
        if len(groups) == 1:
            continue

        elif len(groups) == 2:
            groups = sorted(groups)
            if groups in diff_rooms_consec:
                compatible = False
                return compatible
            # count number of consecutive groups
            if not all_solutions:
                if groups in consecutive_groups:
                    consecutive_count += 1

        elif len(groups) > 2:
            groups = list(itertools.combinations(groups, 2))
            for combination in groups:
                combination = sorted(combination) # otherwise doesn't work properly, not sure why since itertools.comb should do this automatically
                if combination in diff_rooms_consec:
                    compatible = False
                    return compatible
                # count number of consecutive groups
                if not all_solutions:
                    if combination in consecutive_groups:
                        consecutive_count += 1

    if not all_solutions:
        consecutive_ratio_sol = consecutive_count / plus1shift
        if consecutive_ratio_sol <= consecutive_ratio:
            compatible = False

    return compatible

# create dataframe from final dictionary
def dict_to_dataframe(schedule_dict, original_df):
    # select first 5 columns from the original DataFrame
    df_copy = original_df.iloc[:, :5].copy()
    # Apply the schedule_dict to create the "TA" column based on the "Group" column in the original DataFrame
    df_copy["TA"] = df_copy["Group"].map(schedule_dict).fillna('No')
    return df_copy

##### REDUCE DIMENSIONS FUNCTIONS ######

# function to determine combined availability
def decr_PrefNot(df, min_availability_ratio = float(0.4)):
    columns_to_compare = df.columns[5:]
    n_groups = df.shape[0]

    availability = {}
    for column in columns_to_compare:
        count = pd.Series(df[column]).value_counts().to_frame()
        available_count = count.loc["Yes", "count"]
        availability[column] = available_count


    PrefNot_before = df.apply(lambda col: pd.Series(col).value_counts()).T
    PrefNot_before = int(PrefNot_before["Preferably Not"].sum())

    dfT= df.T
    for i, row in df.iloc[:,5:].iterrows():

        pn_count = (dfT.loc[:,i] == 'Preferably Not').sum()
        y_count = (dfT.loc[:,i] == 'Yes').sum()
        n_count = (dfT.loc[:, i] == 'No').sum()
        total = len(df.columns[5:])

        if y_count + pn_count >= 3 and y_count >=2:
            dfT_pn = dfT.loc[dfT[i] == 'Preferably Not']

            if dfT_pn.shape[0] >= 1:
                for j, personT in dfT_pn.iterrows():
                    if availability[j]/n_groups > min_availability_ratio and (y_count + pn_count >= 3 and y_count >=2):
                        #print(f"{j}'s Preferably Not set to No for group {df.iloc[i,2]}")
                        df.at[i, j] = 'No'

                        pn_count = (dfT.loc[:, i] == 'Preferably Not').sum()
                        y_count = (dfT.loc[:, i] == 'Yes').sum()
                        n_count = (dfT.loc[:, i] == 'No').sum()

    PrefNot_after = df.apply(lambda col: pd.Series(col).value_counts()).T
    PrefNot_after = int(PrefNot_after["Preferably Not"].sum())
    print(f"Preferably Not count decreased from {PrefNot_before} to {PrefNot_after}")

    return df


def merge_TA_availability(df, required_columns=int(7)):
    columns_to_compare = df.columns[5:]
    n_domains = len(columns_to_compare)

    RED_TEXT = "\033[91m"
    RESET_TEXT = "\033[0m"

    # this while loop prompts the user to pick a combination until the domains have reached size n (default == 7)
    while n_domains > required_columns:
        similarity_scores = calculate_similarity_scores(df, columns_to_compare)
        similarity_scores = sorted(similarity_scores.items(), key=lambda item: item[1], reverse=True)
        top_ten = similarity_scores[:10]

        # select a number between 1 and total number of timeslots
        time.sleep(2)
        for index, combination in enumerate(top_ten, start=1):
            print(f"{index}. {combination[0]} (Similarity: {combination[1] * 100:.2f}%)")

        while True:
            try:
                print(f"{RED_TEXT}To make the script run more quickly, some of the TAs have to be merged.{RESET_TEXT}")
                choice = int(input(f"Please pick a combination #number (1-{len(top_ten)}): "))

                if 1 <= choice <= len(top_ten):  # check if response is out of bounds
                    selected_timeslot = top_ten[choice - 1][0]
                    time.sleep(1)
                    print(f"You selected: {selected_timeslot}")
                    col1 = selected_timeslot[0]  # dit nog aanpassen
                    name1, shifts1 = col1.split('_')
                    col2 = selected_timeslot[1]  # dit nog aanpassen
                    name2, shifts2 = col2.split('_')
                    n_shifts = int(shifts1) + int(shifts2)
                    column_name = f'{name1}-{name2}_{n_shifts}'

                    # apply the function to create the new column
                    df[column_name] = df.apply(lambda row: combine_availability(row, col1, col2), axis=1)
                    # add a check whether there is no "yes" left in this column, if this is the case, delete the column again
                    # and don't delete the other two columns, and prompt the user to pick a different combination
                    if df[df[column_name] == "Yes"].shape[0] == 0:
                        print(f"{RED_TEXT}Merged TAs ({name1}-{name2}) have no combined 'Yes'-availability. Please pick another combination.{RESET_TEXT}")
                        df = df.drop([column_name], axis=1)
                        time.sleep(1)
                    else:
                        df = df.drop([col1, col2], axis=1)
                        break  # Exit the loop after processing

                else:  # response is out of bounds
                    time.sleep(1)
                    print(f"Invalid input. Please choose a #number between 1 and {len(top_ten)}.")
            except ValueError:  # response is not an integer
                time.sleep(1)
                print("Invalid input. Please enter a #number.")

        columns_to_compare = df.columns[5:]
        n_domains = len(columns_to_compare)
    return df, True

def combine_availability(row, col1, col2):
    # cccess the values from the specified columns in the row
    value1 = row[col1]
    value2 = row[col2]

    if value1 == 'No' or value2 == 'No':
        return 'No'
    elif value1 == 'Preferably Not' or value2 == 'Preferably Not':
        return 'Preferably Not'
    elif value1 == 'Yes' or value2 == 'Yes':
        return 'Yes'
    else:
        return 'No'

def calculate_similarity_scores(dataframe, columns):
    binary_df = dataframe[columns].copy()

    # preprocess dataframe
    binary_df = binary_df.replace({'No': 0, np.nan: 0, 'Preferably Not': 1, 'Yes': 1}).astype(int)

    # initialize a dictionary to store similarity scores
    similarity_scores = {}

    for col1, col2 in itertools.combinations(columns, 2):
        # calculate the percentage of matching values
        if '-' in col1 or '-' in col2:
            continue
        else:
            matches = (binary_df[col1] == binary_df[col2]).sum()  # count matches
            total_rows = len(binary_df)  # total number of rows
            similarity_percentage = matches / total_rows  # calculate percentage
            similarity_scores[(col1, col2)] = similarity_percentage

    return similarity_scores