import praw
import time
import requests
import os
import re
import datetime
import json
#should import the site wrappers for the sites from the nhentai bot
import wrapper.tsumino as tsumino
import wrapper.nhentai as nhentai
import wrapper.hitomila as hitomila
import wrapper.ehentai as ehentai

doNotReplyList = ['Roboragi', 'WhyNotCollegeBoard']

PARSED_SUBREDDIT = 'Animemes'
REPORTING_SUBREDDIT = ['Animemes']
MODDING_SUBREDDIT = ['loli_tag_bot']
# PARSED_SUBREDDIT = 'loli_tag_bot'

def authenticate():
    print("Authenticating...")
    reddit = praw.Reddit('lolitagmod')
    print("Authenticated as {}".format(reddit.user.me()))
    return reddit

def main():
    global reddit
    reddit = authenticate()
    commentsReported = getSavedCommentIDs()
    commentsChecked = []
    while True:
        run_bot(commentsReported, commentsChecked)

def run_bot(commentsReported, commentsChecked):
    print("Current time: " + str(datetime.datetime.now().time()))
    print("Fetching comments...")
    # to limit fetched comments use comments(limit=int)
    for comment in reddit.subreddit(PARSED_SUBREDDIT).comments(limit=100):
        if comment.id not in commentsReported or (comment.id not in commentsChecked and not comment.edited) or comment.author not in doNotReplyList:
            replyString = ""
            print(comment.body)
            replyString = checkForViolation
            commentsChecked.append(comment.id)
        commentsChecked = commentsChecked[-100:]


def checkForViolation(comment):
    numbers = nhentai.scanURL(comment)
    if not numbers:
        numbers = getNumbers(comment)
    if numbers:
        for number in numbers:
            currentCheck = nhentai.analyseNumber(number)
            if currentCheck[-1]:
                return "7.2 Violation: Nhentai URL"

    numbers = tsumino.scanURL(comment)
    if numbers:
        for number in numbers:
            currentCheck = tsumino.analyseNumber(number)
            if currentCheck[-1]:
                return "7.2 Violation: Tsumino URL"

    numbers = ehentai.scanURL(comment)
    if numbers:
        for number in numbers:
            currentCheck = ehentai.analyseNumber(number)
            if currentCheck[-1]:
                return "7.2 Violation: Exhentai URL"

    numbers = hitomila.scanURL(comment)
    if numbers:
        for number in numbers:
            currentCheck = hitomila.analyseNumber(number)
            if currentCheck[-1]:
                return "7.2 Violation: Hitomi.la URL"


def getNumbers(cmt):
    # find and replace with nothing to elimnate URLs from the string.
    cmt = re.sub(r'https?:\/\/\S+', '', cmt)
    ## remove decimal numbers to prevent them from being parsed
    # cmt = re.sub(r'\d+\.\d+', '', cmt)
    # remove numbers the nHentaiTagBot is looking for
    #T sumino
    cmt = re.sub(r'(?<=\))\d{5}(?=\()', '', cmt)
    # ehentai
    cmt = re.sub(r'(?<=\})\d{1,8}\/\w*?(?=\{)', '', cmt)
    # hitomila
    cmt = re.sub(r'(?<=(?<!\>)\!)\d{5,8}(?=\!(?!\<))', '', cmt)
    # improved parser that'll hopefully not catch anything with less than 4 digits and spaced digits.
    numbers = getNumbersFromString(cmt)
    # if the standard search doesn't find anything do a special search
    if not numbers:
        # removes all characters that aren't numbers to find raised numbers.
        commentString2 = re.sub(r'\D*\^', '', cmt)
        # then looks if they are 5 or 6 characters long.
        numbers = getNumbersFromString(commentString2)
    # if there are still no numbers found try erasing crossed out numbers
    if not numbers:
        commentString2 = re.sub(r'~~\d*~~', '', cmt)
        numbers = getNumbersFromString(commentString2)
        # numbers = re.findall(r'\b\d\s*\d\s*\d\s*\d\s*\d\s*\d?\b', commentString2)
    # use a try and catch to prevent crashing when unexpected characters get into the numbers list.
    try:
        numbers = [int(number.replace(" ", "").replace("\xa0", "").replace("\n", "")) for number in numbers]
    except ValueError:
        print("Invalid number found")
        with open("errorCollection.txt", "a") as f:
            f.write("getTagResultCache failed number parsing at " + str(datetime.datetime.now().time()) + " with: " + str(numbers) + " original comment: "+ cmt +"end\n")
    numbers = list(set(numbers))
    return numbers


def getNumbersFromString(cmt):
    numbers = re.findall(r'(?<![\/=\d\w-])\d\s*\d\s*\d\s*\d\s*\d\s*\d?\b', cmt)
    return numbers



def getSavedCommentIDs():
    # return an empty list if empty
    if not os.path.isfile("commentsReported.txt"):
        commentsReported = []
    else:
        with open("commentsRepliedTo.txt", "r") as f:
            # updated read file method from https://stackoverflow.com/questions/3925614/how-do-you-read-a-file-into-a-list-in-python
            commentsReported = f.read().splitlines()

    return commentsReported

if __name__ == '__main__':
    while True:
        try:
            main()
        except Exception as e:
            pass
    # main()