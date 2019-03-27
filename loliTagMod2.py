import praw
import time
import requests
import os
import re
import datetime
import json
#should import the site wrappers for the sites from the nhentai bot
import wrapper.nhentai as nhentai
import wrapper.tsumino as tsumino
import wrapper.ehentai as ehentai
import wrapper.hitomila as hitomila

nhentaiKey = 0
tsuminoKey = 1
ehentaiKey = 2
hitomilaKey = 3


commentsChecked = []
doNotReplyList = ['Roboragi', 'WhyNotCollegeBoard']

PARSED_SUBREDDIT = 'Animemes'
REPORTING_SUBREDDIT = ['Animemes']
# REPORTING_SUBREDDIT = ['loli_tag_bot']
# MODDING_SUBREDDIT = ['loli_tag_bot']
MODDING_SUBREDDIT = []
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
    commentsRemoved = getRemovedCommentIDs()
    # global commentsChecked
    while True:
        run_bot(commentsReported, commentsRemoved)

def run_bot(commentsReported, commentsRemoved):
    # if passed as an argument the list gets reset fix with global assignment wtf???
    global commentsChecked
    print("Current time: " + str(datetime.datetime.now().time()))
    print("Fetching comments...")
    # to limit fetched comments use comments(limit=int)
    for comment in reddit.subreddit(PARSED_SUBREDDIT).comments(limit=100):
        replyString = ""
        if (comment.id not in commentsReported) and (comment.id not in commentsRemoved) and ((comment.id not in commentsChecked) and not comment.edited) and (comment.author not in doNotReplyList):
            print(comment.body)
            replyString = checkForViolation(comment.body)
            if replyString == True:
                commentsChecked.append(comment.id)
                continue
        if replyString:
            if comment.subreddit in REPORTING_SUBREDDIT:
                reportComment(replyString, comment)
                commentsReported.append(comment.id)
            if comment.subreddit in MODDING_SUBREDDIT:
                comment.mod.remove()
                commentsReported.append(comment.id)
        commentsChecked = commentsChecked[-100:]
        commentsReported = commentsReported[-100:]
    print("Sleeping for 30 seconds...")
    time.sleep(10)


def checkForViolation(comment):
    replyString = ""
    #URLs
    numbers = nhentai.scanURL(comment)
    replyString = scanNumbers(numbers, nhentaiKey, "URL")
    if replyString: return replyString

    numbers = tsumino.scanURL(comment)
    replyString = scanNumbers(numbers, tsuminoKey, "URL")
    if replyString: return replyString

    numbers = ehentai.scanURL(comment)
    replyString = scanNumbers(numbers, ehentaiKey, "URL")
    if replyString: return replyString

    numbers = hitomila.scanURL(comment)
    replyString = scanNumbers(numbers, nhentaiKey, "URL")
    if replyString: return replyString

    # bot number lookup
    numbers = nhentai.getNumbers(comment)
    replyString = scanNumbers(numbers, nhentaiKey, "bot call")
    if replyString: return replyString
    
    numbers = tsumino.getNumbers(comment)
    replyString = scanNumbers(numbers, tsuminoKey, "bot call")
    if replyString: return replyString

    numbers = ehentai.getNumbers(comment)
    replyString = scanNumbers(numbers, ehentaiKey, "bot call")
    if replyString: return replyString
    
    numbers = hitomila.getNumbers(comment)
    replyString = scanNumbers(numbers, hitomilaKey, "bot call")
    if replyString: return replyString
    # expanded search criteria
    # any continuous 5 to 6 digit number
    comment = removeOtherSiteCalls(comment)

    numbers = re.findall(r'\d{5,6}(?!\d)', comment)
    try:
        numbers = [int(number) for number in numbers]
    except ValueError:
        numbers = []
    replyString = scanNumbers(numbers, nhentaiKey, "")
    if replyString: return replyString
    
    # Loli tag bot criteria
    numbers = getNumbers(comment)
    replyString = scanNumbers(numbers, nhentaiKey, "expanded check criteria", prepend="Potential")


def scanNumbers(numbers, key, additionalInfo, prepend=""):
    replyString = ""
    if numbers:
        for number in numbers:
            if key == nhentaiKey:
                site = "Nhentai"
                currentCheck = nhentai.analyseNumber(number)
            elif key == tsuminoKey:
                site = "Tsumino"
                currentCheck = tsumino.analyseNumber(number)
            elif key == ehentaiKey:
                site = "E-hentai"
                currentCheck = ehentai.analyseNumber(number)
            elif key == hitomilaKey:
                site = "Hitomi.la"
                currentCheck = hitomila.analyseNumber(number)
            if len(currentCheck) > 1:
                if currentCheck[-1]:
                    kind = "Violation"
                    #TODO figure out the kind of banned content detected.
                    additionalInfo += " " + str(number)
                    replyString = generateReportString(site, additionalInfo, kind=kind, prepend=prepend)
                else:
                    return True
    return replyString
                

def getKindOfViolation(currentCheck, key):
    if key == nhentaiKey:
        for entry in currentCheck[2]:
            if 'loli' in entry[0]:
                return "Loli"
            elif 'shota' in entry[0]:
                return 'shota'
    if key == tsuminoKey:
        for entry in tag:
            if 'loli' in entry.lower():
                isRedacted = True
            elif 'shota' in entry.lower():
                isRedacted = True



def generateReportString(site, additionalInfo, kind="Violation", prepend=""):
    replyString = "7.2 " + kind + ": " + site + " " + additionalInfo
    if prepend:
        replyString = prepend + " " + replyString
    return replyString


def removeOtherSiteCalls(cmt):
    # find and replace with nothing to elimnate URLs from the string.
    cmt = re.sub(r'https?:\/\/\S+', '', cmt)
    # remove numbers the nHentaiTagBot is looking for
    # Nhentai
    cmt = re.sub(r'(?<=\()\d{5,6}(?=\))', '', cmt)
    #Tsumino
    cmt = re.sub(r'(?<=\))\d{5}(?=\()', '', cmt)
    # ehentai
    cmt = re.sub(r'(?<=\})\d{1,8}\/\w*?(?=\{)', '', cmt)
    # hitomila
    cmt = re.sub(r'(?<=(?<!\>)\!)\d{5,8}(?=\!(?!\<))', '', cmt)
    return cmt


def getNumbers(cmt):
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

def reportComment(replyString, comment):
    # trim to max report length
    replyString = replyString[:100]
    # report with the replyString Message
    comment.report(replyString)
    # also write it to file to enable reloading after shutdown
    with open("commentsReported.txt", "a") as f:
        f.write(comment.id + "\n")

def getSavedCommentIDs():
    # return an empty list if empty
    if not os.path.isfile("commentsReported.txt"):
        commentsReported = []
    else:
        with open("commentsReported.txt", "r") as f:
            # updated read file method from https://stackoverflow.com/questions/3925614/how-do-you-read-a-file-into-a-list-in-python
            commentsReported = f.read().splitlines()
    return commentsReported


def getRemovedCommentIDs():
    # return an empty list if empty
    if not os.path.isfile("commentsRemoved.txt"):
        commentsRemoved = []
    else:
        with open("commentsRemoved.txt", "r") as f:
            # updated read file method from https://stackoverflow.com/questions/3925614/how-do-you-read-a-file-into-a-list-in-python
            commentsRemoved = f.read().splitlines()
    return commentsRemoved


if __name__ == '__main__':
    while True:
        try:
            main()
        except Exception as e:
            pass
    # main()