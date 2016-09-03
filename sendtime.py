#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from flask import Flask,
#from odooTimereg import OdooTimereg

app = Flask(__name__)
app.config.from_envvar("SENDTIME_SETTINGS")

@app.route('/api/timesheet')
def get_timesheet():
	user = request.environ.get('REMOTE_USER')
	return "User: %s".format(user)
