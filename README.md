# TA-Schedule-Optimizer
Python-based scheduler that automatically generates optimal weekly schedules for Teaching Assistants (TAs; employees), factoring in availability, shift constraints, and preference prioritization. This tool uses constraint satisfaction techniques to assign shifts fairly and efficiently while avoiding conflicts. Originally created for the Statistics and Psychometrics department of the BSS Faculty at the University of Groningen

## Constraint Satisfaction Problem
The problem of making a schedule is an instance of a Constraint Satisfaction
Problem (CSP). Please be aware that computationally these problems can require a lot of computing power
and memory. It is therefore important to minimize the search space as much as possible. 
For instance, say there are 10 groups (variables) that need assigning to, and on average 3 individuals
(domain) are available for a group, then the search space is 3^10 = 59049. As the variables and domain
increase, the search space grows exponentially. For example, if the variables increase, the problem 
space becomes 3^11 = 177147. If the domain increases, the search space becomes 4^10 = 1048576, as you
can see, it's especially important to reduce the average domain size.

Dataframes that look like the "short"-example should take approximately 10-20 minutes to run.
Dataframes that look like the "long"-example should take approximately 80-120 minutes to run.

In typical situations the script should be finished running within 10 minutes (e.g. 13 groups, 9 TAs),
however, when the number of groups and especially TAs increases, say 18 groups and 11 TAs, the duration
increases significantly (2h+). 
    
If the duration takes more than 4h, the problem's dimensionality is likely too large. Consider whether
this many groups and TAs are needed. ;)

## To Do's
- Implement an OOP framework to improve readability.
- Finalize 'Differing Weekly Availability' script

## Instructions
To make the schedule maker script work, do what is listed below.

### Dataframe Requirements:
An example can be found in the 'example' folder.

1. Ensure that TAs can answer with "Yes", "Preferably Not", and "No". The differentiation between "Yes" and "Preferably Not" is very important. 
2. Use validation lists so that TAs can only answer with "Yes", "Preferably Not" and "No", so that no problems occur with these strings (e.g. typos and missing capital letters).
3. Double check whether the answer options are limited to "Yes", "Preferably Not" and "No".
4. Use a suffix that indicates the number of shifts a TA has in their name column. If Bob has two shifts, the column name should be "Bob_2"
5. Ensure that the total number of shifts is equal to the number of groups.
6. Except for the name columns, keep the names and structure of the first 5 columns (Day-Time-Group-Location-Room) exactly as the example. The script expects the columns from column 6 onwards to be the TAs their names and corresponding availability
7. Make sure the time is indicated by a start time and end time (e.g. 09:00-11:00).

### Required packages:
- pandas
- numpy
- python-constraint
