#!/usr/bin/env -S uv run --script --quiet
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

# NOTE: You will need to set up a file with your google cloud credentials
# as noted in the documentation for the "gspread" module

# event queue - this is to keep from making too many API calls per minute
rowqueue = [ ]
hypequeue = [ ]
supportqueue = [ ]
detailupdate = [ ]
songqueue = [ ]

# Starting row
row = 2
rowsearchwidth = 50 # Size of the initial search

# Track new rows
newrowcount = 100
newrowused = 100
lastrow = 0
ordercount = 0

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
        help="google sheet identifier"
    )

    parser.add_argument(
        "--line",
        type=int,
        default=None,
        help="line to start searching for free space"
    )

    parser.add_argument(
        "--statefile",
        type=str,
        default="default.state",
        help="State file used to remember last location in sheet"
    )

    parsed_args = parser.parse_args()

    if parsed_args.gsheets_credentials_file is None:
        parsed_args.gsheets_credentials_file = Path(
            __file__).parent / "gsheets_credentials.json"

    return parsed_args


""" Recieved Line Examples

 Input is tab seperated

   Stream start and end messages
 ---------------------------------------
 2026-06-11 22:35:37 === ONLINE (type=live @ 2026-06-12T02:35:24Z ===
 2026-06-12 08:48:44 === OFFLINE ===

  Bits
 ---------------------------------------
 2026-06-12 08:19:23			Michael_249	Bits	$0.88	na	
 2026-06-12 08:19:29			Michael_249	Bits	$0.90	na	
 2026-06-12 08:19:39			LRowyn	Bits	$0.85	na	

  Tips
 ---------------------------------------
 2026-06-08 23:55:56			COREYTOWNZ	Tip	$55.55	na	
 2026-06-08 23:56:54			Kirby_Bitera	Tip	$35.00	na	
 2026-06-09 00:05:12			rainchilddotcom	Tip	$35.22	na	
 2026-06-09 00:30:42			andviceversa_	Tip	$30.00	na	
 2026-06-09 00:56:45			Rosennetyle	Tip	$10.00	na	
 2026-06-09 02:05:44			alinsa_vix	Tip	$60.00	na	
 2026-06-09 02:40:43			O_xD	Tip	$30.00	na	
 2026-06-09 02:50:01			Valxa__	Tip	$69.69	na	
 2026-06-09 02:50:54			COREYTOWNZ	Tip	$69.68	na	

 Subs
 ---------------------------------------
 2026-06-12 02:58:00			Ninjafish255	Sub #105	$5.00	na	
 2026-06-12 03:28:36			Insomniac_rap	Sub #101	$10.00	na	
 2026-06-12 05:38:55			MannyHub	Sub #80	$25.00	na	
 2026-06-12 05:57:58			5Iappy	Sub #84	$5.00	na	
 2026-06-12 07:38:20			bombasticdaddynut	Sub #8	$5.00	na	
 2026-06-12 08:33:58			RobAncalagon	Sub #49	$25.00	na	

 Gift Subs
 ---------------------------------------
 2026-06-11 23:12:48		lego1042	PurpleTentacle_	Sub	$5.00	na	
 2026-06-11 23:12:48		lego1042	nonstop_despair	Sub	$5.00	na	
 2026-06-11 23:12:48		lego1042	Desdanovas	Sub	$5.00	na	
 2026-06-11 23:12:48		lego1042	MikeyMet	Sub	$5.00	na	
 2026-06-11 23:12:54		LRowyn	MissBeccaroonie	Sub	$5.00	na	
 2026-06-11 23:12:54		LRowyn	tipen3wiparata	Sub	$5.00	na	
 2026-06-11 23:12:54		LRowyn	majorlobster	Sub	$5.00	na	
 2026-06-11 23:12:54		LRowyn	itmeJP	Sub	$5.00	na	

 Raffle
 ---------------------------------------
 2026-06-11 23:00:35			Zerostalgia	Raffle	$0.00	na	
 2026-06-12 04:24:44			Slest	Raffle	$0.00	na

 Song requests
 ---------------------------------------
 SONG REQUEST FROM alinsa_vix: =HYPERLINK("https://www.youtube.com/watch?v=6gyzuy5cFWg", "Wild Arms 2nd Ignition (2nd Opening - JAP)")
 SONG REQUEST FROM O_xD: =HYPERLINK("https://www.youtube.com/watch?v=1_cePGP6lbU", "Bon Iver - Woods")
 SONG REQUEST FROM COREYTOWNZ: =HYPERLINK("https://youtu.be/E9EarKleINw?si=UZfr46hQltMmvs1k", "Stickerbush Symphony || Donkey Kong Bananza (Original Soundtrack)")
 SONG REQUEST FROM valxa__: =HYPERLINK("https://www.youtube.com/watch?v=TQ8WlA2GXbk", "Official髭男dism - Pretender［Official Video］")
 SONG REQUEST FROM combusterf: =HYPERLINK("6RUIeX6UCT8", "Don Henley - The Boys Of Summer")
 SONG REQUEST FROM Zerostalgia: =HYPERLINK("https://www.youtube.com/watch?v=uvY8fdgezLQ", "Zara Larsson - Midnight Sun (Official Music Video)")
 SONG REQUEST FROM WearsHats: =HYPERLINK("https://youtu.be/c8LNPeVPMIo", "KIRBY KRACKLE "Ring Capacity" (Green Lantern Song) Official Music Video")
 SONG REQUEST FROM TurboAbsurdum: =HYPERLINK("https://www.youtube.com/watch?v=5AlklK5q0wQ", "MERRIL BAINBRIDGE | Mouth | Official Music Video | 1994")
 SONG REQUEST FROM silent_song23: =HYPERLINK("https://www.youtube.com/watch?v=gut423ANiwo&list=RDgut423ANiwo&start_radio=1", "My Little Pony: The Movie - Official 'Rainbow' 🌈 Lyric Music Video by Sia")
 SONG REQUEST FROM Ninjafish255: =HYPERLINK("https://www.youtube.com/watch?v=S9zoPeH-Ly0", "Mega Man 4 (NES) Music - Cossack Fortress 2")
 SONG REQUEST FROM Slest: =HYPERLINK("v=RBaSiVjtKR4", "Body to Body")
 SONG REQUEST FROM Slest: =HYPERLINK("v=Dt2P9jRa7w0", "they don't know 'bout us")
 SONG REQUEST FROM ricketyrailway: =HYPERLINK("https://www.youtube.com/watch?v=eY-eyZuW_Uk", "DJ Shadow - Six Days")
 SONG REQUEST FROM COREYTOWNZ: =HYPERLINK("https://youtu.be/X6QzbvH-ZNo?si=zT8wqW3piUkiEYJx", "The Addams Family Theme song")
 Bump Log Columns
 0 Date/Time string in EST YYYY-MM-DD HH:MM:SS
 1 Order.  Sequence number of the log entry from last STREAM START message (Stream start is 0)
 2 Gifter.  For Gift subs, gift tips/bits for song requests.  This is the username of the gifter otherwise its blank
 3 Member.  The chat nickname that generated the request.  Also for special events like "STREAM START, "STREAM OFFLINE", "HYPETRAIN"
 4 Type.  The type of event:  Tip, Bits, Sub, Sub #XX, Raffle, Hype
 5 US Dollar Amount.  Value of the item
 6 Status. For tracking song requests.  Can be NA, waiting, bumped (shifted in order in nightbot), loop/piano (onglist+ queuing), played, raffle
 7 Detail.  This is mainly for the hyperlink for song requets, but also for other mod notes.
"""

