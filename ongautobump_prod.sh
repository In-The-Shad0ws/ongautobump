#!/bin/bash
#
# Runs the Ong Auto Bump Logger to the test
AUTOBUMPDIR=/home/ongbots/ongautobump
cd $AUTOBUMPDIR

GSHEETID=`cat $AUTOBUMPDIR/gsheet_prod.id`

tail -n 100  -f /home/ongbots/ongwatch/bump.log   | ./ongautobump.py --gsheets-credentials-file $AUTOBUMPDIR/gsheets_credentials.json --gsheets-id $GSHEETID --statefile prod_state.txt
