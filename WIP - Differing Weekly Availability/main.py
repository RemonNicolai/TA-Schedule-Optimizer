# import functions to create schedule, and import other packages
from schedule_maker import *

# define where Excel file can be found
path_excelfile = "examples\\example_dataframe.xlsx"
df = pd.read_excel(path_excelfile)

# generate schedule
df = generate_schedule(df)