def remove_inside_quotes(input_string):
    # 1. Find the first occurrence of "(url," to isolate the parts
    # This ensures we split at the correct comma even if the title has commas.
    if '(' not in input_string and ',' in input_string:
        print(f'Unexpected input: {input_string} - Skipping. Expected format: =HYPERLINK("url", "title")')
        return input_string # Return original if format is unexpected
    else:
        new_string = input_string.replace('","','\n').replace('", "','\n').replace('" ,"','\n')
        # new string should have two lines now
        parts = new_string.split('\n')

    if len(parts) < 2:
        print(f'Unexpected input: {input_string} - {len(parts)} {parts}')
        return input_string # Return original if format is unexpected

    # part[0] will be something like: =HYPERLINK("https://youtu.be/c8LNPeVPMIo"
    # part[1] will be something like:  "KIRBY KRACKLE "Ring Capacity" (Green Lantern Song) Official Music Video")
    
    url_part = parts[0].replace('"','').replace('HYPERLINK(','HYPERLINK("') + '"'

    # Fix just the video if its not the full link
    # Check if we have a simple YouTube ID (no https in URL part)
    # print(f'url part: {url_part}')
    if not '=HYPERLINK("https://' in url_part:
        # Extract the video ID from the URL part
        # The url_part should be something like: HYPERLINK("o5gIvu8sATQ"
        # We need to extract just the video ID part and make it a full URL
        match = re.search(r'\=HYPERLINK\("([^"]+)"', url_part)
        if match:
            video_id = match.group(1)
            # If it's not already a full URL, convert simple ID to full URL
            if not video_id.startswith('http'):
                url_part = f'=HYPERLINK("https://youtu.be/{video_id}")'

    title_part = '"' + parts[1].replace('"','').replace('(','').replace(')','') + '")'

    # 2. Reconstruct
    return f'{url_part}, {title_part}'

