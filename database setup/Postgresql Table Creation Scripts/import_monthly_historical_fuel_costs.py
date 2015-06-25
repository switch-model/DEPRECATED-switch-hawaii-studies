import psycopg2
import csv

# Import historical monthly plant-level fuel costs from a spreadsheet provided by 
# Karl Jandoc and Michael Roberts 2015-06-08. 
# This spreadsheet was originally missing some rows in 2000-2003, but they were 
# filled in using linear interpolation before saving the .csv file.

with open(