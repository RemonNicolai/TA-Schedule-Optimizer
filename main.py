# import functions to create schedule, and import other packages
from schedule_maker_practical import *

'''
    These scripts can be used or adapted to create a schedule for the Statistics Practicals for the
    University of Groningen. 
    
    ##### DATAFRAME PREPROCESSING #####
    Script needs a specific structure as input, the script won't work without this structure. Thus, some preprocessing
    is required. See the example dataframe for the requirements.
    
'''

# set working directory --> this is where the schedule is outputted
# os.chdir('YOURPATH')

# define where Excel file can be found
path_excelfile = "examples\\example_dataframe_long.xlsx" # make sure to use '\\'

# read file
df = pd.read_excel(path_excelfile)

# generate schedule
df = generate_schedule(dataframe=df, min_availability_ratio = 0.3)