def receiveline(line):
    global row
    global rowqueue
    global hypequeue
    global supportqueue
    global songqueue
    global detailupdate

    # Valid date pattern
    validdate = re.compile("^20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]")
    eventstring = re.compile(" ===")
    hypeend = re.compile("=== HYPE TRAIN END")
    hypelevel = re.compile(r'level=(\d*)')
    streamstart = re.compile("=== ONLINE")
    streamend = re.compile("=== OFFLINE")
    songrequest = re.compile(r'SONG REQUEST FROM ([^:]+): (=HYPERLINK.*)')

    items = line.split("\t")
    if len(items) > 1 and validdate.match(items[0]):
        if not eventstring.match(items[1]):
            print(f'Adding Entry: {line.rstrip()}', flush=True)
            # Make sure its the right length
            if len(items)>7:
                items[7] = ''
            else:
                while len(items)<8:
                    items.append('')
            rowqueue.append(items[0:8])

            # This builds a map of support by member
            if (items[4] in ["Tip", "Bits", "Raffle"]) and ( float(items[5].replace('$','')) >= 10 or items[5] == "$0.00" ):
                supportqueue.append([items[3],len(rowqueue)-1+row,items[5]])

    elif hypeend.search(line):
        hypelevel = hypelevel.search(line)
        print(f'Hype: {hypelevel.group(1)}', flush=True)
        if hypelevel.group(1):
            level = int(hypelevel.group(1)) -1
            # New way to record Hype Trains Directly
            items = line.split(" ")
            rowqueue.append([items[0]+" "+items[1],"","","Hype Train End","Hype","0.00","na", f'Completed Level {level}'])

            # Old way.  If nothing adds to the queue, it will not do anything.  Later to remove this code.
            # hypequeue.append([[[ f'Hypetrain Completed Level {level}']],row+len(rowqueue)-1])
    elif streamstart.search(line):
        items = line.split(" === ")
        print(f'Stream Start: {items[0]}', flush=True)
        rowqueue.append([items[0],"","","STREAM START","","","",""])
        supportqueue=[]    # Erase the support queue
        songqueue=[]    # Erase the song queue
    elif streamend.search(line):
        items = line.split(" === ")
        print(f'Stream End: {items[0]}', flush=True)
        rowqueue.append([items[0],"","","STREAM END","","","",""])
        supportqueue=[]    # Erase the support queue
        songqueue=[]    # Erase the song queue
    elif songrequest.search(line):
        songdetail = songrequest.search(line)
        requester = songdetail.group(1)
        song = remove_inside_quotes(songdetail.group(2))
        print(f'Song Request from {requester}: {song}', flush=True)
        
        # Search through supportqueue for a matching member
        detailupdate = []  # Array to hold updates for non-existing entries
        
        # Iterate through supportqueue backwards to avoid index shifting issues when removing items
        i = len(supportqueue) - 1
        match_found = False
        while i >= 0:
            (member, row_num, amount) = supportqueue[i]
            
            # Check if this is the matching requester
            if member.lower() == requester.lower():
                # Look for existing entry in rowqueue with same member and amount
                found_existing = False
                for j, row_entry in enumerate(rowqueue):
                    if (row_entry[3] == member and 
                        row_entry[5] == amount and 
                        row_entry[4] in ["Tip", "Bits", "Raffle"]):
                        
                        # Update the existing entry with song detail
                        row_entry[7] = f'{song}'
                        found_existing = True
                        break
                
                if not found_existing:
                    # Add to detailupdate array for later processing
                    detailupdate.append([row_num, requester, song])
                
                # Remove from supportqueue
                supportqueue.pop(i)

                match_found = True
                break  # Don't continue to next item in queue as we've found a match for this request
            
            i -= 1
        
        if not match_found:
            songqueue.append([requester, song, False])
            print(f'No match found for {requester}\'s request. Added to songqueue')

        # Process detailupdate array - this would be handled in the main function when updating the sheet
    else:
        print(f'Did not understand: {line}')
    
