#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from flask import Flask, request, jsonify, abort
from werkzeug.contrib.cache import SimpleCache
import os
import erppeek
import time
import datetime

app = Flask(__name__)
app.config.from_envvar("SENDTIME_SETTINGS")
cache = SimpleCache()

def current_user():
	user = request.environ.get('REMOTE_USER')
	if user is None:
		if app.config["DEBUG"] != 0:
			user = "rasky"
		else:
			abort(400, {'error': 'REMOTE_USER not provided'})

	# See if we have a client already in list
	pwd = cache.get("pwd:" + user)
	if pwd is None:
		# Login as admin to retrieve userid and password for this user
		# NOTE: Odoo saves passwords in clear... furtunately, we don't store
		# the real passwords here (because we authenticate via SSO), but just
		# a random-generated password.
		client = odoo_client(app.config["ODOO_USER"], app.config["ODOO_PASSWORD"])
		record = client.ResUsers.read(["login="+user], fields=["id", "password"])[0]

		# Some users have no password (so login it's impossible with erppeek), or they
		# have a manually generated password that we don't trust. Let's replace it.
		if len(record["password"]) < 32:
			newpwd = os.urandom(16).encode("hex")
			client.ResUsers.write(record["id"], {"password": newpwd})
			record["password"] = newpwd

		cache.set("id:"+user, record["id"])
		cache.set("pwd:"+user, record["password"])

	return user, cache.get("id:"+user), cache.get("pwd:"+user)

def odoo_client(login, password):
	return erppeek.Client(
		app.config["ODOO_URI"],
		app.config["ODOO_DB"],
		login, password)

@app.errorhandler(500)
def server_error(e):
	return jsonify({"error": "internal server error", "exception": str(e)}), 500

@app.route('/api/timesheet', methods=["POST"])
def get_timesheet():
	login, userid, pwd = current_user()
	client = odoo_client(login, pwd)

	if request.json is None:
		abort(400, {'error': 'request body not in JSON format'})

	rdate = request.json.get("date")
	if rdate is None:
		abort(400, {'error': 'date not provided'})
	date = datetime.date(*time.strptime(rdate, "%Y-%m-%d")[:3])

	desc = request.json.get("description")
	if desc is None:
		abort(400, {'error': 'description not provided'})

	duration = request.json.get("duration")
	if duration is None:
		abort(400, {'error': 'duration not provided'})
	try:
		minutes = int(duration)
	except:
		abort(400, {'error': 'invalid format for duration (should be minutes)'})

	# Parse project from request
	proj = request.json.get("project")
	if proj is None:
		abort(400, {'error': 'project not provided'})

	# Extract project id from OpenERP (with unambiguous match)
	pids = client.AccountAnalyticAccount.read(
		["use_timesheets=True", "state=open", "name ilike " + proj],
		fields=["name"])
	if len(pids) == 0:
		abort(400, {'error': 'no project found matching %s' % proj})
	elif len(pids) > 1:
		if len(proj) > 3:
			abort(418, {'error': 'ambiguous project name',
				'matching_projects': [p['name'] for p in pids]})
		else:
			abort(418, {'error': 'ambiguous project name'})
	projectid = pids[0]["id"]

	# Search for a draft timesheet for this user
	sheetid = client.Hr_timesheet_sheetSheet.search(
		["state=draft", "user_id=%d" % userid, "date_from=%04d-%02d-01" % (date.year, date.month)],
	)
	if len(sheetid) == 0:
		abort(400, {'error': 'no draft timesheet found for this user for the specified month'})
	if len(sheetid) > 1:
		abort(500, {'error': 'too many timesheets for this user???'})
	sheetid = sheetid[0]

	# Now create a registration
	newrecord = client.HrAnalyticTimesheet.create({
		"journal_id": 6,  # Hard-coded timesheet journal used by Develer
		"account_id": projectid,
		"sheet_id": sheetid,
		"date": date.strftime("%Y-%m-%d"),
		"unit_amount": float(minutes)/60,
		"user_id": userid,
		"name": desc,
	})

	return jsonify({
		"record_id": newrecord.id,
	})

if __name__ == '__main__':
    app.run()
