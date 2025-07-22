#!/usr/bin/env python3
import argparse
import io
import json
import os
import re
import sys
import gspread
import select
import time
import traceback
from datetime import datetime, timedelta
from enum import IntEnum
from pathlib import Path
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from tdvutil.argparse import CheckFile

import fcntl

# set sys.stdin non-blocking
orig_fl = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
fcntl.fcntl(sys.stdin, fcntl.F_SETFL, orig_fl | os.O_NONBLOCK)

# import dateparser

# NOTE: You will need to set up a file with your google cloud credentials
# as noted in the documentation for the "gspread" module

# event queue - this is to keep from making too many API calls per minute
rowqueue = [ ]

# Starting row
row = 17400

# Track new rows
newrowcount = 100
newrowused = 100
lastrow = 0

# Arguement Parsing
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search the onglog via discord",
    )

    parser.add_argument(
        "--gsheets-credentials-file",
        type=Path,
        default=None,
        action=CheckFile(must_exist=True),
        help="file with discord credentials"
    )

    parser.add_argument(
        "--gsheets-id",
        default=None,
        help="file with discord credentials"
    )


    parsed_args = parser.parse_args()

    if parsed_args.gsheets_credentials_file is None:
        parsed_args.gsheets_credentials_file = Path(
            __file__).parent / "gsheets_credentials.json"

    return parsed_args

def receiveline(line):
    global row
    global rowqueue

    # Valid date pattern
    validdate = re.compile("^20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]")
    eventstring = re.compile(" ===")
    hypeend = re.compile("=== HYPE TRAIN END")
    hypelevel = re.compile(r'level=(\d*)')
    streamstart = re.compile("=== ONLINE")
    streamend = re.compile("=== OFFLINE")


    items = line.split("\t")
    if len(items) > 1 and validdate.match(items[0]):
        if not eventstring.match(items[1]):
            print(f'Adding Entry: {line}')
            # Make sure its the right length
            if len(items)>7:
                items[7] = ''
            else:
                while len(items)<8:
                    items.append('')
            rowqueue.append(items[0:8])
    elif lastrow>0 and hypeend.search(line):
        hypelevel = hypelevel.search(line)
        print(f'Hype: {hypelevel.group(1)}')
        if hypelevel.group(1):
            level = int(hypelevel.group(1)) -1
            # print(f'Rowqueue {len(rowqueue)-1} Items {len(rowqueue[len(rowqueue)-1])}')
            # rowqueue[lastrow][7]= f'Hypetrain Completed Level {level}'
            try:
                worksheet.update([[ f'Hypetrain Completed Level {level}']],f'H{lastrow}')
            except:
                print(f'Failed to update H{lastrow} for Hypetrain')
    elif streamstart.search(line):
        items = line.split(" === ")
        print(f'Stream Start: {items[0]}')
        rowqueue.append([items[0],"","","STREAM START","","","",""])
    elif streamend.search(line):
        items = line.split(" === ")
        print(f'Stream End: {items[0]}')
        rowqueue.append([items[0],"","","STREAM END","","","",""])
    else:
        print(f'Did not understand: {line}')
    