def findnextrow():
    global supportSheet
    global row
    global lastrow
    global rowqueue
    global hypequeue
    global newrowcount
    global newrowused
    global rowsearchwidth

    validdate = re.compile(r'^(\d+)-(\d+)-(\d+)\s(\d+):(\d+):(\d+)')

    # Expand size of the search window based on input size
    if len(rowqueue) > rowsearchwidth:
        rowsearchwidth=len(rowqueue)*4

    count = rowsearchwidth + 1
    startrow = row - rowsearchwidth
    if startrow < 2:
        startrow = 2
    blankfound = False
    while not blankfound:
        endrow = row + rowsearchwidth
        print(f'Looking for last row between {startrow} and {endrow}')
        count = 0
        rowpos = startrow
        try:
            data = supportSheet.get(f'A{startrow}:G{endrow}', pad_values=True)
            print(f'Data received: {len(data)}', flush=True)
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
            print(traceback.format_exc())
            sys.exit(f"Google Sheet Exception {e}")

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
                    row = rowpos
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
                    if newrow[1] != "":
                        ordercount = int(newrow[1])

                    #print(f'Checking against {newrow}')
                    for r in range(0,len(rowqueue)):
                        #print(f' Datestring: {datestring} rowqueue: {rowqueue[r][0]}')
                        if datestring == rowqueue[r][0] and (newrow[3] == "STREAM START" or (newrow[2] == rowqueue[r][2] and newrow[3] == rowqueue[r][3] and newrow[4][:3] == rowqueue[r][4][:3] and newrow[5] == rowqueue[r][5])):
                            print(f'  Already in sheet: ${rowqueue[r]}')
                            # Decrease and hype count row by one
                            for i in range(len(hypequeue)):
                                hypequeue[i][1]-=1
                        else:
                            newrowqueue.append(rowqueue[r])
                    rowqueue = newrowqueue
            
            # Blank row found
            if newrow[0] == "" and newrow[2] == "" and newrow[3] == "" and not blankfound:
                row = rowpos
                blankfound = True
                print(f'Found last blank row {row}', flush=True)

        if not blankfound:    
            row = rowpos
            print(f'Found last row {row}', flush=True)
            blankfound = True
        startrow = row - 5
        if startrow < 2:
            startrow = 2
        rowsearchwidth = 10 # Reduce future search width

    # Find the last row not likely to have anything in the comment field
    if len(rowqueue)>0:
        for r in range(0,len(rowqueue)):
            # Generate the order column, if STREAM START, then ordercount is an offset from r+1
            if rowqueue[r][3] == "STREAM START" or rowqueue[r][3] == "STREAM END":
                ordercount=(-r-1)
            rowqueue[r][1]= r+ordercount+1
            if rowqueue[r][5]:
                dollarvalue = float(re.sub(r'\$','',rowqueue[r][5]))
                if dollarvalue < 24.99:
                    lastrow = row + r

    print(f'Next blank row: {row} New rows to add: {len(rowqueue)}')

    print(f'To Add:')
    for r in range(0,len(rowqueue)):
        print(f'{rowqueue[r]}')


