#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from flask import Flask, request, jsonify, abort
from werkzeug.contrib.cache import SimpleCache
from secrets import token_hex
import erppeek
import time
import datetime
from calendar import monthrange


app = Flask(__name__)
app.config.from_envvar("SENDTIME_SETTINGS")
cache = SimpleCache()


def current_user(client):
    user = request.environ.get('REMOTE_USER')
    if user is None:
        if app.config["DEBUG"] != 0:
            user = "rasky"
        else:
            abort(400, {'error': 'REMOTE_USER not provided'})
    # Retrieve odoo user id of this user
    record = client.ResUsers.read([('login', '=', user)], fields=["id"])
    if not record:
        abort(400, {'error': 'This user does not exist in Odoo'})
    return record[0]["id"]


def odoo_client():
    return erppeek.Client(
        app.config["ODOO_URI"],
        app.config["ODOO_DB"],
        app.config["ODOO_USER"],
        app.config["ODOO_PASSWORD"])


@app.errorhandler(500)
def server_error(e):
    return jsonify(
        {"error": "internal server error", "exception": str(e)}), 500


@app.route('/check')
def check():
    return jsonify({'message': 'It works!'})


@app.route('/api/timesheet', methods=["POST"])
def get_timesheet():
    client = odoo_client()
    userid = current_user(client)

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
        abort(
            400, {'error': 'invalid format for duration (should be minutes)'})

    # Parse project from request
    proj = request.json.get("project")
    if proj is None:
        abort(400, {'error': 'project not provided'})

    # Extract project id from OpenERP (with unambiguous match)
    pids = client.ProjectProject.read([('active', '=', True),
                                       ('name', 'ilike', proj), ],
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
    sheetid = client.Hr_timesheetSheet.search([
        ('state', 'in', ('draft', 'new')),
        ('user_id', '=', userid),
        ('date_start', '>=', '%04d-%02d-01' % (date.year, date.month)),
        ('date_end', '<=', '%04d-%02d-%02d' % (
            date.year,
            date.month,
            monthrange(date.year, date.month)[1],
            ))
        ])
    if len(sheetid) == 0:
        abort(
            400,
            {'error':
             'no draft timesheet found for this user for the specified month'})
    if len(sheetid) > 1:
        abort(500, {'error': 'too many timesheets for this user???'})
    sheetid = sheetid[0]

    # Now create a registration
    newrecord = client.AccountAnalyticLine.create({
        'date': date.strftime('%Y-%m-%d'),
        'project_id': projectid,
        'name': desc,
        'unit_amount': float(minutes)/60,
        'user_id': userid,
    })

    return jsonify({
        "record_id": newrecord.id,
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0')
