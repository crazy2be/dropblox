#!/bin/bash

# Actually exit on Ctrl+C
trap '{ exit 1; }' INT

python client.py practice src/main.py

# This is pretty gross, but their script keeps dying randomly.
if [ $? == 0 ]; then exit 0
else ./$0
fi

