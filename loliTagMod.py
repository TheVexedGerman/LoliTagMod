import praw, time, requests, os, re, datetime, json

# the API URL defined for easy adjustment
API_URL = 'https://nhentai.net/g/'
PARSED_SUBREDDIT = 'Animemes'
# PARSED_SUBREDDIT = 'loli_tag_bot'

doNotReplyList = ['HelperBot_', 'YTubeInfoBot', 'RemindMeBot', 'anti-gif-bot', 'Roboragi', 'sneakpeekbot', 'tweettranscriberbot', 'WhyNotCollegeBoard']

def authenticate():
    print("Authenticating...")
    reddit = praw.Reddit('lolitagmod')
    print("Authenticated as {}".format(reddit.user.me()))
    return reddit


def main():
    global reddit
    reddit = authenticate()
    commentsRepliedTo = getSavedComments()
    # # postsRepliedTo = getSavedPosts()
    while True:
        run_bot(commentsRepliedTo)


def run_bot(commentsRepliedTo, postsRepliedTo=[]):
    print("Current time: " + str(datetime.datetime.now().time()))
    print("Fetching comments...")
    # to limit fetched comments use comments(limit=int)
    for comment in reddit.subreddit(PARSED_SUBREDDIT).comments(limit=100):
        if comment.id not in commentsRepliedTo and comment.author not in doNotReplyList:
            replyString = ""
            cmt = comment.body
            # print(cmt)
            tagResultCache = getTagResultCache(cmt)
            # Check if tagResultCache is not empty.
            if tagResultCache:
                # comment.mod.remove()
                replyString = generateReplyString(tagResultCache, 0)
            if replyString:
                print("Reporting: " + comment.id)
                reportComment(replyString, comment)
                # comment.report(replyString, comment)
                commentsRepliedTo.append(comment.id)
            # # Check if a reply was generated
            # if replyString:
            #     # post the string and save the replied to comment to not analyse and reply again
            #     # print("PrePost" + replyString)               
            #     writeCommentReply(replyString, comment)
    # do the same for titles as it does for comments
    print("Current time: " + str(datetime.datetime.now().time()))
    print("Fetching posts...")
    for submission in reddit.subreddit(PARSED_SUBREDDIT).new(limit=10):
        # print(submission.title)
        if submission.id not in postsRepliedTo:
            replyString = ""
            title = submission.title
            tagResultCache = getTagResultCache(title)
            if tagResultCache:
                # submission.mod.remove()
                replyString = generateReplyString(tagResultCache, 1)
            if replyString:
                print("reporting: " + submission.id)
                submission.report(replyString)
                postsRepliedTo.append(submission.id)
            # if replyString:
            #     print(replyString)
            #     postsRepliedTo.append(submission.id)
            #     submission.reply(replyString)
    # Sleep for 30 seconds...
    print("Sleeping for 30 seconds...")
    time.sleep(30)


def reportComment(replyString, comment):
    # post the replyString to reddit as a reply
    comment.report(replyString)
    # also write it to file to enable reloading after shutdown
    with open("commentsRepliedTo.txt", "a") as f:
        f.write(comment.id + "\n")


def generateReplyString(tagResultCache, subType):
    replyString = ""
    if tagResultCache:
        if subType == 0:
            if tagResultCache[0]:
                replyString += "7.2 Loli number "
            if tagResultCache[1]:
                replyString += "7.2 Shota number "
        if subType == 1:
            if tagResultCache[0]:
                replyString += "7.2 Loli number "
            if tagResultCache[1]:
                replyString += "7.2 Shota number "
    print(replyString)
    return replyString



def getTagResultCache(cmt):
    print(cmt)
    numbers = getNumbers(cmt)
    # checks if the list is empty
    if numbers:
        print("Numbers available")
        print(numbers)
        # iterates over the list
        for number in numbers:
            print(number)
            # get the tags from the nHentai API function
            tagResult = retrieveTags(number)
            if tagResult:
                if tagResult[0] or tagResult[1]:
                    return tagResult
    return False


def getNumbers(cmt):
    # find and replace with nothing to elimnate URLs from the string.
    if not re.findall(r'https?:\/\/(?:www.)?nhentai.net', cmt):
        cmt = re.sub(r'https?:\/\/\S+', '', cmt)
    # remove decimal numbers to prevent them from being parsed
    cmt = re.sub(r'\d+\.\d+', '', cmt)
    # remove numbers the nHentaiTagBot is looking for
    cmt = re.sub(r'(?<=\))\d{5}(?=\()', '', cmt)
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


def retrieveTags(galleryNumber):
    # checks if the number is close to the current max to prevent using astronomical numbers
    if galleryNumber < 300000:
        # make galleryNumber a String for concat
        galleryNumber = str(galleryNumber)
        # nhentaiTags = requests.get(API_URL+galleryNumber).json() # ['tags'] #
        request = requests.get(API_URL + str(galleryNumber))
        # catch erounious requests
        if request.status_code != 200:
            return []
        nhentaiTags = json.loads(re.search(r'(?<=N.gallery\().*(?=\))', request.text).group(0))
        # catch returns for invalid numbers
        if "error" in nhentaiTags:
            return []
        else:
            isLoli = False
            isShota = False
            for tags in nhentaiTags['tags']:
                # checks for loli
                if 'lolicon' in tags['name']:
                    isLoli = True
                if 'shotacon' in tags['name']:
                    isShota = True
            return [isLoli, isShota]


def getSavedComments():
    # return an empty list if empty
    if not os.path.isfile("commentsRepliedTo.txt"):
        commentsRepliedTo = []
    else:
        with open("commentsRepliedTo.txt", "r") as f:
            # updated read file method from https://stackoverflow.com/questions/3925614/how-do-you-read-a-file-into-a-list-in-python
            commentsRepliedTo = f.read().splitlines()

    return commentsRepliedTo


if __name__ == '__main__':
    while True:
        try:
            main()
        except Exception as e:
            pass
    # main()