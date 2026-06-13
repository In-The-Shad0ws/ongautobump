#!/bin/bash
#
# Runs the Ong Auto Bump Logger to the test
AUTOBUMPDIR=.

GSHEETID=`cat $AUTOBUMPDIR/gsheet_test.id`

(sudo tail -n 100 /home/ongbots/ongwatch/bump.log ; sleep 5; sudo tail -n 100 -f /home/ongbots/ongwatch/bump.log)  | ( ./ongautobump.py --gsheets-credentials-file $AUTOBUMPDIR/gsheets_credentials.json --gsheets-id $GSHEETID --statefile test_state.txt)
