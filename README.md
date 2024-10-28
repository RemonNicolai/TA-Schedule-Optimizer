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
