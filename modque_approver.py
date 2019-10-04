import praw
import time
import requests
import os
import re
import datetime
import json
import psycopg2
#imports the site wrappers for the sites from the nhentai bot
import wrapper.nhentai as nhentai
import wrapper.tsumino as tsumino
import wrapper.ehentai as ehentai
import wrapper.hitomila as hitomila
import wrapper.nHentaiTagBot as bot
import postgres_credentials


nhentaiKey = 0
tsuminoKey = 1
ehentaiKey = 2
hitomilaKey = 3


PARSED_SUBREDDIT = 'Animemes'
FLAIR_ID = "094ce764-898a-11e9-b1bf-0e66eeae092c"
# PARSED_SUBREDDIT = 'loli_tag_bot'

def authenticate():
    print("Authenticating...")
    reddit = praw.Reddit(
        'sachimod'
        # 'lolitagmod'
        )
    print("Authenticated as {}".format(reddit.user.me()))
    return reddit


def main():
    global reddit
    reddit = authenticate()
    global cursor
    global db_conn
    db_conn, cursor = authenticate_db()
    global watched_id_set
    watched_id_set = set()
    global watched_id_report_dict
    watched_id_report_dict = {}
    # run_bot()
    while True:
        run_bot()


def run_bot():
    print("Current time: " + str(datetime.datetime.now().time()))
    print("Fetching modqueue...")
    for comment in reddit.subreddit(PARSED_SUBREDDIT).mod.modqueue(only='comments', limit=None):
        print(comment.body)
        has_numbers, has_redaction = check_for_violation(comment.body)
        if has_numbers:
            if not has_redaction:
                print("Approving Comment")
                comment.mod.approve()
            else:
                print("Removing Comment")
                comment.mod.remove(spam=False)
    print("Checking for improper spoilers")
    check_for_improper_spoilers()
    print("Checking for re-reported reposts")
    approve_old_reposts()
    print("Sleeping for 30 seconds...")
    time.sleep(30)


def check_for_violation(comment):
    print("checkforviolation being run")
    numbers_combi = bot.scanForURL(comment)
    combination = []
    isRedacted = False
    if numbers_combi:
        for i, entry in enumerate(numbers_combi):
            for subentry in entry:
                combination.append([subentry, i])
        if combination:
            for entry in combination:
                number = entry[0]
                key = entry[1]
                if key == nhentaiKey:
                    processedData = nhentai.analyseNumber(number)
                elif key == tsuminoKey:
                    processedData = tsumino.analyseNumber(number)
                elif key == ehentaiKey:
                    processedData = ehentai.analyseNumber(number)
                elif key == hitomilaKey:
                    processedData = hitomila.analyseNumber(number)
                if len(processedData) > 1:
                    if processedData[-1]:
                        isRedacted = True
                        break
        return True, isRedacted
    return False, isRedacted


def check_for_improper_spoilers():
    for submission in reddit.subreddit(PARSED_SUBREDDIT).new(limit=200):
        if submission.spoiler:
            # check title for spoiler formatting
            match = re.search(r"\[.+?\]", submission.title)
            if not match:
                print(f"Removeing: {submission.title}")
                submission.mod.remove()
                # improperly marked spoiler flair
                submission.flair.select(FLAIR_ID)


def authenticate_db():
    db_conn = psycopg2.connect(
    host = postgres_credentials.HOST,
    database = postgres_credentials.DATABASE,
    user = postgres_credentials.USER,
    password = postgres_credentials.PASSWORD
    )   

    return db_conn, db_conn.cursor()


def update_db(post_id, reports_dict):
    cursor.execute("SELECT * FROM repost_report_check WHERE id = %s", [post_id])
    entry_exists = cursor.fetchone()
    if entry_exists:
        cursor.execute("UPDATE repost_report_check SET reports_json = %s, timestamp = %s WHERE id = %s", (json.dumps(reports_dict), datetime.datetime.now(), post_id))
    else:
        cursor.execute("INSERT INTO repost_report_check (id, timestamp, reports_json) VALUES (%s, %s, %s)", (post_id, datetime.datetime.now(), json.dumps(reports_dict)))
    db_conn.commit()


def make_dict(reports):
    report_dict = {}
    for report in reports:
        report_dict.update({report[0]:report[1]})
    return report_dict


def approve_old_reposts():
    for reports in reddit.subreddit(PARSED_SUBREDDIT).mod.reports():
        # Why can't I check if link flair exists without trying to get an exception?
        try:
            # check if there is a template ID (through AttributeError) and if the template ID matches the old repost one
            if reports.link_flair_template_id == "9a07b400-3c37-11e9-a73e-0e2a828fd580":
                approve = True
                report_dict = make_dict(reports.user_reports)
                for report in reports.user_reports:
                    # if the report contains repost it can be ignored.
                    if "repost" not in report[0].lower():
                        approve = False
                        break
                if not approve:
                    cursor.execute("SELECT reports_json FROM repost_report_check WHERE id = %s", [reports.id])
                    reference_dict = cursor.fetchone()
                    # Make sure an entry exits before assignment, otherwise create empty dict
                    if reference_dict:
                        reference_dict = reference_dict[0]
                    else:
                        reference_dict = {}
                    for entry in report_dict:
                        # ignore repost reports even if they have changed number
                        if "repost" in entry.lower():
                            continue
                        # compare the entry to the stored one if they don't match set watch and break out of loop
                        if report_dict.get(entry) != reference_dict.get(entry):
                            watched_id_set.add(reports.id)
                            watched_id_report_dict.update({reports.id:report_dict})
                            update_db(reports.id, report_dict)
                            approve = False
                            break
                        approve = True
                # approve the post and go back to the beginning of the loop        
                if approve:
                    reports.mod.approve()
                    update_db(reports.id, report_dict)
                    continue
        except AttributeError:
            pass
    # Check modlog for approvals of previously marked posts.
    for action in reddit.subreddit(PARSED_SUBREDDIT).mod.log(limit = 200):
        if action.target_fullname[:2] == "t3":
            if action.target_fullname[3:] in watched_id_set:
                cursor.execute("SELECT timestamp FROM repost_report_check WHERE id = %s", [reports.id])
                time = cursor.fetchone()[0]
                action_time = datetime.datetime.utcfromtimestamp(action.created_utc)
                if time < action_time:
                    watched_id_set.remove(action.target_fullname[3:])
                    update_db(action.target_fullname[3:], watched_id_set.pop(action.target_fullname[3:]))


if __name__ == '__main__':
    while True:
        try:
            main()
        except Exception as e:
            print(e)
            pass