#!/bin/bash
#
# Runs the Ong Auto Bump Logger to the test
AUTOBUMPDIR=/home/ongbots/ongautobump
cd $AUTOBUMPDIR
pip3 install -r requirements.txt

source $AUTOBUMPDIR/.venv/bin/activate

GSHEETID=`cat $AUTOBUMPDIR/gsheet_test.id`

tail -n 100  -f /home/ongbots/ongwatch/bump.log   | ./ongautobump.py --gsheets-credentials-file $AUTOBUMPDIR/gsheets_credentials.json --gsheets-id $GSHEETID --line 20000
