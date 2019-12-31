SENDTIME
========

Configuration
-------------

Create your configuration file. If you need you can use ```settings.cfg.sample``` file as template

Export configuration file path as environment data:

```
$ export SENDTIME_SETTINGS=/your/config/file/path
```

Run
---

Run **sendtime** as a python script


Test
----

It's possible to test **sendtime** with curl. For example:

### Check connection

```
$  curl  http://127.0.0.1:5000/check
```

### Send data

```
$  curl --header "Content-Type: application/json" --request POST --data '{"date":"2019-01-30","description":"Descrizione di test","duration":120,"project":"Progetto di Test"}' http://127.0.0.1:5000/api/timesheet
```
