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
import wrapper.nhentai as nhentai
import wrapper.tsumino as tsumino
import wrapper.ehentai as ehentai
import wrapper.hitomila as hitomila
import wrapper.nHentaiTagBot as bot
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

def check_for_violation(comment):
    print("checkforviolation being run")
    numbers_combi = bot.scanForURL(comment)
    improper_nhentai_numbers = check_for_improper_urls(comment)
    if numbers_combi and improper_nhentai_numbers:
        for element in improper_nhentai_numbers:
            numbers_combi[0].append(element)
    elif not numbers_combi and improper_nhentai_numbers:
        numbers_combi = [improper_nhentai_numbers, [], [], []]
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


def check_for_improper_urls(comment):
    improper_nhentai_numbers = re.findall(r'((:?www.)?nhentai.net\/g\/.*?)(\d{1,6})', comment)
    try:
        improper_nhentai_numbers = [int(number[2]) for number in improper_nhentai_numbers]
    except ValueError:
        improper_nhentai_numbers = []
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

def main():
    global reddit
    reddit = authenticate()
    global cursor
    global db_conn
    db_conn, cursor = authenticate_db()
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