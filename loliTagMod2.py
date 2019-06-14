import praw
import time
import requests
import os
import re
import datetime
import json
#imports the site wrappers for the sites from the nhentai bot
import wrapper.nhentai as nhentai
import wrapper.tsumino as tsumino
import wrapper.ehentai as ehentai
import wrapper.hitomila as hitomila
import wrapper.nHentaiTagBot as bot


nhentaiKey = 0
tsuminoKey = 1
ehentaiKey = 2
hitomilaKey = 3


# PARSED_SUBREDDIT = 'Animemes'
PARSED_SUBREDDIT = 'loli_tag_bot'

def authenticate():
    print("Authenticating...")
    reddit = praw.Reddit(
        # 'sachimod'
        'lolitagmod'
        )
    print("Authenticated as {}".format(reddit.user.me()))
    return reddit


def main():
    global reddit
    reddit = authenticate()
    run_bot()
    # while True:
    #     run_bot()


def run_bot():
    print("Current time: " + str(datetime.datetime.now().time()))
    print("Fetching modqueue...")
    for comment in reddit.subreddit(PARSED_SUBREDDIT).mod.modqueue(only='comments', limit=None):
        has_numbers, has_redaction = check_for_violation(comment.body)
        if has_numbers:
            if not has_redaction:
                comment.mod.approve()
            else:
                comment.mod.remove(spam=False)


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
        return True, isRedacted
    return False, isRedacted


main()