#!/bin/bash
#
# Runs the Ong Auto Bump Logger to the test
AUTOBUMPDIR=/home/ongbots/ongautobump
cd $AUTOBUMPDIR
if [ ! -f "$AUTOBUMPDIR/.venv/bin/activate" ]; then
    pip3 install -r requirements.txt
fi
source $AUTOBUMPDIR/.venv/bin/activate

GSHEETID=`cat $AUTOBUMPDIR/gsheet_test.id`

tail -n 100  -f /home/ongbots/ongwatch/bump.log   | ./ongautobump.py --gsheets-credentials-file $AUTOBUMPDIR/gsheets_credentials.json --gsheets-id $GSHEETID
