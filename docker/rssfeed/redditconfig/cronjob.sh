#!/bin/sh
*/30 * * * * cd /usr/local/src/rssfeedredditdatabase && /usr/local/bin/pipenv run python /usr/local/src/rssfeedredditdatabase/rssfeedredditdatabase.py >> /var/log/cron.log 2>&1
