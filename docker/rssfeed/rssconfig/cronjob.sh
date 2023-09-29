#!/bin/sh
*/30 * * * * cd /usr/local/src/rssfeeddatabase && /usr/local/bin/pipenv run python /usr/local/src/rssfeeddatabase/rssfeeddatabase.py >> /var/log/cron.log 2>&1
