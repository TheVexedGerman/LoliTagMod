import praw
import prawcore
import time
import requests
import os
import re
import datetime
import json
import psycopg2
import traceback
#imports the site wrappers for the sites from the nhentai bot
from wrapper.nhentai import Nhentai
from wrapper.ehentai import Ehentai
from wrapper.tsumino import Tsumino
# import wrapper.hitomila as hitomila

from wrapper.DBConn import Database
from wrapper.nHentaiTagBot import NHentaiTagBot as TagBot
import postgres_credentials_modque

nhentaiKey = 0
tsuminoKey = 1
ehentaiKey = 2
hitomilaKey = 3

def authenticate():
    print("Authenticating...")
    reddit = praw.Reddit(
        'hentaimemesmod'
        )
    print("Authenticated as {}".format(reddit.user.me()))
    return reddit
    
def authenticate_db():
    db_conn2 = psycopg2.connect(
    host = postgres_credentials_modque.HOST,
    database = 'hentaimemes',
    user = postgres_credentials_modque.USER,
    password = postgres_credentials_modque.PASSWORD
    )   

    return db_conn2, db_conn2.cursor()


def convert_time(time):
    if time:
        return datetime.datetime.utcfromtimestamp(time)
    return None

def run_bot():
    print("Current time: " + str(datetime.datetime.now().time()))
    print("Fetching modqueue...")
    for comment in reddit.subreddit('hentaimemes').mod.modqueue(only='comments', limit=None):
        print(comment.body)
        has_numbers, has_redaction = check_for_violation(comment.body)
        if has_numbers:
            if not has_redaction:
                print("Approving Comment")
                comment.mod.approve()
            else:
                print("Removing Comment")
                comment.mod.remove(spam=False)
    grab_modlog()
    modmail_fetcher(reddit, 'hentaimemes', cursor, db_conn)

def check_for_violation(comment):
    print("checkforviolation being run")
    numbers_combi = bot.scanForURL(comment)
    improper_nhentai_numbers = check_for_improper_urls(comment)
    if numbers_combi and improper_nhentai_numbers:
        numbers_combi += improper_nhentai_numbers
    elif not numbers_combi and improper_nhentai_numbers:
        numbers_combi = improper_nhentai_numbers
    isRedacted = False
    if numbers_combi:
        for entry in numbers_combi:
            number = entry.get("number")
            key = entry.get("type")
            if key == 'nhentai':
                processedData = nhentai.analyseNumber(number)
            elif key == 'tsumino':
                processedData = tsumino.analyseNumber(number)
            elif key == 'ehentai':
                processedData = ehentai.analyseNumber(number)
            # elif key == hitomilaKey:
            #     processedData = hitomila.analyseNumber(number)
            if processedData.get('isRedacted'):
                isRedacted = True
                break
            if processedData.get('error'):
                return False, False
        return True, isRedacted
    return False, isRedacted


def check_for_improper_urls(comment):
    improper_nhentai_numbers = re.findall(r'((:?www.)?nhentai.net\/g\/.*?)(\d{1,6})', comment)
    try:
        improper_nhentai_numbers = [{'number': int(number[2]), 'type': 'nhentai'} for number in improper_nhentai_numbers]
    except ValueError:
        improper_nhentai_numbers = {}
    return improper_nhentai_numbers


def grab_modlog():
    for action in reddit.subreddit("hentaimemes").mod.log(limit=None):
        cursor.execute("SELECT * FROM modlog WHERE id = %s", [action.id])
        exists = cursor.fetchone()
        if exists:
            break
        cursor.execute("INSERT INTO modlog (action, created_utc, description, details, id, mod, mod_id36, sr_id36, subreddit, subreddit_name_prefixed, target_author, target_body, target_fullname, target_permalink, target_title) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", (action.action, convert_time(action.created_utc), action.description, action.details, action.id, str(action.mod), action.mod_id36, action.sr_id36, action.subreddit, action.subreddit_name_prefixed, str(action.target_author), action.target_body, action.target_fullname, action.target_permalink, action.target_title))
        db_conn.commit()
    print("Sleeping for 30 seconds...")
    time.sleep(30)


def modmail_fetcher(reddit, subreddit, cursor, db_conn):
    for conversation in reddit.subreddit(subreddit).modmail.conversations(limit=1000, state='all'):
        exists = modmail_db_updater(conversation, reddit, cursor, db_conn)
        if exists:
            break
    for conversation in reddit.subreddit(subreddit).modmail.conversations(limit=1000, state='archived'):
        exists = modmail_db_updater(conversation, reddit, cursor, db_conn)
        if exists:
            break
    for conversation in reddit.subreddit(subreddit).modmail.conversations(limit=1000, state='appeals'):
        exists = modmail_db_updater(conversation, reddit, cursor, db_conn)
        if exists:
            break

def modmail_db_updater(conversation, reddit, cursor, db_conn):
    message = reddit.inbox.message(conversation.legacy_first_message_id)
    cursor.execute("SELECT id, replies FROM modmail WHERE id = %s", [message.id])
    exists = cursor.fetchone()
    replies = [reply.id for reply in message.replies]
    if exists and exists[1] == message.replies:
        return True
    cursor.execute("INSERT INTO modmail (id, created_utc, first_message_name, replies, subject, author, body, dest) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO UPDATE SET replies = EXCLUDED.replies, dest = EXCLUDED.dest, sent_to_discord = false", (message.id, convert_time(message.created_utc), message.first_message_name, replies, message.subject, str(message.author), message.body, str(message.dest)))
    for reply in message.replies:
        cursor.execute("INSERT INTO modmail (id, created_utc, first_message_name, subject, author, parent_id, body) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING", (reply.id, convert_time(reply.created_utc), reply.first_message_name, reply.subject, str(reply.author), reply.parent_id, reply.body))
    db_conn.commit()
    return False


def main():
    global reddit
    reddit = authenticate()
    global cursor
    global db_conn
    db_conn, cursor = authenticate_db()
    database = Database()
    global nhentai
    nhentai = Nhentai(database)
    global tsumino
    tsumino = Tsumino(database)
    global ehentai
    ehentai = Ehentai(database)
    global bot
    bot = TagBot(None, database)
    while True:
        run_bot()


if __name__ == '__main__':
    while True:
        try:
            main()
        except Exception as e:
            print(traceback.format_exc())
            open("logh.txt", 'a').write(f"{datetime.datetime.now().time()}:\n{traceback.format_exc()}\n")
            pass
    # main()