def main() -> int:
    global row
    global rowqueue
    global hypequeue
    global supportSheet
    global detailupdate
    global songqueue

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
    supportSheet= gsheet.worksheet("Support")

    # sys.exit()
    state_path = Path(__file__).resolve().parent / args.statefile

    if args.line is not None:
        row = args.line
        state_path.write_text(str(row))

    row = int(state_path.read_text())
    
    print("Ready for data...", flush=True)
    # Ok take stdin and enter into bump log 
    failure_count=0
    
    while True:
        try:
            # Check for up to a second for more data
            if select.select([sys.stdin],[],[],1.0)[0]:
                while True:
                    line = sys.stdin.readline()
                    if not line:
                        break
                    print(f'Line: {line}')
                        
                    receiveline(line)
                    
                    # Quick check for more data without long timeout
                    if not select.select([sys.stdin], [], [], 0.01)[0]:
                        # Handle updating details from song requests provided
                        while len(detailupdate)>0:
                            row_num, requester, song = detailupdate.pop()
                            try:
                                print(f'Updating {song} at row {row_num}')
                                supportSheet.update_cell(row_num, 8, song)
                            except Exception as e:
                                exc_type, exc_obj, exc_tb = sys.exc_info()
                                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                                print(exc_type, fname, exc_tb.tb_lineno)
                                print(traceback.format_exc())
                                print("--= Some failure occured trying to add information. Adding back to songqueue =--", flush=True)
                                songqueue.append([requester, song, False])
                        # Since there is no detail, drop out of loop
                        break 

            if len(rowqueue)>0:
                print("Processing queue...", flush=True)
                try:
                    findnextrow()
                    print("Updating google sheet...")
                    supportSheet.append_rows(rowqueue, table_range=f'A{row}',value_input_option='USER_ENTERED', insert_data_option='INSERT_ROWS')
                    print("Successfully updated", flush=True)
                    row += len(rowqueue)
                    state_path.write_text(str(row))
                    failure_count=0
                    rowqueue = []
                except Exception as e:
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                    print(exc_type, fname, exc_tb.tb_lineno)
                    print(traceback.format_exc())
                    print("--= Some failure occured trying to add information. Pausing 30 seconds =--", flush=True)

                    failure_count = failure_count + 1
                    time.sleep(30*failure_count)

                    # See if reopening the sheet helps
                    gsheet = gc.open_by_key(ONG_BUMP_SPREADSHEET_ID)
                    supportSheet= gsheet.worksheet("Support")

                    if failure_count > 4:
                        print("API Seems to not be working anymore -- exiting")
                        break
            # If there are songs that haven't been showed at the bottom of the list
            if len(songqueue)>0:
                for j, (requester, song, shownflag)  in enumerate(songqueue):
                    if not shownflag:
                        try:
                            supportSheet.update_cell(row+j, 8, song.replace('")',' QUEUED BY '+requester+'")'))
                            songqueue[j]=[requester, song, True]
                        except Exception as e:
                            print (f"Error clearing cell: {e} to remove song queue list")
                            time.sleep(30)
                            break

            # This really isn't a thing any more -- waiting for better hype logging from ongwatch
            if len(hypequeue)>0:
                for hype in hypequeue:                        
                    try:
                        supportSheet.update_acell(hype[0],f'H{hype[1]}')
                        print(f'Updated H{hype[1]} for Hypetrain {hype[0]}', flush=True)
                    except:
                        print(f'Failed to update H{hype[1]} for Hypetrain {hype[0]}', flush=True)
                hypequeue = []

            # Print a dot every second to keep the user entertained while we wait for data
            # print('.',end='',flush=True)

        except StopIteration:
            print('EOF! Terminating')
            break
    print('EOF! Terminating')

if __name__ == "__main__":
    main()