def findnextrow():
    global worksheet
    global row
    global lastrow
    global rowqueue
    global newrowcount
    global newrowused

    validdate = re.compile(r'^(\d+)-(\d+)-(\d+)\s(\d+):(\d+):(\d+)')

    count = 101
    startrow = row - 100
    blankfound = False
    while not blankfound:
        endrow = row + 100
        print(f'Looking for last row between {startrow} and {endrow}')
        count = 0
        rowpos = startrow
        data = worksheet.get(f'A{startrow}:G{endrow}', pad_values=True)
        for datarow in data:
            newrow = []
            # Some reason spaces get turned into \xa0.
            for cell in datarow:
                cell = re.sub(r'\s',' ',cell)
                newrow.append(cell)
            count += 1
            rowpos += 1
            # Check to see if row is blank
            #print(f'{row} {newrow[0]}')
            if newrow[0] != "":
                if rowpos > row:
                    row += 1
                # Worse we need to normalize the date string for leading zeros to match input data
                dateraw = validdate.match(newrow[0])
                if dateraw and len(rowqueue)>0:
                    datenew=[]
                    for i in range(6):
                        value = dateraw.group(i+1)
                        if int(value)<10 and len(value) == 1:
                            value=f'0{value}'
                        datenew.append(value)
                    datestring=f'{datenew[0]}-{datenew[1]}-{datenew[2]} {datenew[3]}:{datenew[4]}:{datenew[5]}'
                    #print(f'date: {int(datenew[3])} {datenew[3][0]} {datestring}')

                    # Display the rows that were found
                    #print(f' In Sheet: {row} {newrow}')

                    # Use the date string and C/D column to eliminate duplicates
                    newrowqueue = []
                    #print(f'Checking against {newrow}')
                    for r in range(0,len(rowqueue)):
                        #print(f' Datestring: {datestring} rowqueue: {rowqueue[r][0]}')
                        if datestring == rowqueue[r][0] and (newrow[3] == "STREAM START" or (newrow[2] == rowqueue[r][2] and newrow[3] == rowqueue[r][3] and newrow[4] == rowqueue[r][4] and newrow[5] == rowqueue[r][5])):
                            print(f'  Already in sheet: ${rowqueue[r]}')
                        else:
                            newrowqueue.append(rowqueue[r])
                    rowqueue = newrowqueue
        if row < endrow:    
            print(f'Found last row {row}')
            blankfound = True
        startrow = row - 5

    # Find the last row not likely to have anything in the comment field
    if len(rowqueue)>0:
        for r in range(0,len(rowqueue)):
            if rowqueue[r][5]:
                dollarvalue = float(re.sub(r'\$','',rowqueue[r][5]))
                if dollarvalue < 24.99:
                    lastrow = row + r

    print(f'Next blank row: {row} New rows to add: {len(rowqueue)}')

    # Next Make sure there are enough new rows, if not, create more new lines
    newrowused += len(rowqueue)
    if newrowused > newrowcount:
        newrowused-=newrowcount
        try:
            worksheet.add_rows(newrowcount+newrowused)
            print(f'Added {newrowused+newrowcount} lines to sheet')
            newrowused=0
        except:
            print("Tried to add lines to the sheet and that failed - new lines might not appear")
            newrowused+=newrowcount  # Restore true status

    print(f'To Add:')
    for r in range(0,len(rowqueue)):
        print(f'{rowqueue[r]}')


def main() -> int:
    global row
    global rowqueue
    global worksheet
    global lastrow

    args = parse_args()

    gc = gspread.service_account(filename=args.gsheets_credentials_file)
    print(gc)

    if args.gsheets_id is None:
        ONG_BUMP_SPREADSHEET_ID = "19zRJ-EIBsJr37l8HViPpGjEJvotfzzkFIKeyxLz6WYg"
    else:
        ONG_BUMP_SPREADSHEET_ID = args.gsheets_id

    ONG_BUMP_SPREADSHEET_URL = f"https://docs.google.com/spreadsheets/d/{ONG_BUMP_SPREADSHEET_ID}"
 
    print(f"Using Sheet: {ONG_BUMP_SPREADSHEET_URL}")
    # gsheet = gc.open("Test Copy of JonathanOng Bump Log")
    gsheet = gc.open_by_key(ONG_BUMP_SPREADSHEET_ID)
    worksheet= gsheet.worksheet("Support")

    # sys.exit()

    print("Ready for data...")
    # Ok take stdin and enter into bump log 
    while True:
        try:
            if select.select([sys.stdin],[],[],1.0)[0]:
                line = sys.stdin.readline()
                while len(line)>0:
                    # print(f'Line: {line}')
                    receiveline(line)
                    line = sys.stdin.readline()   
            else:
                if len(rowqueue)>0:
                    print("Processing queue...")
                    try:
                        findnextrow()
                        if len(rowqueue)>0:
                            worksheet.update(rowqueue,f'A{row}:H{row+len(rowqueue)-1}', raw=False)
                            row += len(rowqueue)
                        rowqueue = []
                    except Exception as e:
                        exc_type, exc_obj, exc_tb = sys.exc_info()
                        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                        print(exc_type, fname, exc_tb.tb_lineno)
                        print(traceback.format_exc())
                        print("--= Some failure occured trying to add information. Pausing 30 seconds =--")
                        time.sleep(30)

        except StopIteration:
            print('EOF!')
            break


if __name__ == "__main__":
    main()

